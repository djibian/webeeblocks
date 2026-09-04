'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const Observer = require('../../plugins/robot_windows/blockly/webeeblocks/execution_observer.js');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const ActivityContract = require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract.js');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');

const mainSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');
const controllerSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'), 'utf8');
const projectUiSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
const classroomFixesSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/classroom_fixes.css'), 'utf8');
assert.match(mainSource, /getElementById\('stepContinue'\)\.disabled = !paused;/);
assert.doesNotMatch(mainSource, /getElementById\('stepContinue'\)\.disabled = !runtimeRunning;/);
assert.match(classroomFixesSource, /body\[data-runtime-state="À CORRIGER"\] #runtimeState/);
assert.match(projectUiSource, /setRuntimeLocked\(state === 'EN VOL' \|\| state === 'RÉINITIALISATION'\);/);
assert.match(projectUiSource, /blocklyDiv\.inert = runtimeLocked;/);
assert.match(projectUiSource, /if \(open\) open\.disabled = locked;/);
assert.match(projectUiSource, /if \(busy \|\| !supported \|\| runtimeLocked\) return null;/);
assert.match(mainSource, /getElementById\('stopSimulation'\)/);
assert.match(mainSource, /await runtimeBackend\.stopSimulation\(\)/);
assert.match(controllerSource, /request\.kind == REQUEST_STOP/);
assert.match(controllerSource, /response_error\(active_id, "USER_STOPPED"\)/);
assert.match(controllerSource, /target_x = x;[\s\S]*target_y = y;[\s\S]*target_z = z;[\s\S]*failsafe_latched = 1;/);
assert.doesNotMatch(controllerSource, /command == CMD_IDLE \|\| command == CMD_RESET/);
assert.match(controllerSource, /if \(active_id >= 1\)[\s\S]*response_error\(active_id, "USER_STOPPED"\)/);
assert.match(mainSource, /runtimeStopRequested = true;/);
assert.match(mainSource, /runtimeDebug\.continueRun\(\)/);
assert.match(mainSource, /if \(runtimeStopRequested\) throw userStoppedError\(\);/);

function block(id,type,inputs){return{id,type,_next:null,_inputs:inputs||{},getNextBlock(){return this._next;},getInputTargetBlock(name){return this._inputs[name]||null;}};}
function link(){var blocks=Array.from(arguments);for(var i=0;i<blocks.length-1;i++)blocks[i]._next=blocks[i+1];return blocks[0];}
function ast(){return{version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:1},{kind:'repeat',count:3,body:[{kind:'if',condition:{kind:'compare',op:'LT',left:{kind:'range',direction:'front',unit:'m'},right:{kind:'number',value:.5}},then:[{kind:'move',direction:'left',distance_m:.3}],else:[{kind:'move',direction:'forward',distance_m:.3}]}]},{kind:'land'}]};}
function backend(values){var r=values.slice(),trace=[];return{trace,async takeoff(h){trace.push(['takeoff',h]);},async land(){trace.push(['land']);},async move(d,x){trace.push(['move',d,x]);},async vertical(){throw Error('unused');},async turn(){throw Error('unused');},async wait(){throw Error('unused');},async setSpeed(){throw Error('unused');},async readRange(d){var v=r.shift();trace.push(['range',d,v]);return v;}};}
function workspace(){var range=block('range-front','webeeblocks_v2_range'),num=block('threshold','math_number'),cmp=block('compare','logic_compare',{A:range,B:num}),left=block('left-action','webeeblocks_v2_move'),forward=block('forward-action','webeeblocks_v2_move'),iff=block('if','controls_if',{IF0:cmp,DO0:left,ELSE:forward}),repeat=block('repeat','controls_repeat_ext',{DO:iff}),takeoff=block('takeoff','webeeblocks_v2_takeoff'),land=block('land','webeeblocks_v2_land');link(takeoff,repeat,land);var all={takeoff,repeat,if:iff,compare:cmp,'range-front':range,threshold:num,'left-action':left,'forward-action':forward,land};return{getTopBlocks(){return[takeoff];},getBlockById(id){return all[id]||null;},highlightBlock(){}};}
async function until(p,label){var start=Date.now();while(Date.now()-start<1000){if(p())return;await new Promise(r=>setTimeout(r,0));}throw Error('timeout '+label);}

async function proveProgramInvalidRetryWithoutReset() {
  const elements = {};
  function element(id) {
    if (!elements[id]) elements[id] = {id, disabled:false, hidden:false, checked:false, textContent:'', addEventListener(){}};
    return elements[id];
  }
  const testWorkspace = {valid:false, getAllBlocks(){return [{type:this.valid?'allowed':'forbidden'}];}};
  let compileCalls = 0;
  let interpreterRuns = 0;
  const compiler = {compileWorkspace(){compileCalls += 1; return {version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:1},{kind:'land'}]};}};
  const interpreter = {async run(){interpreterRuns += 1;}};
  const uiBackend = {ready:true, capabilities:{actions:['takeoff','land'],rangeDirections:[],moveDirections:[],verticalDirections:[],simulationDebug:true,simulationReset:true}};
  const profile = {toolbox:['allowed'],parameterBounds:{},runtime:{allowedStatementKinds:['takeoff','land'],rangeDirections:[],moveDirections:[],verticalDirections:[],astBounds:{}}};
  const context = {
    console:{log(){},error(){}},
    Blockly:{Theme:{defineTheme(){return{};}},Themes:{Classic:{}},Events:{UI:'ui',BLOCK_MOVE:'move'},Blocks:{}},
    document:{getElementById:element,body:{dataset:{}},createElement(){return{setAttribute(){},appendChild(){}};}},
    window:{dispatchEvent(){},addEventListener(){}},
    CustomEvent:function(type,init){this.type=type;this.detail=init&&init.detail;},
    WebeeBlocksRuntimeOutcome:Outcome,
    WebeeBlocksActivityContract:ActivityContract,
    WebeeBlocksSemanticAst:compiler,
    WebeeBlocksInterpreter:interpreter,
    WebeeBlocksExecutionObserver:{create(){return null;}},
    WebeeBlocksActivities:{BLOCK_CATALOG:{}},
    WebeeBlocksActivityProfiles:{},
    WebeeBlocksWwiBackend:function(){},
    setTimeout,clearTimeout,Promise
  };
  vm.createContext(context);
  vm.runInContext(mainSource, context, {filename:'blockly_v2/main.js'});
  context.runtimeProfile = profile;
  context.workspace = testWorkspace;
  context.runtimeBackend = uiBackend;
  element('stepMode').checked = false;
  context.updateRuntimeActions();
  assert.strictEqual(element('submit').disabled,false,'ready runtime must initially allow Lancer');

  await context.runProgram();
  assert.strictEqual(compileCalls,0,'invalid block reached compiler');
  assert.strictEqual(interpreterRuns,0,'invalid block reached interpreter/backend path');
  assert.strictEqual(element('runtimeState').textContent,'À CORRIGER');
  assert.strictEqual(context.runtimeTerminal,false,'PROGRAM_INVALID became terminal');
  assert.strictEqual(element('submit').disabled,false,'Lancer stayed disabled after PROGRAM_INVALID');

  testWorkspace.valid = true;
  context.onWorkspaceChange({type:'change'});
  assert.strictEqual(element('submit').disabled,false,'workspace correction should not require reset');
  await context.runProgram();
  assert.strictEqual(compileCalls,1,'corrected workspace did not reach compiler on second attempt');
  assert.strictEqual(interpreterRuns,1,'corrected workspace did not execute on second attempt');
  assert.strictEqual(element('runtimeState').textContent,'TERMINÉ');
  assert.strictEqual(element('runtimeDetail').textContent,'Programme exécuté');

  context.onWorkspaceChange({type:'move',oldParentId:null,newParentId:null});
  assert.strictEqual(element('runtimeDetail').textContent,'Programme exécuté',
    'moving an unconnected top-level stack visually must not require simulation reset');

  context.onWorkspaceChange({type:'move',oldParentId:null,newParentId:'parent-block'});
  assert.strictEqual(element('runtimeDetail').textContent,'Programme modifié — réinitialisez la simulation avant de relancer',
    'a structural Blockly move must still require simulation reset');
}

(async()=>{
  await proveProgramInvalidRetryWithoutReset();
  var a=backend([.4,.8,.3]),b=backend([.4,.8,.3]),program=ast();
  await Interpreter.run(program,a,{maxSteps:1000});
  await Interpreter.run(program,b,{maxSteps:1000,hooks:{onNode(){},beforeStep(){},onSensor(){}}});
  assert.deepStrictEqual(a.trace,b.trace);assert.deepStrictEqual(program,ast());
  var c=backend([.4,.8,.3]),pauses=[],sensors=[],obs=Observer.create(workspace(),{onPause:d=>pauses.push([d.blockId,d.node.kind,d.iteration,Object.prototype.hasOwnProperty.call(d,'decision')]),onSensor:d=>sensors.push([d.blockId,d.direction,d.value])});
  var run=Interpreter.run(ast(),c,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'takeoff');assert.deepStrictEqual(c.trace,[]);assert.deepStrictEqual(pauses[0].slice(0,2),['takeoff','takeoff']);obs.next();
  await until(()=>pauses.length===2,'repeat iteration');assert.deepStrictEqual(c.trace,[['takeoff',1]]);assert.deepStrictEqual(pauses[1].slice(0,3),['repeat','repeat',0]);obs.next();
  await until(()=>pauses.length===3,'range');assert.deepStrictEqual(c.trace,[['takeoff',1]]);assert.deepStrictEqual(pauses[2].slice(0,2),['range-front','range']);obs.next();
  await until(()=>sensors.length===1,'sensor');await until(()=>pauses.length===4,'number');assert.deepStrictEqual(sensors[0],['range-front','front',.4]);assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[3].slice(0,2),['threshold','number']);obs.next();
  await until(()=>pauses.length===5,'compare');assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[4].slice(0,2),['compare','compare']);obs.next();
  await until(()=>pauses.length===6,'if');assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[5].slice(0,2),['if','if']);assert.strictEqual(pauses[5][3],false);obs.next();
  await until(()=>pauses.length===7,'chosen move');assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[6].slice(0,2),['left-action','move']);obs.continueRun();await run;obs.finish();
  assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4],['move','left',.3],['range','front',.8],['move','forward',.3],['range','front',.3],['move','left',.3],['land']]);
  var sent=[],wwi=new WwiBackend({send:m=>sent.push(m)},{timeoutMs:500,simulationDebug:true,simulationStop:true});var req=wwi.move('forward',2);wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 ERR UNSAFE_OR_TIMEOUT');var error;try{await req;}catch(e){error=e;}assert.strictEqual(error.code,'UNSAFE_OR_TIMEOUT');assert.strictEqual(error.message,'Runtime v2 backend error: UNSAFE_OR_TIMEOUT');assert.deepStrictEqual(Outcome.classify(error),{state:'ARRÊTÉ',detail:'L’action n’a pas pu être terminée',machineCode:'UNSAFE_OR_TIMEOUT'});assert.strictEqual(Outcome.classify(Error('technical')).state,'ERREUR');assert.strictEqual(Outcome.isRetryable({code:'PROGRAM_INVALID'}),true);assert.strictEqual(Outcome.isRetryable(error),false);assert.strictEqual(Outcome.isRetryable(Error('technical')),false);assert.strictEqual(wwi.capabilities.simulationDebug,true);assert.strictEqual(wwi.capabilities.simulationStop,true);
  var stopSent=[],stopBackend=new WwiBackend({send:m=>stopSent.push(m)},{timeoutMs:500,simulationStop:true,simulationReset:true});
  var activeMove=stopBackend.move('forward',2),stopRequest=stopBackend.stopSimulation();
  assert.match(stopSent[0],/ REQUEST 1 MOVE forward /);assert.match(stopSent[1],/ REQUEST 2 STOP$/);
  stopBackend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 ERR USER_STOPPED');
  var stoppedError;try{await activeMove;}catch(e){stoppedError=e;}
  assert.strictEqual(stoppedError.code,'USER_STOPPED');
  assert.deepStrictEqual(Outcome.classify(stoppedError),{state:'ARRÊTÉ',detail:'Vol arrêté — réinitialisez la simulation avant de relancer',machineCode:'USER_STOPPED'});
  stopBackend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK');await stopRequest;
  assert.strictEqual(Object.keys(stopBackend.pending).length,0);
  assert.strictEqual(stopBackend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK'),true);
  assert.strictEqual(Object.keys(stopBackend.pending).length,0);
  var sentBeforeBlockedMove=stopSent.length,blockedMove=stopBackend.move('forward',.3),blockedError;try{await blockedMove;}catch(e){blockedError=e;}
  assert.strictEqual(blockedError.code,'USER_STOPPED');assert.strictEqual(stopSent.length,sentBeforeBlockedMove,'stopped backend emitted a later AST action');
  var resetRequest=stopBackend.resetSimulation();assert.match(stopSent[stopSent.length-1],/ REQUEST 3 RESET$/);stopBackend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK');await resetRequest;
  var afterReset=stopBackend.move('forward',.3);assert.match(stopSent[stopSent.length-1],/ REQUEST 4 MOVE forward /);stopBackend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 OK');await afterReset;
  var physical=new WwiBackend({send:m=>sent.push(m)},{timeoutMs:500,simulationDebug:false});assert.notStrictEqual(physical.capabilities.simulationDebug,true);
  console.log('PASS: invalid programs are retryable through the real UI runtime without reset, execution state stays coherent, Continue is pause-only, observability remains optional, semantic stepping hides branch outcomes, raw sensor is fresh, movement waits for its own step, and machine codes remain testable.');
})().catch(e=>{console.error(e.stack||e);process.exit(1);});
