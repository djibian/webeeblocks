"""Synthetic trajectory boundary tests; not native-flight acceptance."""
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as N
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.grand_prix.layout_u import generate
from tools.grand_prix.oracle_u import Attempt, swept_gap, collides, low_segment_allowed, inside, swept_inside, swept_envelope_inside, RADIUS

FIXTURE=Path(__file__).with_name('fixtures')/'grand_prix_u_geometry.json'


def layout(seed):
    data=json.loads(FIXTURE.read_text())[str(seed)]
    result=N(**data)
    result.gates=[N(**g) for g in data['gates']]
    result.boxes=[N(**b) for b in data['walls']+data['gate_boxes']]
    result.identifier=f'fixture-gp-u-v1-{seed}'
    result.landing_target=lambda count:(.70,result.side+{1:0.,2:-.5,3:.5}[count])
    return result


class PathTrace:
    def __init__(self,seed):
        self.layout=layout(seed);self.oracle=Attempt(self.layout,1,.023)
        self.ms=0;self.p=(0.,0.,.023);self.oracle.start(1,0.)
    def sample(self,p,completed=False):
        self.ms+=32;self.p=tuple(p)
        return self.oracle.sample(self.ms/1000,self.p,(0.,0.,0.),completed=completed)
    def to(self,target):
        start=self.p;count=max(1,math.ceil(math.dist(start,target)/.02))
        for i in range(1,count+1):
            self.sample(tuple(a+(b-a)*i/count for a,b in zip(start,target)))
    def route(self):
        self.to((0.,0.,.8))
        starts=((0.,0.,0.),(2.,0.,math.pi/2),(2.,2.,math.pi))
        ends=((2.,0.),(2.,2.),(.7,2.))
        for side in range(3):
            for g in self.layout.gates:
                if g.side!=side:continue
                before=(g.x-.4*math.cos(g.heading),g.y-.4*math.sin(g.heading))
                after=(g.x+.4*math.cos(g.heading),g.y+.4*math.sin(g.heading))
                self.to((*before,.8));self.to((*before,.4))
                self.to((*after,.4));self.to((*after,.8))
            self.to((*ends[side],.8))
        return self
    def finish(self,target=None):
        point=target or self.layout.landing_target(len(self.layout.gates))
        self.to((*point,.8));self.to((*point,.023))
        result=None
        for _ in range(50):result=self.sample(self.p,True)
        return result


class Tests(unittest.TestCase):
    def test_1_2_3_passages_choose_distinct_targets_without_ast_input(self):
        for seed in (0,1,4):
            trace=PathTrace(seed).route();result=trace.finish()
            self.assertEqual(result.status,'achieved',result)
            self.assertEqual(result.crossings,len(trace.layout.gates))
            self.assertFalse(hasattr(result,'score'))
            self.assertFalse(hasattr(result,'laps'))

    def test_wrong_pose_is_irreversible_even_without_contact(self):
        trace=PathTrace(1).route();result=trace.finish((.7,2.))
        self.assertEqual(result.reason,'wrong-landing',result)
        trace.to((.7,1.5,.023))
        self.assertIs(trace.sample(trace.p,True),result)

    def test_single_sample_just_outside_before_and_after_band(self):
        for progress in (-.460001,.460001):
            trace=PathTrace(0);g=trace.layout.gates[0]
            trace.to((0,0,.8))
            if progress>0:
                trace.to((g.x-.4,g.y,.8));trace.to((g.x-.4,g.y,.4))
                trace.to((g.x+.4,g.y,.4));trace.to((g.x+.4,g.y,.8))
            trace.to((g.x+progress,g.y,.8))
            trace.to((g.x+progress,g.y,.59))
            self.assertEqual(trace.oracle.result.reason,'low-outside-zone')

    def test_review_counterexample_between_native_32ms_samples(self):
        trace=PathTrace(0)
        trace.to((0.,0.,.8));trace.to((.370,0.,.6001))
        self.assertIsNone(trace.oracle.result)
        result=trace.sample((.410,0.,.5800))
        self.assertEqual(result.reason,'low-outside-zone')
        self.assertIs(trace.sample((.410,0.,.8)),result)

    def test_entry_exit_vertical_transitions_all_gate_headings(self):
        # Neither endpoint is illegally low: only the continuous segment is.
        # Every native heading, both longitudinal boundaries and both senses.
        for seed in (0,1,4):
            course=layout(seed)
            for g in course.gates:
                for sign in (-1,1):
                    def point(progress,z):
                        return (g.x+progress*math.cos(g.heading),
                                g.y+progress*math.sin(g.heading),z)
                    outside=point(sign*.48,.6001)
                    inside=point(sign*.44,.58)
                    for a,b in ((outside,inside),(inside,outside)):
                        self.assertLess(math.dist(a,b),.064)
                        self.assertFalse(low_segment_allowed(a,b,course))
                    # Descend only after entering; ascend before leaving.
                    safe_out=point(sign*.48,.62)
                    safe_in=point(sign*.44,.5999)
                    for a,b in ((safe_out,safe_in),(safe_in,safe_out)):
                        self.assertTrue(low_segment_allowed(a,b,course))

    def test_band_threshold_boundaries_and_lateral_exit(self):
        course=layout(0);g=course.gates[0]
        left=g.x-.55+.09
        for x,expected in ((left,True),(math.nextafter(left,-math.inf),False),
                           (math.nextafter(left,math.inf),True)):
            self.assertEqual(low_segment_allowed((x,0.,.59),(x,0.,.59),course),expected)
        for z,expected in ((.6,True),(math.nextafter(.6,-math.inf),False),
                           (math.nextafter(.6,math.inf),True)):
            self.assertEqual(low_segment_allowed((.37,0.,z),(.41,0.,z),course),expected)
        # Geometry only: lateral sweep is independently forbidden even when
        # longitudinally in band. Collision checking remains a separate oracle.
        self.assertFalse(low_segment_allowed((g.x,.43,.6001),(g.x,.39,.58),course))

    def test_union_gap_and_bounded_takeoff_final_exceptions(self):
        course=N(gates=[N(x=0.,y=0.,heading=0.),N(x=.93,y=0.,heading=0.)],width=1.,side=2.)
        self.assertFalse(low_segment_allowed((.45,0.,.4),(.48,0.,.4),course))
        course.gates[1].x=.90  # overlapping closed bands cover the whole sweep
        self.assertTrue(low_segment_allowed((.45,0.,.4),(.48,0.,.4),course))
        course.gates=[]
        self.assertFalse(low_segment_allowed((.13,0.,.58),(.15,0.,.6001),course,takeoff_until=1.))
        self.assertTrue(low_segment_allowed((.13,0.,.5999),(.15,0.,.62),course,takeoff_until=1.))
        self.assertFalse(low_segment_allowed((0.,0.,.59),(0.,0.,.59),course,takeoff_until=.5))
        self.assertTrue(low_segment_allowed((.85,2.,.5999),(.87,2.,.62),course,final=True))
        self.assertFalse(low_segment_allowed((.85,2.,.58),(.87,2.,.6001),course,final=True))
        self.assertFalse(low_segment_allowed((.7,2.,.4),(.7,2.,.4),course))

    def test_takeoff_expiration_and_return_do_not_restore_exception(self):
        trace=PathTrace(0);trace.to((0.,0.,.8));trace.to((.16,0.,.8));trace.to((0.,0.,.8));trace.to((0.,0.,.59))
        self.assertEqual(trace.oracle.result.reason,'low-outside-zone')
        trace=PathTrace(0)
        self.assertIsNone(trace.oracle.sample(15.,trace.p,(0.,0.,0.)))
        self.assertEqual(trace.oracle.sample(15.001,trace.p,(0.,0.,0.)).reason,'low-outside-zone')

    def test_low_floor_shortcut_and_bypass_refuse(self):
        trace=PathTrace(0);trace.to((0,0,.8));trace.to((.3,0,.8));trace.to((.3,0,.4))
        self.assertEqual(trace.oracle.result.reason,'low-outside-zone')
        trace=PathTrace(0);trace.to((0,0,.8));trace.to((1.,1.,.8))
        self.assertIn(trace.oracle.result.reason,('envelope-contact','off-track','route-shortcut'))

    def test_partial_oscillation_never_double_counts(self):
        trace=PathTrace(0);g=trace.layout.gates[0]
        trace.to((0,0,.8));trace.to((g.x-.4,0,.8));trace.to((g.x-.4,0,.4))
        trace.to((g.x+.2,0,.4));self.assertEqual(trace.oracle.crossings,0)
        trace.to((g.x-.4,0,.4));self.assertEqual(trace.oracle.crossings,0)
        trace.to((g.x+.4,0,.4));self.assertEqual(trace.oracle.crossings,1)
        trace.to((g.x-.2,0,.4));self.assertEqual(trace.oracle.result.reason,'reverse-crossing')
        self.assertEqual(trace.oracle.crossings,1)

    def test_exact_deadline_before_at_after_and_late_completion(self):
        for ms,failed in ((209999,False),(210000,True),(210001,True)):
            trace=PathTrace(0);trace.to((0,0,.8))
            result=trace.oracle.sample(ms/1000,trace.p,(0.,0.,0.))
            self.assertEqual(result is not None,failed)
            if failed:
                self.assertEqual(result.reason,'time-limit')
                self.assertIs(trace.oracle.sample((ms+1000)/1000,trace.p,(0.,0.,0.),completed=True),result)

    def test_swept_track_boundary_rejects_a_short_corner_cut_without_walls(self):
        # Both samples are strictly inside the concave U polygon, and the
        # observed 32 ms hop is physically plausible, but the chord leaves it.
        course = layout(0)
        a, b = (1.49, .49, .8), (1.51, .53, .8)
        self.assertTrue(inside(a, course.polygon))
        self.assertTrue(inside(b, course.polygon))
        self.assertLess(math.dist(a,b), .064)
        self.assertFalse(swept_inside(a,b,course.polygon))
        self.assertFalse(swept_inside(b,a,course.polygon))
        # Red floor markings are non-colliding. The independent off-track
        # oracle must still reject this path if the old Solid walls are gone.
        course.boxes = []
        attempt = Attempt(course, 1, .023)
        self.assertTrue(attempt.start(1, 0.))
        attempt.previous = a
        self.assertEqual(attempt.sample(.032,b,(0.,0.,0.)).reason,'off-track')

    def test_swept_track_boundary_preserves_legal_corner_arcs_and_tangency(self):
        course = layout(0)
        for a,b in (((1.49,.49),(1.53,.49)),
                    ((1.53,.49),(1.53,.53)),
                    ((1.49,.49),(1.51,.51)),
                    ((0.,0.),(2.,0.)),
                    ((2.,0.),(2.,2.)),
                    ((2.,2.),(.7,2.))):
            self.assertTrue(swept_inside(a,b,course.polygon),(a,b))
            self.assertTrue(swept_inside(b,a,course.polygon),(b,a))
        self.assertFalse(swept_inside((1.49,.49),(1.48,.51),course.polygon))

    def test_swept_contact_detects_collision_between_clear_endpoints(self):
        box=N(x=0.,y=0.,z=.5,sx=.04,sy=.04,sz=1.)
        self.assertEqual(swept_gap((-.2,0,.5),(.2,0,.5),box),0.)
        self.assertTrue(collides((-.2,0,.5),(.2,0,.5),box))
        self.assertFalse(collides((-.2,.12,.5),(.2,.12,.5),box))

    def test_painted_limits_reject_whole_craft_departure_without_colliders(self):
        course = generate(0)
        # The center remains on the track while a rotor envelope crosses the
        # red line. No wall/contact oracle may be credited with this rejection.
        for sign in (-1, 1):
            p = (.30, sign*(course.width/2-RADIUS+.001), .8)
            self.assertTrue(swept_inside(p,p,course.polygon))
            self.assertFalse(swept_envelope_inside(p,p,course.polygon))
            bare = N(polygon=course.polygon, boxes=[], identifier='no-wall-envelope-test')
            attempt = Attempt(bare,1,.023)
            self.assertTrue(attempt.start(1,0.))
            attempt.previous = p
            result = attempt.sample(.032,p,(0.,0.,0.))
            self.assertEqual(result.reason,'off-track')
            self.assertIs(attempt.sample(.064,(.30,0.,.8),(0.,0.,0.)),result)

    def test_concave_corner_envelope_sweep_between_clear_native_samples(self):
        course = generate(0)
        corner = (course.side-course.width/2, course.width/2)
        offset, half = (RADIUS-.001)/math.sqrt(2), .020/math.sqrt(2)
        a = (corner[0]+offset-half, corner[1]-offset-half, .8)
        b = (corner[0]+offset+half, corner[1]-offset+half, .8)
        self.assertLess(math.dist(a,b),.064)
        self.assertTrue(swept_inside(a,b,course.polygon))
        for p in (a,b):
            self.assertTrue(swept_envelope_inside(p,p,course.polygon))
        for first,last in ((a,b),(b,a)):
            self.assertFalse(swept_envelope_inside(first,last,course.polygon))
            attempt = Attempt(N(polygon=course.polygon,boxes=[],identifier='no-wall-corner-test'),1,.023)
            attempt.start(1,0.); attempt.previous=first
            self.assertEqual(attempt.sample(.032,last,(0.,0.,0.)).reason,'off-track')

    def test_whole_craft_boundary_preserves_clear_routes_and_tangency(self):
        for seed in (0,1,4,65535):
            course = generate(seed)
            points = ((0.,0.),(2.,0.),(2.,2.),(.7,2.))
            for a,b in zip(points,points[1:]):
                self.assertTrue(swept_envelope_inside(a,b,course.polygon))
                self.assertTrue(swept_envelope_inside(b,a,course.polygon))
        square = ((0.,0.),(1.,0.),(1.,1.),(0.,1.))
        self.assertTrue(swept_envelope_inside((RADIUS,.2),(RADIUS,.8),square))
        outside = math.nextafter(RADIUS,0.)
        self.assertFalse(swept_envelope_inside((outside,.2),(outside,.8),square))

    def test_valid_corner_arc_not_forced_through_exact_center(self):
        trace=PathTrace(0)
        trace.to((0,0,.8))
        g=trace.layout.gates[0]
        trace.to((g.x-.4,0,.8));trace.to((g.x-.4,0,.4));trace.to((g.x+.4,0,.4));trace.to((g.x+.4,0,.8))
        trace.to((1.7,0,.8));trace.to((1.7,.3,.8))
        self.assertIsNone(trace.oracle.result)
        self.assertEqual(trace.oracle.side,1)


if __name__=='__main__':unittest.main()
