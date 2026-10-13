#!/usr/bin/env python3
"""gp-v4 geometry/program falsification. Model traces are not native evidence."""
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout import generate, world_text
from tools.grand_prix.oracle import Attempt, RADIUS
from tools.grand_prix.lap_progress import candidate_score


def evidence(layout, laps=1, **flags):
    payload=dataclasses.asdict(layout);payload.update(strategyLaps=laps,efficient=True,**flags)
    return subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],cwd=ROOT,
                          input=json.dumps(payload),text=True,capture_output=True)


def judge(layout, data, threshold=180):
    attempt=Attempt(layout,1,.015,threshold);attempt.start(1,0,False)
    complete=data['trace'][-33]['time']
    for sample in data['trace']:
        attempt.sample(sample['time'],sample['position'],sample['velocity'],completed=sample['time']>=complete)
    return attempt


class Tests(unittest.TestCase):
    def test_legacy_worlds_unchanged(self):
        for seed,digest in [(1,'ab67e121554e19809678634cb6afc890215657a13314e9d4f4382733cd55a090'),(4,'5aa9d3d5f0a12ef8657ce0dea458d79b24cb0b7960695de85997b062e2b75f38')]:
            self.assertEqual(hashlib.sha256(world_text(generate(seed)).encode()).hexdigest(),digest)
        self.assertEqual(RADIUS,.09)

    def test_geometry_and_reproducibility(self):
        shapes=set()
        for seed in range(128):
            l=generate(seed,'gp-v4');self.assertEqual(l,generate(seed,'gp-v4'))
            self.assertEqual((l.side,l.width,l.landing_offset),(2.5,1.,.75))
            self.assertTrue(2<=len(l.gates)<=4);self.assertTrue(2<=len(l.final_gates)<=4)
            self.assertTrue(l.final_gates[-1].closed)
            self.assertTrue(all(not g.closed for g in l.final_gates[:-1]))
            self.assertAlmostEqual(l.final_gates[-2].y-l.final_gates[-1].y,1.55)
            self.assertEqual(len([b for b in l.boxes if b.sz==.5]),4-len(l.gates))
            self.assertIn('"gp-v4" "180"',world_text(l));shapes.add((len(l.gates),len(l.final_gates)-1))
        self.assertEqual(shapes,{(a,b) for a in (2,3,4) for b in (1,2,3)})

    def test_public_threshold_boundaries(self):
        for threshold in (120,180,240,300):
            for seconds,penalty in [(threshold-.032,0),(threshold,0),(threshold+.032,1),(threshold+1,1),(threshold+1.032,2)]:
                self.assertEqual(candidate_score(7,seconds,threshold),35-penalty)
        for bad in (True,0,-1,601,180.5,float('nan')):
            with self.assertRaises(ValueError):candidate_score(1,1,bad)

    def test_sensor_witness_on_different_shapes(self):
        for seed in (0,1,4,5,12,16):
            l=generate(seed,'gp-v4')
            for laps in (1,2):
                p=evidence(l,laps);self.assertEqual(p.returncode,0,(seed,laps,p.stderr))
                data=json.loads(p.stdout);a=judge(l,data)
                self.assertEqual(a.result.status,'achieved',(seed,laps,a.failure_reason))
                self.assertEqual(a.result.laps,laps)
                self.assertEqual(a.result.crossings,laps*len(l.gates)+len(l.final_gates)-1)
                self.assertEqual(data['result']['variables']['portes'],len(l.gates))

    def test_saturation_never_certifies_terminal(self):
        for seed in (0,1,4):
            p=evidence(generate(seed,'gp-v4'),injectRangeLossBoth=True)
            self.assertNotEqual(p.returncode,0)
            failure=json.loads(p.stderr.split('WITNESS_FAILURE ',1)[1]);self.assertEqual(failure['lands'],0)

    def test_generic_profile_preflight_budget(self):
        script="""
const W=require('./tools/grand_prix/reference_program_v4'),I=require('./plugins/robot_windows/blockly/webeeblocks/interpreter'),C=require('./plugins/robot_windows/blockly/webeeblocks/activity_contract'),A=require('./plugins/robot_windows/blockly/webeeblocks/activities'),B=require('./plugins/robot_windows/blockly/webeeblocks/wwi_backend'),vm=require('vm'),fs=require('fs');
const c={WebeeBlocksActivities:A,Blockly:{inject(){}},WebeeBlocksWwiBackend:B};c.window=c;
vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix/setup.js','utf8'),c);
for(const laps of [1,2]){const ast=W.build(true,laps),facts=C.preflightAst(c.WebeeBlocksActivities.getProfile('progression-grand-prix-v1'),ast);C.preflightBackend(c.WebeeBlocksActivities.getProfile('progression-grand-prix-v1'),facts,new B({send(){}},{}));I.validateExecutionBudget(ast,20000);}
"""
        subprocess.run(['node','-e',script],cwd=ROOT,check=True)

if __name__=='__main__':unittest.main()
