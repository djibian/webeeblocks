#!/usr/bin/env python3
"""Versioned compact candidate checks. Ideal traces never prove native timing."""
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


class Tests(unittest.TestCase):
    def test_legacy_worlds_remain_byte_identical(self):
        hashes={1:'ab67e121554e19809678634cb6afc890215657a13314e9d4f4382733cd55a090',
                4:'5aa9d3d5f0a12ef8657ce0dea458d79b24cb0b7960695de85997b062e2b75f38'}
        for seed,digest in hashes.items():
            self.assertEqual(hashlib.sha256(world_text(generate(seed)).encode()).hexdigest(),digest)
            self.assertEqual(generate(seed).side,1.4)
        with self.assertRaises(ValueError):generate(1,'unknown')

    def test_compact_is_explicit_and_preserves_obstacle_envelopes(self):
        self.assertEqual(RADIUS,.09)
        for seed in (6,12,16):
            layout=generate(seed,'gp-v3')
            self.assertEqual(layout.side,1.0)
            self.assertEqual(layout.identifier,f'gp-v3-{seed}')
            self.assertIn(f'controllerArgs [ "{seed}" "gp-v3" ]',world_text(layout))
            self.assertEqual(layout,generate(seed,'gp-v3'))
            # Every H retains its two full-height 48 cm approach plates.
            near=[b for b in layout.boxes if b.z==.65 and b.sz==1.3 and
                  ((b.sx==.48 and b.sy==.04) or (b.sx==.04 and b.sy==.48))]
            self.assertEqual(len(near),2*(len(layout.gates)+len(layout.final_gates)))
            low=[b for b in layout.boxes if b.z==.25 and b.sz==.5]
            self.assertEqual(len(low),4-len(layout.gates))
            self.assertTrue(all(sorted((b.sx,b.sy))==[.08,.8] for b in low))

    @staticmethod
    def evidence(layout,laps,memory=False,loss=False):
        payload=dataclasses.asdict(layout)
        payload.update(strategyLaps=laps,efficient=True,memoryChoice=memory,injectRangeLossBoth=loss)
        return subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],cwd=ROOT,
                              input=json.dumps(payload),text=True,capture_output=True)

    def test_all_22_shapes_fixed_and_count_based_exit(self):
        representatives={}
        for seed in range(65536):
            layout=generate(seed,'gp-v3')
            representatives.setdefault((layout.gates,layout.final_gates),seed)
        self.assertEqual(len(representatives),22)
        for memory,laps in ((False,1),(False,2),(False,3),(True,2)):
            for seed in representatives.values():
                layout=generate(seed,'gp-v3');process=self.evidence(layout,laps,memory)
                self.assertEqual(process.returncode,0,(seed,laps,memory,process.stderr))
                evidence=json.loads(process.stdout)
                variables=evidence['result']['variables']
                self.assertEqual(variables['invalide'],0)
                self.assertEqual(variables['portes'],len(layout.gates))
                self.assertEqual(variables['restantes'],0)
                self.assertEqual(variables['fin'],1)
                active=Attempt(layout,1,.015);active.start(1,0,False)
                landing=evidence['trace'][-33]['time']
                for sample in evidence['trace']:
                    active.sample(sample['time'],sample['position'],sample['velocity'],completed=sample['time']>=landing)
                self.assertEqual(active.result.status,'achieved',(seed,active.failure_reason))
                expected=(2 if len(layout.gates)==4 else 1) if memory else laps
                self.assertEqual(active.result.laps,expected)
                self.assertEqual(active.result.crossings,expected*len(layout.gates)+len(layout.final_gates)-1)

    def test_terminal_double_saturation_refuses_land(self):
        for seed in (6,16):
            process=self.evidence(generate(seed,'gp-v3'),1,loss=True)
            self.assertNotEqual(process.returncode,0)
            failure=json.loads(process.stderr.split('WITNESS_FAILURE ',1)[1])
            self.assertEqual(failure['lands'],0)
            self.assertIn('iteration limit exceeded',failure['message'])

    def test_early_final_turn_and_uncapped_learned_stride_are_refuted(self):
        for seed,laps,flag in ((12,2,'skipLearnedFinalCorner'),(6,3,'unsafeCompactStride')):
            layout=generate(seed,'gp-v3');payload=dataclasses.asdict(layout)
            payload.update(strategyLaps=laps,efficient=True);payload[flag]=True
            process=subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],cwd=ROOT,
                                   input=json.dumps(payload),text=True,capture_output=True)
            if flag=='skipLearnedFinalCorner':
                self.assertNotEqual(process.returncode,0)
                failure=json.loads(process.stderr.split('WITNESS_FAILURE ',1)[1])
                self.assertEqual(failure['lands'],0)
            else:
                self.assertEqual(process.returncode,0,process.stderr)
                evidence=json.loads(process.stdout);active=Attempt(layout,1,.015);active.start(1,0,False)
                for sample in evidence['trace']:active.sample(sample['time'],sample['position'],sample['velocity'])
                self.assertEqual(active.failure_reason,'envelope-contact')
                self.assertIsNone(active.result.candidate_points)

    def test_fixed_programmes_keep_existing_preflight_budget(self):
        script="""
const W=require('./tools/grand_prix/reference_program_compact'),I=require('./plugins/robot_windows/blockly/webeeblocks/interpreter'),C=require('./plugins/robot_windows/blockly/webeeblocks/activity_contract'),A=require('./plugins/robot_windows/blockly/webeeblocks/activities'),B=require('./plugins/robot_windows/blockly/webeeblocks/wwi_backend'),vm=require('vm'),fs=require('fs');
const context={WebeeBlocksActivities:A,Blockly:{inject(){}},WebeeBlocksWwiBackend:B};context.window=context;
vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix/setup.js','utf8'),context);
const profile=context.WebeeBlocksActivities.getProfile('progression-grand-prix-v1'),backend=new B({send(){}},{});
for(const [laps,memory] of [[1,false],[2,false],[3,false],[2,true]]){const ast=W.build(true,laps,true,memory);I.validateExecutionBudget(ast,20000);const facts=C.preflightAst(profile,ast);C.preflightBackend(profile,facts,backend);}
console.log('PASS generic compact ASTs: actual profile/backend preflight and unchanged 20000 budget');
"""
        subprocess.run(['node','-e',script],cwd=ROOT,check=True)


if __name__=='__main__':unittest.main()
