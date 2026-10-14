"""Behavior-only three-side oracle. No AST inspection or score surface."""
from dataclasses import dataclass
import math
from .simulation_time import milliseconds

ORACLE = 'grand-prix-u-v1'
RADIUS = .09
DEADLINE_MS = 210000
LOW_THRESHOLD = .60
LOW_BEFORE = LOW_AFTER = .55
FRAME_CLEAR = .24 + RADIUS
LANDING_TOL = .14


def local(g, p):
    dx,dy = p[0]-g.x,p[1]-g.y
    return dx*math.cos(g.heading)+dy*math.sin(g.heading), -dx*math.sin(g.heading)+dy*math.cos(g.heading)


def swept_gap(a, b, box):
    """Exact minimum Euclidean segment/AABB gap, including corner arcs."""
    center = (box.x,box.y,box.z)
    half = (box.sx/2,box.sy/2,box.sz/2)
    delta = [y-x for x,y in zip(a,b)]
    cuts = [0.,1.]
    for x,d,c,h in zip(a,delta,center,half):
        if d:
            cuts += [t for t in ((c-h-x)/d,(c+h-x)/d) if 0<t<1]
    cuts = sorted(set(cuts))
    def square(t):
        return sum(max(abs(x+d*t-c)-h,0)**2 for x,d,c,h in zip(a,delta,center,half))
    best = min(square(t) for t in cuts)
    for lo,hi in zip(cuts,cuts[1:]):
        numerator=denominator=0.
        middle=(lo+hi)/2
        for x,d,c,h in zip(a,delta,center,half):
            q=x+d*middle-c
            if abs(q)>h:
                offset=x-c-math.copysign(h,q)
                numerator += offset*d
                denominator += d*d
        if denominator:
            best=min(best,square(max(lo,min(hi,-numerator/denominator))))
    return math.sqrt(best)


def inside(p, polygon):
    x,y=p[:2];value=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
            value=not value
    return value


def collides(a,b,box):
    # Distance to a closed set is 1-Lipschitz. A remote box cannot meet a
    # segment shorter than its initial clearance minus the preserved radius.
    initial=math.sqrt(sum(max(abs(x-c)-s/2,0)**2 for x,c,s in
                         zip(a,(box.x,box.y,box.z),(box.sx,box.sy,box.sz))))
    if initial >= RADIUS+math.dist(a,b):return False
    return swept_gap(a,b,box)<RADIUS



def clipped_interval(a, b, bounds):
    """Closed segment parameters inside a convex axis-aligned region."""
    lo, hi = 0., 1.
    for x, y, (lower, upper) in zip(a, b, bounds):
        delta = y-x
        if not delta:
            if not lower <= x <= upper: return None
        else:
            first, last = sorted(((lower-x)/delta, (upper-x)/delta))
            lo, hi = max(lo, first), min(hi, last)
            if lo > hi: return None
    return lo, hi


def low_segment_allowed(a, b, layout, *, final=False, takeoff_until=None):
    """Cover the entire strictly-low part by the union of bounded exceptions.

    Parameter intervals avoid endpoint-only tests and arbitrary subdivisions.
    Closed zone boundaries and z == LOW_THRESHOLD remain legal; no epsilon
    enlarges a permitted region. This proves the observed straight segment,
    not an unobserved curve between samples.
    """
    if min(a[2], b[2]) >= LOW_THRESHOLD: return True
    low = clipped_interval((a[2],), (b[2],), ((-math.inf, LOW_THRESHOLD),))
    intervals = []
    for g in layout.gates:
        interval = clipped_interval(local(g, a), local(g, b),
            ((-LOW_BEFORE+RADIUS, LOW_AFTER-RADIUS),
             (-layout.width/2+RADIUS, layout.width/2-RADIUS)))
        if interval is not None: intervals.append(interval)
    if final:
        interval = clipped_interval(a[:2], b[:2],
            ((.11, .86), (layout.side-.81, layout.side+.81)))
        if interval is not None: intervals.append(interval)
    if takeoff_until is not None:
        # Disk intersection plus the exact 15 s temporal bound. The caller
        # disables this exception permanently after the first exit.
        dx, dy = b[0]-a[0], b[1]-a[1]
        aa = dx*dx+dy*dy
        bb = 2*(a[0]*dx+a[1]*dy)
        cc = a[0]*a[0]+a[1]*a[1]-.14**2
        if not aa:
            if cc <= 0: intervals.append((0., min(1., takeoff_until)))
        else:
            disc = bb*bb-4*aa*cc
            if disc >= 0:
                first, last = (-bb-math.sqrt(disc))/(2*aa), (-bb+math.sqrt(disc))/(2*aa)
                lo, hi = max(0., first), min(1., last, takeoff_until)
                if lo <= hi: intervals.append((lo, hi))
    covered = low[0]
    for lo, hi in sorted(intervals):
        if hi < covered: continue
        if lo > covered: return False
        covered = max(covered, hi)
        if covered >= low[1]: return True
    return False


@dataclass(frozen=True)
class Result:
    status: str
    configuration: str
    attempt: int
    seconds: float
    reason: str | None
    crossings: int


class Attempt:
    def __init__(self, layout, attempt, origin_z):
        if type(attempt) is not int or attempt<1 or not math.isfinite(origin_z):
            raise ValueError('invalid attempt identity/origin')
        self.layout,self.attempt,self.origin_z=layout,attempt,origin_z
        self.start_ms=None;self.last_ms=None;self.previous=(0.,0.,origin_z)
        self.result=None;self.failure_reason=None;self.airborne=False
        self.side=0;self.cursor=0;self.armed=False;self.crossed=False
        self.takeoff_done=False;self.stationary_ms=None;self.completion_ms=None

    @property
    def crossings(self): return self.cursor

    def start(self, attempt, now):
        if attempt != self.attempt or self.start_ms is not None or self.result is not None:
            return False
        self.start_ms=milliseconds(now);self.last_ms=self.start_ms
        return True

    def fail(self, now, reason):
        if self.result is None:
            end=milliseconds(now)
            seconds=0. if self.start_ms is None else (end-self.start_ms)/1000
            self.failure_reason=reason
            self.result=Result('not-achieved',self.layout.identifier,self.attempt,seconds,reason,self.cursor)
        return self.result

    def sample(self, now, p, velocity, contacts=(), completed=False):
        if self.result is not None or self.start_ms is None: return self.result
        ms=milliseconds(now)
        if ms < self.last_ms: return self.fail(now,'invalid-clock')
        if ms-self.start_ms >= DEADLINE_MS: return self.fail(now,'time-limit')
        if len(p)!=3 or len(velocity)!=3 or not all(math.isfinite(v) for v in (*p,*velocity)):
            return self.fail(now,'invalid-sample')
        if math.dist(p,self.previous)>max(.06,(ms-self.last_ms)/1000*2):
            return self.fail(now,'sample-displacement')
        x,y,z=p
        if z<self.origin_z-.02 or z>self.origin_z+1.15:
            return self.fail(now,'altitude')
        if not inside(p,self.layout.polygon): return self.fail(now,'off-track')
        if any(collides(self.previous,p,b) for b in self.layout.boxes):
            return self.fail(now,'envelope-contact')
        if any(len(c)!=3 or not all(math.isfinite(v) for v in c) or c[2]>.012 for c in contacts):
            return self.fail(now,'device-contact')
        if z>self.origin_z+.20:self.airborne=True
        takeoff_until = None
        if not self.takeoff_done:
            remaining = self.start_ms+15000-self.last_ms
            takeoff_until = remaining/(ms-self.last_ms) if ms>self.last_ms else (1. if remaining>=0 else -1.)
        if not low_segment_allowed(self.previous, p, self.layout,
                final=self.side==2, takeoff_until=takeoff_until):
            return self.fail(now,'low-outside-zone')
        if math.hypot(x,y)>.14 or ms-self.start_ms>15000:self.takeoff_done=True
        if self.side==0 and y>.41 or self.side==1 and x<self.layout.side-.41:
            return self.fail(now,'route-shortcut')
        if self.side==2 and y<self.layout.side-.9+RADIUS:
            return self.fail(now,'route-shortcut')
        # Gate events cannot be supplied by the AST or inferred from detection.
        if self.cursor < len(self.layout.gates):
            g=self.layout.gates[self.cursor]
            progress,offset=local(g,p);before,_=local(g,self.previous)
            if progress <= -FRAME_CLEAR:self.armed=True
            if g.side==self.side:
                if self.armed and before<.11<=progress:
                    if abs(offset)+RADIUS> .28 or z+RADIUS>.62 or z-RADIUS<.10:
                        return self.fail(now,'gate-envelope')
                    self.crossed=True
                if self.crossed and progress < -.11:
                    self.crossed=False;self.armed=False
                if progress>=FRAME_CLEAR:
                    if not (self.armed and self.crossed):return self.fail(now,'missed-gate')
                    self.cursor+=1;self.armed=False;self.crossed=False
        for g in self.layout.gates[:self.cursor]:
            if g.side==self.side and local(g,p)[0]<-.11:
                return self.fail(now,'reverse-crossing')
        if self.side<2:
            corner=(self.layout.side,0.) if self.side==0 else (self.layout.side,self.layout.side)
            if abs(x-corner[0])<=.40 and abs(y-corner[1])<=.40:
                if self.cursor<len(self.layout.gates) and self.layout.gates[self.cursor].side<=self.side:
                    return self.fail(now,'missed-gate')
                self.side+=1;self.crossed=False
        if completed and self.completion_ms is None:self.completion_ms=ms
        if self.completion_ms is not None:
            target=self.layout.landing_target(len(self.layout.gates))
            eligible=(self.airborne and self.side==2 and self.cursor==len(self.layout.gates) and
                      z<=self.origin_z+.07 and math.hypot(*velocity[:2])<=.12 and abs(velocity[2])<=.12 and
                      abs(x-target[0])<=LANDING_TOL and abs(y-target[1])<=LANDING_TOL)
            if eligible:
                if self.stationary_ms is None:self.stationary_ms=ms
                if ms-self.stationary_ms>=500:
                    self.result=Result('achieved',self.layout.identifier,self.attempt,
                                       (ms-self.start_ms)/1000,None,self.cursor)
            else:self.stationary_ms=None
            if self.result is None and ms-self.completion_ms>=1500:
                return self.fail(now,'wrong-landing')
        self.previous=tuple(p);self.last_ms=ms
        return self.result
