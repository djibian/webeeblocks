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
  const scenarios = [
    {manual:false, kind:'arithmetic', code:'PROGRAM_INVALID'},
    {manual:true, kind:'arithmetic', code:'USER_STOPPED'},
    {manual:false, kind:'loop', code:'LOOP_ITERATION_LIMIT'},
    {manual:false, kind:'budget', code:'EXECUTION_BUDGET_LIMIT'}
  ];
  for (const [index, {manual, kind, code}] of scenarios.entries()) {
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
    const original = Object.fromEntries(['stopSimulation','resetSimulation','readRange','move','takeoff','land'].map(k=>[k,backend[k]]));
    const started = deferred(), release = deferred();
    let stops=0,resets=0,moves=0,takeoffs=0,lands=0,rangeValue,manualStop,nativeAck;
    const ranges=[];
    try {
      const block=(type,fields={})=>{
        const b=ws.newBlock(type);
        for(const [key,value] of Object.entries(fields))b.setFieldValue(String(value),key);
        return b;
      };
      const connect=(b,name,child)=>b.getInput(name).connection.connect(child.outputConnection);
      const t=block('webeeblocks_v2_takeoff'),m=block('webeeblocks_v2_move',{DIRECTION:'forward'}),l=block('webeeblocks_v2_land');
      connect(t,'HEIGHT',block('math_number',{NUM:.9}));
      const next=(a,b)=>a.nextConnection.connect(b.previousConnection);
      if(kind==='arithmetic'){
        const subtraction=block('math_arithmetic',{OP:'MINUS'});
        connect(subtraction,'A',block('math_number',{NUM:0}));
        connect(subtraction,'B',block('webeeblocks_v2_range',{DIRECTION:'front'}));
        connect(m,'DISTANCE',subtraction);
        next(t,m);next(m,l);
      } else {
        connect(m,'DISTANCE',block('math_number',{NUM:.20}));
        if(kind==='loop'){
          const loop=block('controls_whileUntil',{MODE:'WHILE',MAX_ITERATIONS:1});
          const condition=block('logic_compare',{OP:'GT'});
          connect(condition,'A',block('webeeblocks_v2_range',{DIRECTION:'front'}));
          connect(condition,'B',block('math_number',{NUM:.30}));
          connect(loop,'BOOL',condition);
          loop.getInput('DO').connection.connect(m.previousConnection);
          next(t,loop);next(loop,l);
        } else {
          // Exhaust the actual published 20,000-step budget without
          // changing the profile or issuing thousands of flight effects.
          // Repeat-only programs reach the dynamic budget guard.
          const variable=ws.getVariableMap().createVariable('compteur','').getId();
          const init=block('variables_set',{VAR:variable});
          connect(init,'VALUE',block('math_number',{NUM:0}));
          const change=block('math_change',{VAR:variable});
          connect(change,'DELTA',block('math_number',{NUM:1}));
          let nested=change;
          for(let depth=0;depth<3;depth++){
            const repeat=block('controls_repeat_ext');
            connect(repeat,'TIMES',block('math_number',{NUM:20}));
            repeat.getInput('DO').connection.connect(nested.previousConnection);
            nested=repeat;
          }
          next(init,t);next(t,m);next(m,nested);next(nested,l);
        }
      }
      Contract.preflightWorkspace(profile,ws);
      Contract.applyFieldBounds(profile,ws);
      const ast=Semantic.compileWorkspace(ws);
      Contract.preflightAst(profile,ast);
      let left;
      if(kind==='arithmetic'){
        assert.equal(ast.program[1].distance_m.kind,'arithmetic');
        assert.equal(ast.program[1].distance_m.op,'MINUS');
        assert.equal(ast.program[1].distance_m.right.kind,'range');
        left=ast.program[1].distance_m.left.value;
      } else if(kind==='loop'){
        assert.equal(ast.program[1].kind,'while');
        assert.equal(ast.program[1].max_iterations,1);
        assert.deepEqual(ast.program[1].body,[{kind:'move',direction:'forward',distance_m:.20}]);
        Interpreter.validateExecutionBudget(ast,profile.runtime.maxSteps);
      } else {
        assert.equal(profile.runtime.maxSteps,20000);
        assert.deepEqual(ast.program.map(node=>node.kind),['set_variable','takeoff','move','repeat','land']);
        let nested=ast.program[3];
        for(let depth=0;depth<3;depth++){
          assert.equal(nested.kind,'repeat');assert.equal(nested.count,20);
          assert.equal(nested.body.length,1);nested=nested.body[0];
        }
        assert.equal(nested.kind,'set_variable');assert.equal(nested.value.op,'ADD');
        assert.throws(()=>Interpreter.validateExecutionBudget(ast,profile.runtime.maxSteps),
          /reachable execution exceeds runtime budget/);
      }
      vm.createContext(context);
      vm.runInContext(fs.readFileSync('plugins/robot_windows/blockly_v2/main.js','utf8'),context);
      context.runtimeProfile=profile;context.workspace=ws;context.runtimeBackend=backend;
      context.updateRuntimeActions();
      backend.takeoff=async function(...args){takeoffs++;return original.takeoff.apply(this,args);};
      backend.move=async function(...args){const result=await original.move.apply(this,args);moves++;return result;};
      backend.land=async function(...args){lands++;return original.land.apply(this,args);};
      backend.resetSimulation=async function(...args){resets++;return original.resetSimulation.apply(this,args);};
      backend.stopSimulation=async function(...args){
        stops++;nativeAck=original.stopSimulation.apply(this,args);
        started.resolve();
        await nativeAck;
        await release.promise;
      };
      backend.readRange=async function(...args){
        rangeValue=await original.readRange.apply(this,args);
        ranges.push(rangeValue);
        assert(Number.isFinite(rangeValue));
        if(kind==='arithmetic')
          assert(rangeValue>left,'native observation must make the computed MOVE negative');
        else {
          assert.equal(kind,'loop');
          assert(rangeValue>.30,'native condition must remain true at the loop limit');
        }
        if(manual) manualStop=context.stopSimulation();
        return rangeValue;
      };
      const run=context.runProgram();
      await Promise.race([started.promise,run.then(()=>{throw Error('run ended before native STOP');})]);
      await until(()=>context.runtimeOutcomePending===true);
      const expectedMoves=kind==='arithmetic'?0:1;
      assert.equal(takeoffs,1);assert.equal(stops,1);assert.equal(moves,expectedMoves);assert.equal(lands,0);
      assert.equal(ranges.length,kind==='arithmetic'?1:kind==='loop'?2:0);
      assert.equal(element('submit').disabled,true);assert.equal(element('resetSimulation').disabled,true);
      await context.resetSimulation();await context.runProgram();
      assert.equal(resets,0);assert.equal(takeoffs,1);assert.equal(stops,1);
      await nativeAck; // real native ACK, not a synthesized reply
      await waitForForcedLanding(3+index); // independent native LAND ACK
      release.resolve();
      await run;
      if(manual)assert.equal(await manualStop,true);
      assert.equal(stops,1);assert.equal(moves,expectedMoves);assert.equal(lands,0);
      assert.equal(context.runtimeTerminal,true);assert.equal(context.runtimeSafetyUnknown,false);
      assert.equal(element('runtimeState').textContent,code==='PROGRAM_INVALID'?'À CORRIGER':'ARRÊTÉ');
      if(kind==='loop')assert.match(element('runtimeDetail').textContent,/limite de 1 itérations.*Réinitialisez/);
      if(kind==='budget')assert.match(element('runtimeDetail').textContent,/limite d’étapes.*Réinitialisez/);
      assert.equal(element('resetSimulation').disabled,false);
      assert.equal(diagnostics.length,1);
      assert.equal(diagnostics[0].machineCode,code);
      const bytes=context.serializedWorkspace();
      await context.resetSimulation();
      assert.equal(resets,1);assert.equal(element('runtimeState').textContent,'PRÊT');
      assert.equal(context.serializedWorkspace(),bytes);
      assert.equal(context.runtimeTerminal,false);
      await assert.rejects(backend.readActivityOutcome(profile.evaluation),{code:'OUTCOME_UNAVAILABLE'});
      if(kind==='arithmetic')
        console.log('A7_STUDENT_STOP_PASS '+JSON.stringify({manual,rangeValue,takeoffs,stops,moves,resets,
          code:diagnostics[0].machineCode,blockly:Blockly.VERSION,forcedLandings:3+index}));
      else
        console.log('A7_EXECUTION_LIMIT_STOP_PASS '+JSON.stringify({kind,ranges,takeoffs,stops,moves,lands,resets,
          code:diagnostics[0].machineCode,blockly:Blockly.VERSION,forcedLandings:3+index,maxSteps:profile.runtime.maxSteps}));
    } finally {
      release.resolve();
      for(const [key,value] of Object.entries(original))backend[key]=value;
      ws.dispose();
    }
  }
}
module.exports=proveStudentStop;
