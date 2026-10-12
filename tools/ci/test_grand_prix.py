#!/usr/bin/env python3
"""Ideal geometry/candidate-oracle checks; not Webots dynamics acceptance."""
from pathlib import Path
import dataclasses
import json
import math
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout import generate,ray_distance,world_text
from tools.grand_prix.oracle import Attempt

class Tests(unittest.TestCase):
    def test_reproducible_and_bounded(self):
        counts=set();finals=set()
        for seed in range(100):
            layout=generate(seed);self.assertEqual(world_text(layout),world_text(generate(seed)))
            self.assertIn('boundingObject Box',world_text(layout));self.assertNotIn('lap=',world_text(layout))
            counts.add(len(layout.gates));finals.add(len(layout.final_gates))
            self.assertLessEqual(len(layout.gates),4)
            for gate in layout.gates:
                x,y=gate.x-.2*math.cos(gate.heading),gate.y-.2*math.sin(gate.heading)
                high=ray_distance(layout,x,y,.91,gate.heading);low=ray_distance(layout,x,y,.41,gate.heading)
                self.assertIsNotNone(high);self.assertIsNotNone(low);self.assertGreater(low,high+.3)
                for side in [-1,1]:self.assertAlmostEqual(ray_distance(layout,x,y,.91,gate.heading+side*math.pi/2),.28,places=5)
            final=layout.final_gates[-1];x,y=final.x-.12*math.cos(final.heading),final.y-.12*math.sin(final.heading)
            self.assertAlmostEqual(ray_distance(layout,x,y,.91,final.heading),ray_distance(layout,x,y,.41,final.heading))
        self.assertEqual(counts,{2,3,4});self.assertEqual(finals,{1,2})
        for seed in [-1,65536,True,1.5]:
            with self.assertRaises(ValueError):generate(seed)

    def test_same_sensor_only_ast_across_layouts(self):
        for seed in [*range(16),42,65535]:
            layout=generate(seed)
            result=subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],input=json.dumps(dataclasses.asdict(layout)),cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            evidence=json.loads(result.stdout)
            witness=evidence['result']['variables']
            self.assertEqual(witness['invalide'],0,(seed,witness))
            self.assertEqual(witness['portes'],len(layout.gates),(seed,witness))
            self.assertEqual(witness['restantes'],0,(seed,witness))
            self.assertEqual(witness['fin'],1,(seed,witness))
            self.assertEqual(witness['portes finales'],len(layout.final_gates)-1)
            active=Attempt(layout,1,.015);active.start(1,0,False)
            landing=evidence['trace'][-33]['time']
            for sample in evidence['trace']:
                active.sample(sample['time'],sample['position'],sample['velocity'],completed=sample['time']>=landing)
                if active.result and active.result.status!='achieved':break
            self.assertIsNotNone(active.result,(seed,active.cursor,len(active.events)))
            self.assertEqual(active.result.status,'achieved',(seed,active.cursor,evidence['trace'][-1]))
            self.assertGreater(active.result.seconds,0)

    def test_missing_low_return_is_neither_open_nor_closed(self):
        layout=dataclasses.asdict(generate(1));layout['injectRangeLoss']=True
        result=subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],input=json.dumps(layout),cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        values=json.loads(result.stdout)['result']['variables']
        self.assertEqual(values['invalide'],1)
        self.assertEqual(values['fin'],0)

    def test_refutations_and_clock_binding(self):
        layout=generate(3)
        for position,contacts in [([.7,.7,.9],[]),([0,-.8,.4],[]),([0,0,1.3],[]),([0,0,.4],[[0,0,.1]])]:
            attempt=Attempt(layout,1,.015);attempt.start(1,0,False)
            attempt.sample(2,position,[0,0,0],contacts,True)
            self.assertEqual(attempt.result.status,'not-achieved');self.assertIsNone(attempt.result.seconds)
        attempt=Attempt(layout,2,.015)
        self.assertFalse(attempt.start(1,0,False));self.assertIsNone(attempt.start_time)
        attempt.start(2,1,True);attempt.start(2,2,False)
        self.assertTrue(attempt.debug);self.assertEqual(attempt.start_time,1)
        attempt.sample(.5,[0,0,.015],[0,0,0]);self.assertEqual(attempt.result.status,'not-achieved')
        # A stationary vehicle / repeated corner samples cannot make any lap.
        attempt=Attempt(layout,3,.015);attempt.start(3,0,False)
        for i in range(1,20):attempt.sample(i*.032,[0,0,.015],[0,0,0])
        self.assertEqual(attempt.cursor,0)
        attempt.sample(1,[0,0,.015],[0,0,0],completed=True)
        attempt.sample(3,[0,0,.015],[0,0,0],completed=True)
        self.assertEqual(attempt.result.status,'not-achieved')

if __name__=='__main__':unittest.main()
