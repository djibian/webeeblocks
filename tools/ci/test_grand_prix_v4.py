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
    if attempt.result is None:
        last=data['trace'][-1]
        for tick in range(1,65):
            attempt.sample(round(last['time']+tick*.032,3),last['position'],[0,0,0],completed=True)
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

    def test_all_33_shapes_and_endpoint_shortfall(self):
        representatives={}
        for seed in range(65536):
            layout=generate(seed,'gp-v4')
            representatives.setdefault((layout.gates,layout.final_gates),seed)
        self.assertEqual(len(representatives),33)
        for seed in representatives.values():
            for laps in (1,2):
                l=generate(seed,'gp-v4');p=evidence(l,laps)
                self.assertEqual(p.returncode,0,(seed,laps,p.stderr))
                a=judge(l,json.loads(p.stdout))
                self.assertEqual(a.result.status,'achieved',(seed,laps,a.failure_reason))
        for seed in (0,1,4,5):
            for laps in (1,2):
                l=generate(seed,'gp-v4');p=evidence(l,laps,moveEndpointShortfall=.015)
                self.assertEqual(p.returncode,0,(seed,laps,p.stderr))
                a=judge(l,json.loads(p.stdout))
                self.assertEqual(a.result.status,'achieved',(seed,laps,a.failure_reason))

    def test_saturation_never_certifies_terminal(self):
        for seed in (0,1,4):
            p=evidence(generate(seed,'gp-v4'),injectRangeLossBoth=True)
            self.assertNotEqual(p.returncode,0)
            failure=json.loads(p.stderr.split('WITNESS_FAILURE ',1)[1]);self.assertEqual(failure['lands'],0)

    def test_unexpected_closed_gate_stops_and_has_no_score(self):
        from tools.grand_prix.layout import Box
        for seed in (0,1,4,5):
            l=generate(seed,'gp-v4');g=l.gates[0]
            horizontal=abs(__import__('math').cos(g.heading))>.5
            closed=Box(g.x,g.y,.65,.04 if horizontal else .56,.56 if horizontal else .04,1.3)
            l=dataclasses.replace(l,boxes=(*l.boxes,closed))
            p=evidence(l);self.assertNotEqual(p.returncode,0)
            failure=json.loads(p.stderr.split('WITNESS_FAILURE ',1)[1]);self.assertEqual(failure['lands'],0)
            # The witness fails before another translation crosses the obstacle.
            self.assertGreater(__import__('math').dist(failure['last_position'][:2],(g.x,g.y)),.09)

    def test_blind_terminal_counterexample_needs_multiple_lengths(self):
        for seed,expected in ((4,'achieved'),(1,'not-achieved'),(0,'not-achieved')):
            l=generate(seed,'gp-v4');p=evidence(l,fixedFinalSteps=19)
            self.assertEqual(p.returncode,0,p.stderr)
            a=judge(l,json.loads(p.stdout));self.assertEqual(a.result.status,expected)
            if expected=='not-achieved':self.assertIsNone(a.result.candidate_points)

    def test_native_lateral_refutation_changes_first_effect(self):
        script="""
const fs=require('fs'),assert=require('assert'),W=require('./tools/grand_prix/reference_program_v4'),I=require('./plugins/robot_windows/blockly/webeeblocks/interpreter');
const f=JSON.parse(fs.readFileSync('tools/ci/fixtures/grand_prix_v4_lateral_60efa67.json','utf8'));
(async()=>{for(const old of [false,true]){
const ast=W.build(true,1),phase=ast.program[ast.program.length-2];
if(old){const guard=phase.body[0].then[3].else[0].else[0];guard.condition={kind:'logic',op:'OR',left:{kind:'compare',op:'LT',left:{kind:'variable_get',variable:{id:'gp-gauche',name:'gauche'}},right:{kind:'number',value:.3}},right:{kind:'compare',op:'LT',left:{kind:'variable_get',variable:{id:'gp-droite',name:'droite'}},right:{kind:'number',value:.3}}};}
ast.program=[{kind:'takeoff',height_m:.4},...ast.program.filter(n=>n.kind==='set_variable'),...phase.body,{kind:'land'}];
let effect;const backend={capabilities:{conditionalLoops:true},takeoff:async()=>{},readRange:async d=>f.ranges[d],move:async(d,n)=>{effect=[d,n];throw new Error('captured-first-effect');}};
await assert.rejects(I.run(ast,backend,{maxSteps:20000}),/captured-first-effect/);
assert.deepStrictEqual(effect,old?['forward',.2]:['left',.1]);
}})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        subprocess.run(['node','-e',script],cwd=ROOT,check=True)

    def test_count_policy_same_ast_changes_exit_and_count_ablation(self):
        for seed in (1,16):
            l=generate(seed,'gp-v4');p=evidence(l,2,memoryChoice=True)
            self.assertEqual(p.returncode,0,p.stderr)
            data=json.loads(p.stdout);a=judge(l,data)
            self.assertEqual(a.result.status,'achieved',a.failure_reason)
            self.assertEqual(a.result.laps,1 if len(l.gates)>=3 else 2)
        l=generate(1,'gp-v4');p=evidence(l,2,memoryChoice=True,forgetCounts=True)
        self.assertEqual(p.returncode,0,p.stderr)
        a=judge(l,json.loads(p.stdout));self.assertEqual(a.result.laps,2)

    def test_time_policy_real_ast_and_public_rules(self):
        for seed in (0,1,4):
            layout=generate(seed,'gp-v4')
            self.assertIn('"gp-v4" "540" ]',world_text(layout,540))
            for threshold in (180,540):
                process=evidence(layout,2,strategyTime=threshold,finalEstimate=90)
                self.assertEqual(process.returncode,0,process.stderr)
                data=json.loads(process.stdout);attempt=judge(layout,data,threshold)
                self.assertEqual(attempt.result.status,'achieved',attempt.failure_reason)
                self.assertGreater(data['result']['variables']['temps observé'],0)
        process=evidence(generate(1,'gp-v4'),2,strategyTime=180,disableClock=True)
        self.assertNotEqual(process.returncode,0)
        failure=json.loads(process.stderr.split('WITNESS_FAILURE ',1)[1])
        self.assertEqual(failure['lands'],0)
        self.assertEqual(failure['last_position'],[0,0,.015])
        for invalid in (True,0,601,180.5):
            with self.assertRaises(ValueError):world_text(generate(1,'gp-v4'),invalid)

    def test_generic_profile_preflight_budget(self):
        script="""
const W=require('./tools/grand_prix/reference_program_v4'),I=require('./plugins/robot_windows/blockly/webeeblocks/interpreter'),C=require('./plugins/robot_windows/blockly/webeeblocks/activity_contract'),A=require('./plugins/robot_windows/blockly/webeeblocks/activities'),B=require('./plugins/robot_windows/blockly/webeeblocks/wwi_backend'),vm=require('vm'),fs=require('fs');
const c={WebeeBlocksActivities:A,Blockly:{inject(){}},WebeeBlocksWwiBackend:B};c.window=c;
vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix/setup.js','utf8'),c);
for(const [laps,memory] of [[1,false],[2,false],[2,true]]){const ast=W.build(true,laps,true,memory),facts=C.preflightAst(c.WebeeBlocksActivities.getProfile('progression-grand-prix-v1'),ast);C.preflightBackend(c.WebeeBlocksActivities.getProfile('progression-grand-prix-v1'),facts,new B({send(){}},{}));I.validateExecutionBudget(ast,20000);}
const policy=require('./tools/grand_prix/reference_policy_time'),timed=policy.build(W,540,90),profile=c.WebeeBlocksActivities.getProfile('progression-grand-prix-v1');
const facts=C.preflightAst(profile,timed);C.preflightBackend(profile,facts,new B({send(){}},{}));I.validateExecutionBudget(timed,20000);
"""
        subprocess.run(['node','-e',script],cwd=ROOT,check=True)

if __name__=='__main__':unittest.main()
