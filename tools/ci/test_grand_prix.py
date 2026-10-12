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
from tools.grand_prix.layout import Box,Gate,Layout,generate,ray_distance,world_text
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
        # Geometry is determined by these gates; absent sides receive their
        # low obstacle deterministically. Cover every shape over the full
        # supported seed domain, without passing any seed/count into the AST.
        representatives={}
        for seed in range(65536):
            layout=generate(seed)
            representatives.setdefault((layout.gates,layout.final_gates),seed)
        self.assertEqual(len(representatives),92)
        for seed in representatives.values():
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

    def test_double_saturation_is_uncertain_but_can_land_in_arrival(self):
        layout=generate(4);payload=dataclasses.asdict(layout);payload['injectRangeLossBoth']=True
        evidence=json.loads(subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],input=json.dumps(payload),cwd=ROOT,text=True,capture_output=True,check=True).stdout)
        values=evidence['result']['variables']
        self.assertEqual(values['invalide'],1)
        self.assertEqual(values['fin'],0)
        # A behavioural oracle cannot infer this variable or a sensor's
        # semantic certainty. An explicit generic programme failure remains
        # necessary: normal LAND/COMPLETE can still score a valid trajectory.
        active=Attempt(layout,1,.015);active.start(1,0,False)
        landing=evidence['trace'][-33]['time']
        for sample in evidence['trace']:active.sample(sample['time'],sample['position'],sample['velocity'],completed=sample['time']>=landing)
        self.assertEqual(active.result.status,'achieved')
        self.assertIsNotNone(active.result.seconds)

    def test_generic_until_composition_or_refusal_without_language(self):
        # Probe the actual shared interpreter, not an alternative implementation.
        feature="""const I=require('./plugins/robot_windows/blockly/webeeblocks/interpreter');
const ast={version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.5},{kind:'while',mode:'UNTIL',condition:{kind:'number',value:1},body:[],max_iterations:20},{kind:'land'}]};
try { I.validateProgram(ast); console.log('supported'); } catch(e) { if(!/unsupported statement/.test(e.message))throw e; console.log('unavailable'); }"""
        supported=subprocess.run(['node','-e',feature],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()=='supported'
        for seed in [1,4]:
            for fault in [False,True]:
                payload=dataclasses.asdict(generate(seed));payload.update(useConditionalLoops=True,injectRangeLossBoth=fault)
                process=subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],input=json.dumps(payload),cwd=ROOT,text=True,capture_output=True)
                if supported and not fault:
                    self.assertEqual(process.returncode,0,process.stderr)
                    evidence=json.loads(process.stdout)
                    self.assertEqual(evidence['result']['variables']['fin'],1)
                    self.assertEqual(evidence['lands'],1)
                else:
                    self.assertNotEqual(process.returncode,0)
                    failure=json.loads(process.stderr.split('WITNESS_FAILURE ',1)[1].strip())
                    self.assertEqual(failure['lands'],0)
                    if supported:self.assertIn('iteration limit exceeded',failure['message'])
                    else:self.assertEqual(failure['last_position'],[0,0,.015])

    def test_safe_rounded_corner_is_not_a_solution_shape_oracle(self):
        layout=next(generate(seed) for seed in range(100) if not any(g.heading==0 for g in generate(seed).gates))
        # Independent geometry: the whole 9 cm envelope clears the island
        # corner (1.0, .4) and the outer walls at x=1.8 and y=-.4.
        point=[1.22,.18,.415]
        self.assertGreater(math.hypot(point[0]-1.0,point[1]-.4),.09)
        self.assertGreater(1.8-point[0],.09)
        self.assertGreater(point[1]+.4,.09)
        active=Attempt(layout,1,.015);active.start(1,0,False)
        active.sample(4,point,[0,0,0])
        self.assertEqual(active.cursor,1)
        # Repeated corner readings still cannot produce the next corner/lap.
        for i in range(1,20):active.sample(4+i*.032,point,[0,0,0])
        self.assertEqual(active.cursor,1)

    def test_v1_blind_counterexample_and_v2_repair(self):
        def outcome(layout,blind):
            payload=dataclasses.asdict(layout);payload['blind']=blind
            result=subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],input=json.dumps(payload),cwd=ROOT,text=True,capture_output=True,check=True)
            evidence=json.loads(result.stdout);active=Attempt(layout,1,.015);active.start(1,0,False)
            landed=evidence['trace'][-33]['time']
            for sample in evidence['trace']:active.sample(sample['time'],sample['position'],sample['velocity'],completed=sample['time']>=landed)
            return active.result,evidence['ranges']
        for fixture in json.loads((ROOT/'tools/ci/fixtures/grand_prix_v1_blind_counterexample.json').read_text()):
            v=fixture['layout'];old=Layout(v['seed'],tuple(Gate(**g) for g in v['gates']),tuple(Gate(**g) for g in v['final_gates']),tuple(Box(**b) for b in v['boxes']),'gp-v1')
            result,reads=outcome(old,True)
            self.assertEqual(result.status,'achieved');self.assertEqual(reads,[])
        failed=0;targets=set()
        for seed in range(16):
            result,reads=outcome(generate(seed),True)
            self.assertEqual(reads,[])
            if result.status=='not-achieved':failed+=1
            targets.add(generate(seed).final_gates[-1].y+.25)
        self.assertGreater(failed,0)
        self.assertEqual({round(t,2) for t in targets},{-.85,-.55})

    def test_gate_count_memory_is_not_behaviorally_necessary_yet(self):
        layout=generate(4);payload=dataclasses.asdict(layout);payload['forgetCounts']=True
        evidence=json.loads(subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],input=json.dumps(payload),cwd=ROOT,text=True,capture_output=True,check=True).stdout)
        values=evidence['result']['variables']
        self.assertEqual(values['portes'],0)
        self.assertEqual(values['restantes'],0)
        self.assertEqual(values['invalide'],0)
        active=Attempt(layout,1,.015);active.start(1,0,False)
        landed=evidence['trace'][-33]['time']
        for sample in evidence['trace']:active.sample(sample['time'],sample['position'],sample['velocity'],completed=sample['time']>=landed)
        self.assertEqual(active.result.status,'achieved')
        # Keep the positive counterexample. Rejecting this trajectory by AST
        # shape would hide the pedagogical limitation and violate the oracle.

    def test_unexpected_closure_has_same_ranges_but_no_success(self):
        layout=generate(1)
        opened=layout.final_gates[0]
        self.assertFalse(opened.closed)
        # An unforeseen lower panel has the same high/low observations as a
        # terminal closed H. Sensors alone cannot attach a semantic identity.
        obstruction=Box(opened.x,opened.y,.31,.56,.04,.62)
        attack=dataclasses.replace(layout,boxes=(*layout.boxes,obstruction))
        payload=dataclasses.asdict(attack)
        evidence=json.loads(subprocess.run(['node','tools/ci/test_grand_prix_witness.js'],input=json.dumps(payload),cwd=ROOT,text=True,capture_output=True,check=True).stdout)
        values=evidence['result']['variables']
        self.assertEqual(values['fin'],1)
        self.assertEqual(values['portes finales'],0)
        active=Attempt(attack,1,.015);active.start(1,0,False)
        landed=evidence['trace'][-33]['time']
        for sample in evidence['trace']:active.sample(sample['time'],sample['position'],sample['velocity'],completed=sample['time']>=landed)
        last=evidence['trace'][-1]
        active.sample(last['time']+2,last['position'],[0,0,0],completed=True)
        self.assertIsNotNone(active.result)
        self.assertEqual(active.result.status,'not-achieved')
        self.assertIsNone(active.result.seconds)

    def test_real_initial_overshoot_remains_rejected(self):
        # Actual R2025a sample from b7f1493 / run 38239852904 / artifact
        # 11741872557. Keep the altitude ceiling; repair the witness instead.
        samples=[(5.216,[-1.2821024416431867e-16,2.263184313423007e-16,1.1744828454376302],[6.898282543315577e-16,6.500460122346386e-16,1.00107798645228]),
                 (38.112,[1.1028303338139693,-2.448587053625974e-15,1.1702111270140578],[-.0018354002108879374,1.2401019790947692e-16,.22102079124237933])]
        for time,position,velocity in samples:
            active=Attempt(generate(1),1,.015);active.start(1,0,False)
            active.sample(time,position,velocity)
            self.assertEqual(active.failure_reason,'altitude')
            self.assertEqual(active.result.status,'not-achieved')
            self.assertIsNone(active.result.seconds)

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
