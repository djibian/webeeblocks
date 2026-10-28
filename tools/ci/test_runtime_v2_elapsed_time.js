'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.resolve(__dirname,'../..');
const Blockly=require(root+'/plugins/robot_windows/blockly_v2/node_modules/blockly');
require(root+'/plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
const Compiler=require(root+'/plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const Interpreter=require(root+'/plugins/robot_windows/blockly/webeeblocks/interpreter');
const Contract=require(root+'/plugins/robot_windows/blockly/webeeblocks/activity_contract');
const Physical=require(root+'/plugins/robot_windows/blockly/webeeblocks/physical_capability_contract');
const Backend=require(root+'/plugins/robot_windows/blockly/webeeblocks/wwi_backend');
const Profiles=require(root+'/plugins/robot_windows/blockly/webeeblocks/activities');
const expression={kind:'elapsed_time',unit:'s'},variable={id:'time',name:'durée'};
const ast={version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.5},{kind:'set_variable',variable,value:expression},{kind:'land'}]};
async function prove(){
  vm.runInNewContext(fs.readFileSync(root+'/plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js','utf8'),{Blockly:{defineBlocksWithJsonArray:definitions=>Blockly.defineBlocksWithJsonArray(definitions.filter(x=>x.type==='webeeblocks_v2_elapsed'))}});
  const ws=new Blockly.Workspace(),time=ws.newBlock('webeeblocks_v2_elapsed');
  assert.deepStrictEqual(Compiler.compileExpression(time),expression);
  const copy=new Blockly.Workspace();Blockly.serialization.workspaces.load(Blockly.serialization.workspaces.save(ws),copy);
  assert.deepStrictEqual(Compiler.compileExpression(copy.getTopBlocks(true)[0]),expression);
  copy.dispose();ws.dispose();
  // Existing intermediate activities neither expose nor admit this new expression.
  for(const p of Profiles.DOCUMENT.activities.filter(x=>x.id.startsWith('progression-'))){
    assert(!p.toolbox.includes('webeeblocks_v2_elapsed'));
    assert.throws(()=>Contract.preflightAst(p,ast),/elapsed simulation time unavailable in profile/);
  }
  const facts=Contract.collectAst(ast);assert(facts.elapsedTime);
  assert.throws(()=>Contract.preflightBackend({},facts,{capabilities:{}}),/unavailable on backend/);
  assert.throws(()=>Physical.deriveFacts(ast),/unsupported AST expression kind: elapsed_time/);
  let effects=[];const b={capabilities:{elapsedSimulationTime:true},takeoff:async()=>effects.push('T'),land:async()=>effects.push('L'),readElapsedTime:async()=>3.125};
  assert.equal((await Interpreter.run(ast,b)).variables['durée'],3.125);
  assert.deepStrictEqual(effects,['T','L']);
  for(const value of [null,undefined,'3',NaN,Infinity,-.1]){
    effects=[];await assert.rejects(()=>Interpreter.run(ast,{...b,readElapsedTime:async()=>value}),/finite nonnegative/);
    assert.deepStrictEqual(effects,['T']);
  }
  effects=[];const unreachable={...ast,program:[ast.program[0],{kind:'if',condition:{kind:'number',value:0},then:[ast.program[1]],else:[]},ast.program[2]]};
  await assert.rejects(()=>Interpreter.run(unreachable,{...b,capabilities:{}}),/unavailable on this backend/);
  assert.deepStrictEqual(effects,[]);
  assert.throws(()=>Interpreter.validateProgram({...ast,program:[ast.program[0],{...ast.program[1],value:{...expression,unit:'ms'}},ast.program[2]]}),/unsupported elapsed time unit/);
  const messages=[],wwi=new Backend({send:m=>messages.push(m)},{simulationReset:true,simulationStop:true,timeoutMs:100});
  const read=wwi.readElapsedTime();assert(messages[0].endsWith('1 ELAPSED'));
  wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 VALUE 3.125');assert.equal(await read,3.125);
  const old=wwi.readElapsedTime();const cancelled=assert.rejects(old,e=>e.code==='RESET_CANCELLED');
  const reset=wwi.resetSimulation();await cancelled;
  wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 VALUE 999');
  wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK');await reset;
  const fresh=wwi.readElapsedTime();wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 VALUE 999');
  wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 VALUE 1');assert.equal(await fresh,1);
  const bad=wwi.readElapsedTime();wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 5 OK');await assert.rejects(bad,/invalid elapsed time/);
  const late=wwi.readElapsedTime();const lateRejected=assert.rejects(late,e=>e.code==='TIME_UNAVAILABLE');
  const stop=wwi.stopSimulation();wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 7 OK');await stop;
  wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 6 VALUE 50');await lateRejected;
  await assert.rejects(()=>wwi.readElapsedTime(),e=>e.code==='USER_STOPPED');
  console.log('PASS elapsed simulation time: real Blockly, serialization, profile opt-in, all-path capability preflight, invalid observations, stale reset replies and physical refusal');
}
module.exports=prove;
if(require.main===module)prove().catch(e=>{console.error(e);process.exitCode=1;});
