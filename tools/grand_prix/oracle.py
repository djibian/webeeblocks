"""Behavioral trajectory oracle; inputs only from a simulation supervisor."""
from __future__ import annotations
import math
from dataclasses import dataclass
from .layout import Gate, Layout, WIDTH, local
from .lap_progress import Progress, candidate_score
from .simulation_time import elapsed_seconds, milliseconds

ORACLE='grand-prix-v1'
RADIUS=.09
MAX_TIME=600.

@dataclass(frozen=True)
class Result:
    status: str
    configuration: str
    attempt: int
    seconds: float | None
    laps: int = 0
    crossings: int = 0
    candidate_points: int | None = None

class Attempt:
    def __init__(self, layout: Layout, attempt: int, origin_z: float):
        if type(attempt) is not int or attempt < 1 or not math.isfinite(origin_z): raise ValueError('invalid attempt origin')
        self.layout,self.attempt,self.origin_z=layout,attempt,origin_z
        self.start_time=None;self.last_time=None;self.debug=False;self.result=None
        self.previous=(0.,0.,origin_z);self.airborne=False;self.cursor=0;self.armed=False
        self.events=[];self.completion_time=None;self.stationary_since=None;self.failure_reason=None
        side=layout.side
        corners=[(side,0),(side,side),(0,side),(0,0)]
        for side,corner in enumerate(corners):
            for gate in layout.gates:
                heading=round((gate.heading%(2*math.pi))/(math.pi/2))%4
                if heading==side:self.events.append(gate)
            self.events.append(corner)
        ring=tuple('h:'+str(i) if isinstance(event,Gate) else ('junction' if i==len(self.events)-1 else 'corner:'+str(i)) for i,event in enumerate(self.events))
        self.final_events=[gate for gate in layout.final_gates if not gate.closed]
        self.progress=Progress(ring,tuple('final:'+str(i) for i in range(len(self.final_events))))
        self.exit_started=False

    def _advance(self):
        if not self.progress.advance(self.progress.expected):
            self.fail('route-bound')
        self.cursor=self.progress.cursor

    def start(self, attempt: int, sim_time: float, debug: bool):
        if attempt != self.attempt: return False
        if type(debug) is not bool or not math.isfinite(sim_time) or sim_time < 0: return self.fail('invalid-start')
        if self.start_time is not None:
            # A repeated mode message cannot erase the taint or restart a clock.
            self.debug=self.debug or debug
            return False
        try:milliseconds(sim_time)
        except ValueError:return self.fail('invalid-start-clock')
        self.start_time=sim_time;self.last_time=sim_time;self.debug=debug
        return True

    def fail(self,reason='invalid-attempt'):
        if self.result is None:
            self.failure_reason=reason
            self.progress.fail()
            self.result=Result('not-achieved',self.layout.identifier,self.attempt,None,self.progress.laps,self.progress.crossings)
        return False

    def sample(self, sim_time, position, velocity, contacts=(), completed=False):
        if self.result is not None or self.start_time is None:return self.result
        if len(position)!=3 or len(velocity)!=3 or not all(math.isfinite(v) for v in [sim_time,*position,*velocity]):self.fail('invalid-sample');return self.result
        try:duration=elapsed_seconds(self.start_time,sim_time)
        except ValueError:self.fail('invalid-clock');return self.result
        if sim_time<self.last_time or duration>MAX_TIME:self.fail('clock-or-deadline');return self.result
        elapsed=sim_time-self.last_time
        if math.dist(position,self.previous) > max(.06,elapsed*.7):self.fail('sample-displacement');return self.result
        self.last_time=sim_time
        x,y,z=position
        if z>self.origin_z+.2:self.airborne=True
        if z>self.origin_z+1.15 or z<self.origin_z-.02:self.fail('altitude')
        for box in self.layout.boxes:
            gap=[max(abs(value-center)-size/2,0) for value,center,size in zip(position,(box.x,box.y,box.z),(box.sx,box.sy,box.sz))]
            if math.sqrt(sum(d*d for d in gap))<RADIUS:self.fail('envelope-contact')
        if any(len(p)!=3 or not all(math.isfinite(v) for v in p) or p[2]>.012 for p in contacts):self.fail('device-contact')
        # Inner clearance is already judged by the exact sphere/Box distance.
        # Expanding the island again as a rectangle rejects safe corner arcs.
        on_ring=(-.4+RADIUS<=x<=self.layout.side+.4-RADIUS and -.4+RADIUS<=y<=self.layout.side+.4-RADIUS)
        on_final=abs(x)<=.4-RADIUS and self.layout.final_gates[-1].y+.02+RADIUS<=y<=.31
        if not on_ring and not on_final:self.fail('off-track')
        if self.exit_started and not on_final:self.fail('return-after-exit')
        if y<-.31 and not self.exit_started:
            if not self.progress.choose_exit():self.fail('early-exit')
            else:
                self.exit_started=True;self.events=self.final_events;self.cursor=0;self.armed=False
        if self.result:return self.result
        if self.cursor<len(self.events):
            event=self.events[self.cursor]
            if isinstance(event,Gate):
                progress,offset=local(event,position)
                before,_=local(event,self.previous)
                if progress<=-.10:self.armed=True
                if -.11<=progress<=.11 and (abs(offset)+RADIUS>.28 or z+RADIUS>.62 or z-RADIUS<.10):self.fail('gate-envelope')
                if self.armed and before<.10<=progress:
                    if abs(offset)+RADIUS>.28 or z+RADIUS>.62 or z-RADIUS<.10:self.fail('gate-envelope')
                    else:self._advance();self.armed=False
            elif abs(x-event[0])<=WIDTH/2 and abs(y-event[1])<=WIDTH/2 and self.airborne:
                self._advance();self.armed=False
        self.previous=tuple(position)
        if completed and self.completion_time is None:self.completion_time=sim_time
        if self.completion_time is not None:
            landed=z<=self.origin_z+.07
            stationary=math.hypot(*velocity[:2])<=.12 and abs(velocity[2])<=.12
            arrival=abs(x)<=.14 and abs(y-(self.layout.final_gates[-1].y+.25))<=.14
            eligible=self.airborne and self.progress.final_complete and landed and stationary and arrival
            if eligible:
                if self.stationary_since is None:self.stationary_since=sim_time
                if sim_time-self.stationary_since>=.5:
                    seconds=None if self.debug else duration
                    self.result=Result('achieved',self.layout.identifier,self.attempt,seconds,self.progress.laps,self.progress.crossings,None if seconds is None else candidate_score(self.progress.crossings,seconds))
            else:self.stationary_since=None
            if self.result is None and sim_time-self.completion_time>=1.5:self.fail('invalid-completion')
        return self.result
