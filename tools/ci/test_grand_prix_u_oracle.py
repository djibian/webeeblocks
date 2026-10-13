"""Synthetic trajectory boundary tests; not native-flight acceptance."""
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as N
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.grand_prix.oracle_u import Attempt, swept_gap, collides

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

    def test_swept_contact_detects_collision_between_clear_endpoints(self):
        box=N(x=0.,y=0.,z=.5,sx=.04,sy=.04,sz=1.)
        self.assertEqual(swept_gap((-.2,0,.5),(.2,0,.5),box),0.)
        self.assertTrue(collides((-.2,0,.5),(.2,0,.5),box))
        self.assertFalse(collides((-.2,.12,.5),(.2,.12,.5),box))

    def test_valid_corner_arc_not_forced_through_exact_center(self):
        trace=PathTrace(0)
        trace.to((0,0,.8))
        g=trace.layout.gates[0]
        trace.to((g.x-.4,0,.8));trace.to((g.x-.4,0,.4));trace.to((g.x+.4,0,.4));trace.to((g.x+.4,0,.8))
        trace.to((1.7,0,.8));trace.to((1.7,.3,.8))
        self.assertIsNone(trace.oracle.result)
        self.assertEqual(trace.oracle.side,1)


if __name__=='__main__':unittest.main()
