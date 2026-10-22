'use strict';
const assert=require('assert');
const Demo=require('../blockly/guarded_move_demo');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
const I=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const C=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const S=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const O=require('../../plugins/robot_windows/blockly/webeeblocks/execution_observer');
const P=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Physical=require('../../plugins/robot_windows/blockly/webeeblocks/physical_capability_contract');
const Wwi=require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend');
const position={id:'p',name:'position'},number=value=>({kind:'number',value});
function node(extra={}){return Object.assign({kind:'guarded_move',max_distance_m:.4,threshold_m:.35,progress:position,on_sensor:[]},extra);}
function program(g=node(),initial=0){return{version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.8},{kind:'set_variable',variable:position,value:number(initial)},g,{kind:'land'}]};}
function fake(samples){let epoch=1;const effects=[];return{effects,capabilities:{guardedMove:true,actions:['takeoff','move','vertical','land'],rangeDirections:['front'],moveDirections:['forward']},getMotionEpoch:()=>String(epoch),rotate:()=>epoch++,takeoff:async()=>effects.push('takeoff'),vertical:async()=>effects.push('vertical'),land:async()=>effects.push('land'),move:async(d,n)=>{effects.push(['move',d,n]);return null;},readRange:async()=>{effects.push('range');return samples.length?samples.shift():2;}};}
async function prove(){
 // Real Blockly, project validation, source map and exact serialised identities.
 for(const crossing of [false,true]){
  const d=Demo.build(crossing),map=O.buildSourceMap(d.workspace),reopen=new Blockly.Workspace();
  const options={Blockly,profiles:Profiles,activitiesDocument:d.document,blockCatalog:Activities.BLOCK_CATALOG,semanticAst:S,activityContract:C};
  const loaded=P.validateProjectText(JSON.stringify(d.project),d.profile,options);assert.deepStrictEqual(loaded.ast,d.ast);
  const fixture=require('fs').readFileSync('tools/blockly/guarded_'+(crossing?'single_h':'approach')+'_demo.wbb','utf8');assert.deepStrictEqual(P.validateProjectText(fixture,d.profile,options).ast,d.ast);
  Blockly.serialization.workspaces.load(loaded.project.workspace,reopen);assert.deepStrictEqual(S.compileWorkspace(reopen),d.ast);assert.deepStrictEqual(O.buildSourceMap(reopen),map);
  assert.strictEqual(d.blocks,crossing?15:7);
  assert.throws(()=>C.preflightWorkspace(Activities.getProfile('reactive-obstacle-v2'),d.workspace),/block forbidden/);
  const b=d.workspace.getAllBlocks(false).find(b=>b.type==='webeeblocks_v2_guarded_move'),read=b.getFieldValue.bind(b);
  b.getFieldValue=k=>k==='DISTANCE'?.15:read(k);assert.throws(()=>S.compileStatement(b),/multiple of 0.1/);b.getFieldValue=read;
  const facts=C.preflightAst(d.profile,d.ast);assert(facts.ranges.has('front')&&facts.moveDirections.has('forward')&&facts.statements.has('move'));
  for(const key of ['guardedMove','actions','rangeDirections','moveDirections']){const back=fake([]);delete back.capabilities[key];assert.throws(()=>C.preflightBackend(d.profile,facts,back),/unavailable/);}
  const tight=structuredClone(d.profile);tight.runtime.astBounds['guarded_move.max_distance_m'].max=.3;assert.throws(()=>C.preflightAst(tight,d.ast),/outside profile bounds/);
  const tinyMove=structuredClone(d.profile);tinyMove.runtime.astBounds['move.distance_m'].min=.2;assert.throws(()=>C.preflightAst(tinyMove,d.ast),/outside profile bounds/);
  const guardedPaths=[];const back=fake([2,2,.3,2,.3]);
  if(!crossing){const obs=O.create(d.workspace,{onPause:x=>{guardedPaths.push(x);queueMicrotask(()=>obs.next());}});await I.run(d.ast,back,{hooks:obs.begin(true)});obs.finish();assert(guardedPaths.filter(x=>x.node.kind==='guarded_move').every(x=>x.blockId===map[x.path.join('/')]));assert(guardedPaths.some(x=>x.phase==='range')&&guardedPaths.some(x=>x.phase==='move'));}
  reopen.dispose();d.workspace.dispose();
 }
 // Every parameter and all-path preflight must reject before TAKEOFF.
 for(const field of ['max_distance_m','threshold_m'])for(const bad of [NaN,Infinity,-1,0,'0.4',null]){
  const b=fake([]);await assert.rejects(()=>I.run(program(node({[field]:bad})),b));assert.deepStrictEqual(b.effects,[]);
 }
 for(const max of [.15,2.1])assert.throws(()=>I.validateProgram(program(node({max_distance_m:max}))),/guarded maximum/);
 for(const t of [.249,1.501])assert.throws(()=>I.validateProgram(program(node({threshold_m:t}))),/threshold/);
 const invalidNested=program(node({on_sensor:[{kind:'land'}]}));assert.throws(()=>I.validateProgram(invalidNested),/top-level/);
 const unassigned=program();unassigned.program.splice(1,1);assert.throws(()=>I.validateProgram(unassigned),/before assignment/);
 const branchVar={id:'x',name:'x'},noDefinite=program(node({on_sensor:[{kind:'set_variable',variable:branchVar,value:number(1)}]}));noDefinite.program.splice(-1,0,{kind:'set_variable',variable:position,value:{kind:'variable_get',variable:branchVar}});assert.throws(()=>I.validateProgram(noDefinite),/before assignment/);
 for(const key of ['guardedMove','actions','rangeDirections','moveDirections']){const b=fake([]);delete b.capabilities[key];await assert.rejects(()=>I.run(program(),b),/unavailable/);assert.deepStrictEqual(b.effects,[]);}
 for(const key of ['readRange','move','getMotionEpoch']){const b=fake([]);delete b[key];await assert.rejects(()=>I.run(program(),b),/missing/);assert.deepStrictEqual(b.effects,[]);}
 assert.throws(()=>Physical.deriveFacts(program()),/unsupported AST statement kind: guarded_move/);
 const physicalProgram=program({kind:'if',condition:number(0),then:[node()],else:[]});assert.throws(()=>Physical.deriveFacts(physicalProgram),/guarded_move/);
 // Sensor termination (including equality), distance termination and priority.
 const flag={id:'flag',name:'flag'},stopNode=node({on_sensor:[{kind:'set_variable',variable:flag,value:number(1)}]});
 for(const sample of [0,.35]){const b=fake([sample]);const r=await I.run(program(stopNode),b);assert.strictEqual(r.variables.position,0);assert.strictEqual(r.variables.flag,1);assert(!b.effects.some(Array.isArray));}
 const maxBack=fake(Array(5).fill(2));const max=await I.run(program(stopNode),maxBack);assert.strictEqual(max.variables.position,.4);assert(!('flag'in max.variables));assert.strictEqual(maxBack.effects.filter(Array.isArray).length,4);assert.strictEqual(maxBack.effects.filter(x=>x==='range').length,5);
 const both=fake([2,2,2,2,.35]);const rBoth=await I.run(program(stopNode),both);assert.strictEqual(rBoth.variables.flag,1);assert.strictEqual(rBoth.variables.position,.4);
 for(const samples of [[2,.3],[2,2,.3],[2,2,2,.3]]){const expected=(samples.length-1)*.1,b=fake(samples),r=await I.run(program(),b);assert(Math.abs(r.variables.position-expected)<1e-12);assert(b.effects.filter(Array.isArray).every(x=>x[2]===.1));}
 // Deliberately constant returns demonstrate the COMMAND limit, not odometry.
 const stuck=fake([.8,.8,.8,.8,.8]);const commanded=await I.run(program(),stuck);assert.strictEqual(commanded.variables.position,.4);
 for(const bad of [NaN,Infinity,-1,2.002,null,undefined,'0.8']){const b=fake([bad]);await assert.rejects(()=>I.run(program(),b),/range/);assert.deepStrictEqual(b.effects,['takeoff','range']);}
 const saturated=fake(Array(5).fill(2.001));assert.strictEqual((await I.run(program(),saturated)).variables.position,.4);
 for(const ack of [undefined,true,'OK',.1,{}]){const b=fake([2]);b.move=async()=>{b.effects.push('sent');return ack;};const vars=[];await assert.rejects(()=>I.run(program(),b,{hooks:{onVariables:x=>vars.push(x.values.position)}}),/unambiguous/);assert.deepStrictEqual(vars,[0]);assert.deepStrictEqual(b.effects,['takeoff','range','sent']);}
 for(const code of ['UNSAFE_OR_TIMEOUT','USER_STOPPED','TIME_LIMIT','RESET_CANCELLED']){const b=fake([2]);b.move=async()=>{b.effects.push('sent');throw Object.assign(Error(code),{code});};await assert.rejects(()=>I.run(program(),b),e=>e.code===code);assert.deepStrictEqual(b.effects,['takeoff','range','sent']);}
 for(const after of ['range','move']){const b=fake([2]);const original=b[after==='range'?'readRange':'move'];b[after==='range'?'readRange':'move']=async(...a)=>{const r=await original(...a);b.rotate();return r;};await assert.rejects(()=>I.run(program(),b),/epoch changed/);assert(!b.effects.includes('land'));assert(b.effects.filter(Array.isArray).length<2);}
 for(const phase of ['range','move']){const signal=new AbortController(),b=fake([2]);await assert.rejects(()=>I.run(program(),b,{signal:signal.signal,hooks:{beforeStep:x=>{if(x.phase===phase)signal.abort();}}}),e=>e.code==='USER_STOPPED');assert(!b.effects.some(Array.isArray));assert(!b.effects.includes('land'));}
 const cancelled=new AbortController();cancelled.abort();const never=fake([]);await assert.rejects(()=>I.run(program(),never,{signal:cancelled.signal}),e=>e.code==='USER_STOPPED');assert.deepStrictEqual(never.effects,[]);
 const cost=I.validateExecutionBudget(program(),1000),budgetBack=fake([]);await assert.rejects(()=>I.run(program(),budgetBack,{maxSteps:cost-1}),/before takeoff/);assert.deepStrictEqual(budgetBack.effects,[]);assert.strictEqual((await I.run(program(),fake([]),{maxSteps:cost})).remainingBudget,0);
 const overflow=fake([2]);await assert.rejects(()=>I.run(program(node(),1e308),overflow),/cannot advance/);assert(!overflow.effects.some(Array.isArray));
 // Ordinary crossing moves are counted only by the pupil's explicit updates.
 const composed=program(node({max_distance_m:.2}));composed.program.splice(-1,0,{kind:'move',direction:'forward',distance_m:.3},{kind:'set_variable',variable:position,value:{kind:'arithmetic',op:'ADD',left:{kind:'variable_get',variable:position},right:number(.3)}});assert.strictEqual((await I.run(composed,fake([]))).variables.position,.5);
 // Production WWI: wrong response type fails; a delayed MOVE ACK after RESET
 // cannot update progression or send another movement.
 const sent=[],wwi=new Wwi({send:m=>sent.push(m)},{timeoutMs:100});wwi.ready=true;let completed=false;
 const running=I.run(program(),wwi,{hooks:{onVariables:x=>{if(x.values.position)completed=true;}}});
 async function response(payload){await new Promise(r=>setImmediate(r));const id=Number(sent.at(-1).match(/REQUEST (\d+)/)[1]);wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+id+' '+payload);}
 await response('OK');await response('VALUE 2');await response('VALUE 0.1');await assert.rejects(()=>running,/unambiguous/);assert.strictEqual(completed,false);
 // A real RESET rejects the pending MOVE; late ACK cannot resurrect it.
 const resetSent=[],resetBackend=new Wwi({send:m=>resetSent.push(m)},{timeoutMs:200,simulationReset:true});resetBackend.ready=true;
 const afterReset=[];const resetRun=I.run(program(),resetBackend,{hooks:{onVariables:x=>afterReset.push(x.values.position)}});
 const resetRejection=assert.rejects(()=>resetRun,e=>e.code==='RESET_CANCELLED');
 async function replyReset(payload){await new Promise(r=>setImmediate(r));const id=Number(resetSent.at(-1).match(/REQUEST (\d+)/)[1]);resetBackend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+id+' '+payload);}
 await replyReset('OK');await replyReset('VALUE 2');await new Promise(r=>setImmediate(r));
 const moveId=Number(resetSent.at(-1).match(/REQUEST (\d+)/)[1]);assert(resetSent.at(-1).includes(' MOVE '));
 const resetting=resetBackend.resetSimulation();await resetRejection;
 resetBackend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+moveId+' OK');await replyReset('OK');await resetting;
 assert.deepStrictEqual(afterReset,[0]);assert.strictEqual(resetSent.filter(x=>x.includes(' MOVE ')).length,1);assert(!resetSent.some(x=>x.endsWith(' LAND')));
 // Cancellation during an acknowledged action preserves its commanded amount,
 // then fails without executing another read/move or the normal LAND.
 const abort=new AbortController(),pending=fake([2]),amounts=[];
 pending.move=async()=>{pending.effects.push('sent');abort.abort();return null;};
 await assert.rejects(()=>I.run(program(),pending,{signal:abort.signal,hooks:{onVariables:x=>amounts.push(x.values.position)}}),e=>e.code==='USER_STOPPED');
 assert.deepStrictEqual(amounts,[0,.1]);assert.deepStrictEqual(pending.effects,['takeoff','range','sent']);
 // A capability hidden in the conditional sensor body is still preflighted.
 const unreachable=program(node({on_sensor:[{kind:'set_variable',variable:position,value:{kind:'elapsed_time',unit:'s'}}]})),noClock=fake([2]);
 await assert.rejects(()=>I.run(unreachable,noClock),/elapsed simulation time/);assert.deepStrictEqual(noClock.effects,[]);
 console.log('PASS guarded movement: real Blockly/.wbb/source map, bounds, all-path capabilities/budget, discrete range/ACK sequencing, cancellation/epoch, errors, no false completion or odometry, physical refusal and explicit crossing accounting');
}
module.exports=prove;if(require.main===module)prove().catch(e=>{console.error(e);process.exitCode=1;});
