'use strict';
const assert=require('assert');
const Witness=require('../grand_prix/reference_program_u.js');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const ast=Witness.build();
Interpreter.validateProgram(ast);
assert(Interpreter.validateExecutionBudget(ast,20000)<=20000);
const text=JSON.stringify(ast);
for(const term of ['seed','configuration','elapsed_time','score','candidate_points','gateCount'])assert(!text.includes('"'+term+'"'));
assert.strictEqual(JSON.stringify(Witness.build()),text);
const kinds=new Set();
(function walk(value){if(Array.isArray(value))value.forEach(walk);else if(value&&typeof value==='object'){if(value.kind)kinds.add(value.kind);Object.values(value).forEach(walk);}})(ast);
for(const kind of kinds)assert(['takeoff','vertical','move','turn','land','repeat','while','set_variable','variable_get','number','range','if','compare','arithmetic','logic'].includes(kind));
assert(text.includes('"name":"portes"'));
assert(ast.program[0].kind==='takeoff'&&ast.program.at(-1).kind==='land');
console.log('PASS ordinary bounded sensor/variable AST; no layout/oracle inputs');

async function proveFinalApproach() {
 // Native counterexample: #614, run 38899675445, s15, artifact 12045334965.
 // front=.847940396 and expanded side ranges select the terminal branch at
 // x=.8611102118861833. Descending there crosses z=.60 outside x<=.86.
 // This scripted sensor/control test checks the ordinary AST's ordering; the
 // unchanged native oracle/suite must still prove the complete trajectory.
 for (const initial of [.847940396, .849, .78, .70, .62]) {
  let side=0,front=initial,altitude=0,descents=0,landed=false;
  const backend={
   capabilities:{conditionalLoops:true},
   async takeoff(height){altitude=height;},
   async turn(){side+=1;},
   async readRange(direction){
    if(side<2)return direction==='front'?.15:.48;
    if(direction==='front')return front;
    return direction==='left'?.882480556:.877638915;
   },
   async move(direction,distance){
    assert.strictEqual(side,2);
    assert.strictEqual(altitude,.8,'terminal positioning must precede descent');
    assert(['forward','back'].includes(direction));
    front+=direction==='forward'?-distance:distance;
   },
   async vertical(direction,distance){
    if(direction==='down') {
     descents+=1;
     assert(front>=.63&&front<=.73,
      'descent before safe terminal approach: front='+front);
    }
    altitude+=direction==='up'?distance:-distance;
   },
   async land(){landed=true;}
  };
  await Interpreter.run(ast,backend,{maxSteps:20000});
  assert(landed&&descents===1);
 }
 console.log('PASS terminal sensor approach stays high before bounded descent');
}
proveFinalApproach().catch(error=>{console.error(error);process.exitCode=1;});
