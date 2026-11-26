'use strict';
// Qualification-only: genuine Blockly/contract/interpreter and production UI
// state machine, using a headless DOM adapter and the live R2025a WWI backend.
// The ACK gate delays delivery to the UI only; never alters native execution.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {setTimeout: delay} = require('node:timers/promises');
const {school} = require('../grand_prix/witness_workspace_a7');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome');

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return {promise, resolve};
}
async function until(predicate) {
  const limit = Date.now() + 35000;
  while (!predicate()) {
    assert(Date.now() < limit, 'student-error UI did not settle');
    await delay(10);
  }
}
async function proveStudentStop(backend, waitForForcedLanding) {
  const {profile, options} = school();
  const Blockly = options.Blockly;
  assert.equal(Blockly.VERSION, '13.2.1');
  const Contract = options.activityContract, Semantic = options.semanticAst;
  for (const [index, manual] of [false, true].entries()) {
    const ws = new Blockly.Workspace();
    const el = new Map(), diagnostics = [];
    const element = id => {
      if (!el.has(id)) el.set(id, {checked:false,disabled:false,hidden:false,
        textContent:'',setAttribute(){},addEventListener(){}});
      return el.get(id);
    };
    const context = {Blockly, console, URL, setTimeout, clearTimeout, Promise,
      document:{currentScript:{src:'https://example.invalid/main.js'},
        body:{dataset:{}},getElementById:element},
      window:{dispatchEvent(e){if(e.type==='webeeblocks-runtime-v2-diagnostic')diagnostics.push(e.detail);},
        addEventListener(){}},
      CustomEvent:function(type,init){this.type=type;this.detail=init&&init.detail;},
      WebeeBlocksRuntimeOutcome:Outcome,WebeeBlocksActivityContract:Contract,
      WebeeBlocksSemanticAst:Semantic,WebeeBlocksInterpreter:Interpreter};
    const original = Object.fromEntries(['stopSimulation','resetSimulation','readRange','move','takeoff'].map(k=>[k,backend[k]]));
    const started = deferred(), release = deferred();
    let stops=0,resets=0,moves=0,takeoffs=0,rangeValue,manualStop,nativeAck;
    try {
      const block=(type,fields={})=>{
        const b=ws.newBlock(type);
        for(const [key,value] of Object.entries(fields))b.setFieldValue(String(value),key);
        return b;
      };
      const connect=(b,name,child)=>b.getInput(name).connection.connect(child.outputConnection);
      const t=block('webeeblocks_v2_takeoff'),m=block('webeeblocks_v2_move',{DIRECTION:'forward'}),l=block('webeeblocks_v2_land');
      connect(t,'HEIGHT',block('math_number',{NUM:.9}));
      const subtraction=block('math_arithmetic',{OP:'MINUS'});
      connect(subtraction,'A',block('math_number',{NUM:0}));
      connect(subtraction,'B',block('webeeblocks_v2_range',{DIRECTION:'front'}));
      connect(m,'DISTANCE',subtraction);
      t.nextConnection.connect(m.previousConnection);m.nextConnection.connect(l.previousConnection);
      Contract.preflightWorkspace(profile,ws);
      Contract.applyFieldBounds(profile,ws);
      const ast=Semantic.compileWorkspace(ws);
      Contract.preflightAst(profile,ast);
      assert.equal(ast.program[1].distance_m.kind,'arithmetic');
      assert.equal(ast.program[1].distance_m.op,'MINUS');
      assert.equal(ast.program[1].distance_m.right.kind,'range');
      const left=ast.program[1].distance_m.left.value;
      vm.createContext(context);
      vm.runInContext(fs.readFileSync('plugins/robot_windows/blockly_v2/main.js','utf8'),context);
      context.runtimeProfile=profile;context.workspace=ws;context.runtimeBackend=backend;
      context.updateRuntimeActions();
      backend.takeoff=async function(...args){takeoffs++;return original.takeoff.apply(this,args);};
      backend.move=async function(...args){moves++;return original.move.apply(this,args);};
      backend.resetSimulation=async function(...args){resets++;return original.resetSimulation.apply(this,args);};
      backend.stopSimulation=async function(...args){
        stops++;nativeAck=original.stopSimulation.apply(this,args);
        started.resolve();
        await nativeAck;
        await release.promise;
      };
      backend.readRange=async function(...args){
        rangeValue=await original.readRange.apply(this,args);
        assert(Number.isFinite(rangeValue)&&rangeValue>left,'native observation must make the computed MOVE negative');
        if(manual) manualStop=context.stopSimulation();
        return rangeValue;
      };
      const run=context.runProgram();
      await Promise.race([started.promise,run.then(()=>{throw Error('run ended before native STOP');})]);
      await until(()=>context.runtimeOutcomePending===true);
      assert.equal(takeoffs,1);assert.equal(stops,1);assert.equal(moves,0);
      assert.equal(element('submit').disabled,true);assert.equal(element('resetSimulation').disabled,true);
      await context.resetSimulation();await context.runProgram();
      assert.equal(resets,0);assert.equal(takeoffs,1);assert.equal(stops,1);
      await nativeAck; // real native ACK, not a synthesized reply
      await waitForForcedLanding(3+index); // independent native LAND ACK
      release.resolve();
      await run;
      if(manual)assert.equal(await manualStop,true);
      assert.equal(stops,1);assert.equal(moves,0);
      assert.equal(context.runtimeTerminal,true);assert.equal(context.runtimeSafetyUnknown,false);
      assert.equal(element('runtimeState').textContent,manual?'ARRÊTÉ':'À CORRIGER');
      assert.equal(element('resetSimulation').disabled,false);
      assert.equal(diagnostics.length,1);
      assert.equal(diagnostics[0].machineCode,manual?'USER_STOPPED':'PROGRAM_INVALID');
      const bytes=context.serializedWorkspace();
      await context.resetSimulation();
      assert.equal(resets,1);assert.equal(element('runtimeState').textContent,'PRÊT');
      assert.equal(context.serializedWorkspace(),bytes);
      assert.equal(context.runtimeTerminal,false);
      await assert.rejects(backend.readActivityOutcome(profile.evaluation),{code:'OUTCOME_UNAVAILABLE'});
      console.log('A7_STUDENT_STOP_PASS '+JSON.stringify({manual,rangeValue,takeoffs,stops,moves,resets,
        code:diagnostics[0].machineCode,blockly:Blockly.VERSION,forcedLandings:3+index}));
    } finally {
      release.resolve();
      for(const [key,value] of Object.entries(original))backend[key]=value;
      ws.dispose();
    }
  }
}
module.exports=proveStudentStop;
