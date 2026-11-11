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
assert.match(projectUiSource, /setRuntimeLocked\(state === 'EXÉCUTION' \|\| state === 'RÉINITIALISATION'\);/);
assert.match(projectUiSource, /workspace\.setIsReadOnly\(runtimeLocked\)/);
assert.match(projectUiSource, /blocklyDiv\.inert = busy;/);
assert.doesNotMatch(projectUiSource, /blocklyDiv\.inert = runtimeLocked;/);
assert.match(projectUiSource, /if \(open\) open\.disabled = locked;/);
assert.match(projectUiSource, /if \(busy \|\| !supported \|\| runtimeLocked\) return null;/);
assert.match(mainSource, /getElementById\('stopSimulation'\)/);
assert.match(mainSource, /await runtimeBackend\.stopSimulation\(\)/);
assert.match(controllerSource, /request\.kind == REQUEST_STOP/);
assert.match(controllerSource, /wb_robot_get_device\("range_left"\)/);
assert.match(controllerSource, /wb_robot_get_device\("range_right"\)/);
assert.match(controllerSource, /strcmp\(request\.direction, "left"\) == 0/);
assert.match(controllerSource, /strcmp\(request\.direction, "right"\) == 0/);
assert.match(controllerSource, /strcmp\(request\.direction, "back"\) != 0/);
assert.match(controllerSource, /strcmp\(request\.direction, "right"\) != 0/);
assert.match(controllerSource, /target_x = x - cos\(yaw\) \* request\.value/);
assert.match(controllerSource, /target_y = y - cos\(yaw\) \* request\.value/);
assert.match(controllerSource, /response_error\(active_id, "USER_STOPPED"\)/);
assert.match(controllerSource, /target_x = x;[\s\S]*target_y = y;[\s\S]*target_z = z;[\s\S]*failsafe_latched = 1;/);
assert.doesNotMatch(controllerSource, /command == CMD_IDLE \|\| command == CMD_RESET/);
assert.match(controllerSource, /if \(active_id >= 1\)[\s\S]*response_error\(active_id, "USER_STOPPED"\)/);
assert.match(mainSource, /runtimeStopRequested = true;/);
assert.match(mainSource, /runtimeDebug\.cancel\(\)/);
assert.match(mainSource, /if \(runtimeStopRequested\) throw userStoppedError\(\);/);

function block(id,type,inputs){return{id,type,_next:null,_inputs:inputs||{},getNextBlock(){return this._next;},getInputTargetBlock(name){return this._inputs[name]||null;}};}
function link(){var blocks=Array.from(arguments);for(var i=0;i<blocks.length-1;i++)blocks[i]._next=blocks[i+1];return blocks[0];}
function ast(){return{version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:1},{kind:'repeat',count:3,body:[{kind:'if',condition:{kind:'compare',op:'LT',left:{kind:'range',direction:'front',unit:'m'},right:{kind:'number',value:.5}},then:[{kind:'move',direction:'left',distance_m:.3}],else:[{kind:'move',direction:'forward',distance_m:.3}]}]},{kind:'land'}]};}
function backend(values){var r=values.slice(),trace=[];return{trace,async takeoff(h){trace.push(['takeoff',h]);},async land(){trace.push(['land']);},async move(d,x){trace.push(['move',d,x]);},async vertical(){throw Error('unused');},async turn(){throw Error('unused');},async wait(){throw Error('unused');},async setSpeed(){throw Error('unused');},async readRange(d){var v=r.shift();trace.push(['range',d,v]);return v;}};}
function workspace(){var range=block('range-front','webeeblocks_v2_range'),num=block('threshold','math_number'),cmp=block('compare','logic_compare',{A:range,B:num}),left=block('left-action','webeeblocks_v2_move'),forward=block('forward-action','webeeblocks_v2_move'),iff=block('if','controls_if',{IF0:cmp,DO0:left,ELSE:forward}),repeat=block('repeat','controls_repeat_ext',{DO:iff}),takeoff=block('takeoff','webeeblocks_v2_takeoff'),land=block('land','webeeblocks_v2_land');link(takeoff,repeat,land);var all={takeoff,repeat,if:iff,compare:cmp,'range-front':range,threshold:num,'left-action':left,'forward-action':forward,land};return{getTopBlocks(){return[takeoff];},getBlockById(id){return all[id]||null;},highlightBlock(){}};}
async function until(p,label){var start=Date.now();while(Date.now()-start<1000){if(p())return;await new Promise(r=>setTimeout(r,0));}throw Error('timeout '+label);}

// A host watchdog must not truncate the existing Continue observation window.
const nativeWorkflow = fs.readFileSync(path.resolve(__dirname, '../../.github/workflows/ci-runtime.yml'), 'utf8');
const stepHarness = fs.readFileSync(path.resolve(__dirname, 'prepare_runtime_v2_observability.py'), 'utf8');
const stepJob = nativeWorkflow.split('- name: Run real Robot Window semantic step scenario')[1].split('- name: Validate causal semantic steps')[0];
const hostSeconds = Number(stepJob.match(/timeout -k 5s (\d+)s xvfb-run/)[1]);
const continueMs = Number(stepHarness.match(/'continued completion', (\d+)\)/)[1]);
function coversContinue(seconds) { return seconds >= 65 + continueMs / 1000; }
assert.strictEqual(coversContinue(65),false,'historical host cut must remain a counterexample');
assert(coversContinue(hostSeconds),'host envelope truncates an authorized Continue phase');
if(process.platform !== 'win32') {
  const shellScript=stepJob.split('run: |')[1].split('\n').map(line=>line.replace(/^ {10}/,'')).join('\n');
  const syntax=require('child_process').spawnSync('bash',['-n'],{input:shellScript,encoding:'utf8'});
  assert.strictEqual(syntax.status,0,syntax.stderr);
}
assert.match(stepHarness, /'STEP_CONTINUE_DONE'/); // Completion is still browser-owned after TERMINÉ.

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
  context.runtimeProjectPending = true;
  context.updateRuntimeActions();
  assert.strictEqual(element('submit').disabled,true,'project transaction enabled Lancer between scene ACK and workspace application');
  await context.runProgram();
  assert.strictEqual(compileCalls,0,'late Lancer during project transaction reached compilation');
  assert.strictEqual(interpreterRuns,0,'late Lancer during project transaction reached backend');
  context.runtimeProjectPending = false;
  context.onWorkspaceChange({type:'change'});
  context.updateRuntimeActions();
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


async function proveOutcomePendingBlocksResetAndLateVerdicts() {
  function deferred() {
    let resolve, reject;
    const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
    return {promise, resolve, reject};
  }
  const elements = {};
  function element(id) {
    if (!elements[id]) elements[id] = {
      id, disabled:false, hidden:false, checked:false, textContent:'', addEventListener(){}
    };
    return elements[id];
  }
  const missionCompletion = deferred();
  const failureOutcome = deferred();
  let failExecution = false;
  let resetCalls = 0;
  let outcomeReads = 0;
  const profile = {runtime:{maxSteps:100}, evaluation:{type:'mission-state-v1'}};
  const backend = {
    ready:true,
    capabilities:{simulationReset:true, simulationStop:false},
    async completeActivityMission() { await missionCompletion.promise; },
    async readActivityOutcome() {
      outcomeReads++;
      return failExecution ? failureOutcome.promise : {status:'achieved'};
    },
    async resetSimulation() { resetCalls++; }
  };
  const context = {
    console:{log(){}, error(){}},
    Blockly:{
      Theme:{defineTheme(){return{};}}, Themes:{Classic:{}},
      Events:{UI:'ui',BLOCK_MOVE:'move'}, Blocks:{},
      serialization:{workspaces:{save(){return {blocks:[]};}}}
    },
    document:{getElementById:element, body:{dataset:{}}, currentScript:null},
    window:{dispatchEvent(){}, addEventListener(){}},
    CustomEvent:function(type, init){this.type=type;this.detail=init&&init.detail;},
    WebeeBlocksRuntimeOutcome:Outcome,
    WebeeBlocksActivityContract:{
      async execute(profile, workspace, compiler, interpreter, runtime, options) {
        options.onAst({version:1, program:[]});
        if (failExecution) {
          const error = new Error('native movement refused');
          error.code = 'UNSAFE_OR_TIMEOUT';
          throw error;
        }
      }
    },
    WebeeBlocksSemanticAst:{}, WebeeBlocksInterpreter:{},
    WebeeBlocksExecutionObserver:{}, WebeeBlocksActivities:{},
    WebeeBlocksActivityProfiles:{}, WebeeBlocksWwiBackend:function(){},
    Promise, setTimeout, clearTimeout
  };
  vm.createContext(context);
  vm.runInContext(mainSource, context, {filename:'blockly_v2/main.js'});
  context.runtimeProfile = profile;
  context.workspace = {};
  context.runtimeBackend = backend;

  const firstRun = context.runProgram();
  await until(() => context.runtimeOutcomePending, 'mission completion wait');
  assert.strictEqual(context.runtimeRunning,false,'interpreter must have finished before mission outcome');
  assert.strictEqual(context.runtimeTerminal,true,'outcome wait must retain reset-required terminal state');
  assert.strictEqual(element('runtimeState').textContent,'EXÉCUTION',
    'late mission result must not be presented as completed');
  context.updateRuntimeActions(); // Adversarial delayed UI update.
  assert.strictEqual(element('resetSimulation').disabled,true,'reset exposed before mission outcome settled');
  assert.strictEqual(element('submit').disabled,true,'launch/stop exposed while evaluator is pending');
  await context.resetSimulation(); // Direct/stale callback must be guarded too.
  assert.strictEqual(resetCalls,0,'RESET overlapped an unsettled mission result');
  assert.strictEqual(context.runtimeTerminal,true);
  missionCompletion.resolve();
  await firstRun;
  assert.strictEqual(outcomeReads,1);
  assert.strictEqual(context.runtimeOutcomePending,false);
  assert.strictEqual(element('runtimeState').textContent,'MISSION RÉUSSIE');
  assert.strictEqual(element('resetSimulation').disabled,false,'reset remained blocked after valid outcome');

  await context.resetSimulation();
  assert.strictEqual(resetCalls,1,'real reset should be allowed after outcome');
  assert.strictEqual(element('runtimeState').textContent,'PRÊT');

  // An UNSAFE_OR_TIMEOUT can await an irreversible world-failure witness.
  // Its read must also finish before any later RESET invalidates the attempt.
  failExecution = true;
  const secondRun = context.runProgram();
  await until(() => context.runtimeOutcomePending && outcomeReads === 2, 'failure witness wait');
  assert.strictEqual(context.runtimeRunning,false);
  context.updateRuntimeActions();
  assert.strictEqual(element('resetSimulation').disabled,true,
    'failure-witness read exposed RESET before exact-attempt evidence');
  await context.resetSimulation();
  assert.strictEqual(resetCalls,1,'RESET overlapped unresolved failure-witness read');
  failureOutcome.resolve({status:'not-achieved'});
  await secondRun;
  assert.strictEqual(context.runtimeOutcomePending,false,'failure path left UI permanently locked');
  assert.strictEqual(element('runtimeState').textContent,'MISSION NON RÉUSSIE');
  assert.strictEqual(element('resetSimulation').disabled,false);
  await context.resetSimulation();
  assert.strictEqual(resetCalls,2);
  assert.strictEqual(element('runtimeState').textContent,'PRÊT');
}


function proveReadonlyStepNavigation() {
  const projectUi = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
  const html = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/blockly_v2.html'), 'utf8');
  assert.match(html, /id="debugShowCurrent"/);
  assert.match(mainSource, /workspace\.centerOnBlock\(debugCurrentBlockId, true\)/);
  const documentListeners = {};
  const events = {};
  const controls = {};
  const registeredMenus = [];
  let breakpointMenu = null;
  function el(id) {
    if (!controls[id]) controls[id] = {
      disabled:false, inert:false, textContent:'', hidden:false, checked:false,
      listeners:{}, addEventListener(type, fn) { this.listeners[type] = fn; }
    };
    return controls[id];
  }
  const centered = [], commands = [];
  const visible = {}, blockModels = {};
  const view = {left:100, top:100, right:800, bottom:600};
  const wk = {
    readOnly:false,
    isReadOnly() { return this.readOnly; },
    setIsReadOnly(value) { this.readOnly = value; },
    getBlockById(id) {
      if (!blockModels[id]) {
        const marked = new Set();
        const svg = {
          contains(target) {return target === id;},
          classList:{toggle(name, flag){if(flag)marked.add(name);else marked.delete(name);}},
          getBoundingClientRect() { return visible[id] ? {left:200,top:200,right:300,bottom:230,width:100,height:30} :
            {left:900,top:900,right:1000,bottom:930,width:100,height:30}; }
        };
        blockModels[id] = {id,type:'procedures_callnoreturn',workspace:wk,marked,getSvgRoot(){return svg;}};
      }
      return blockModels[id];
    },
    getAllBlocks() { return Object.values(blockModels); },
    getParentSvg() { return {querySelector() { return {getBoundingClientRect() { return view; }}; }}; },
    centerOnBlock(id, blockOnly) { centered.push([id,blockOnly]); visible[id] = true; },
    zoomCenter(value) { commands.push(['zoom',value]); },
    zoomToFit() { commands.push(['fit']); },
    setScale(value) { commands.push(['scale',value]); },
    scrollCenter() { commands.push(['scrollCenter']); }
  };
  let boundChecks=0;
  const context = {
    console:{log(){},error(){}},
    Blockly:{Theme:{defineTheme(){return{};}},Themes:{Classic:{}},
      Events:{UI:'ui',BLOCK_MOVE:'move',BLOCK_CREATE:'create',BLOCK_DELETE:'delete',VIEWPORT_CHANGE:'viewport_change'},Blocks:{},
      ContextMenuRegistry:{ScopeType:{BLOCK:'block'},registry:{register(item){registeredMenus.push(item);}}}},
    document:{currentScript:null, getElementById:el, body:{dataset:{},appendChild(){}},
      createElement(tag){
        const node={hidden:true,dataset:{},style:{},listeners:{},setAttribute(){},
          appendChild(){},addEventListener(type,fn){this.listeners[type]=fn;},focus(){}};
        if(tag==='button') breakpointMenu=node;
        return node;
      },
      addEventListener(type,fn){documentListeners[type]=fn;}},
    window:{addEventListener(type,fn){events[type]=fn;},dispatchEvent(){}},
    CustomEvent:function(type,init){this.type=type;this.detail=init&&init.detail;},
    WebeeBlocksExecutionObserver:Observer, WebeeBlocksActivities:{BLOCK_CATALOG:{}},
    WebeeBlocksActivityContract:{applyFieldBounds(){boundChecks++;}},
    setTimeout,clearTimeout,Promise
  };
  vm.createContext(context);
  vm.runInContext(mainSource, context, {filename:'blockly_v2/main.js'});
  context.workspace = wk;
  vm.runInContext(projectUi, context, {filename:'blockly_v2/project_ui.js'});
  context.wireDebugControls();
  context.wireWorkspaceControls();
  assert.equal(registeredMenus.length,1,'exactly one native Blockly breakpoint item');
  const nativeBlock = wk.getBlockById('main');
  const menuOption = registeredMenus[0];
  assert.equal(menuOption.preconditionFn({block:nativeBlock}),'enabled');
  assert.match(menuOption.displayText({block:nativeBlock}),/Ajouter/);
  menuOption.callback({block:nativeBlock});
  assert(context.runtimeDebug.hasBreakpoint('main'),'native menu must add in-memory breakpoint');
  assert(nativeBlock.marked.has('webeeblocks-breakpoint'),'native menu must mark block SVG');
  assert.match(menuOption.displayText({block:nativeBlock}),/Retirer/);
  menuOption.callback({block:nativeBlock});
  assert.equal(context.runtimeDebug.hasBreakpoint('main'),false);
  context.runtimeRunning = true;
  events['webeeblocks-runtime-v2']({detail:{state:'EXÉCUTION'}});
  assert.equal(wk.isReadOnly(),true,'execution must lock Blockly edits');
  assert.equal(el('blocklyDiv').inert,false,'execution must leave native scrollbars interactive');
  assert.equal(el('projectSaveAs').disabled,true,'project writes remain locked');
  const callbacks=context.runtimeDebug.callbacks;
  callbacks.onBegin({enabled:true});
  callbacks.onActive({blockId:'main',path:['program',0],node:{kind:'takeoff'}});
  callbacks.onPause({blockId:'main'});
  assert.deepEqual(centered,[['main',true]],'first offscreen block must become visible');
  assert.equal(el('stepNext').disabled,false);
  assert.equal(el('stepContinue').disabled,false);
  assert.equal(el('debugShowCurrent').disabled,false);
  el('blocklyDiv').listeners.pointerdown();
  callbacks.onActive({blockId:'procedure-a',path:['program',1,'body',0],node:{kind:'move'}});
  callbacks.onPause({blockId:'procedure-a'});
  assert.equal(centered.length,1,'manual scrollbar/pan must suppress automatic recenter');
  const duringPause = wk.getBlockById('procedure-a');
  assert.equal(menuOption.preconditionFn({block:duringPause}),'hidden',
    'native edit menu must remain hidden in flight');
  context.runtimeDebug.waiter = {resolve(){}};
  let stoppedContextEvent = false;
  el('blocklyDiv').listeners.contextmenu({
    target:'procedure-a',clientX:150,clientY:230,
    preventDefault(){stoppedContextEvent=true;},stopPropagation(){}
  });
  assert(stoppedContextEvent,'read-only paused Blockly must intercept right-click');
  assert.equal(breakpointMenu.hidden,false);
  assert.match(breakpointMenu.textContent,/Ajouter/);
  breakpointMenu.listeners.click.call(breakpointMenu);
  assert(context.runtimeDebug.hasBreakpoint('procedure-a'),
    'paused read-only context action must add breakpoint without editing');
  assert(duringPause.marked.has('webeeblocks-breakpoint'));
  assert.equal(wk.isReadOnly(),true,'breakpoint context action unlocked Blockly editing');
  el('blocklyDiv').listeners.contextmenu({
    target:'procedure-a',clientX:150,clientY:230,
    preventDefault(){},stopPropagation(){}
  });
  assert.match(breakpointMenu.textContent,/Retirer/);
  breakpointMenu.listeners.click.call(breakpointMenu);
  assert.equal(context.runtimeDebug.hasBreakpoint('procedure-a'),false);
  context.runtimeDebug.waiter = null;
  el('debugShowCurrent').listeners.click.call(el('debugShowCurrent'));
  assert.deepEqual(centered[1],['procedure-a',true],'explicit return must center only current block');
  callbacks.onPause({blockId:'procedure-a'});
  assert.equal(centered.length,2,'already visible block must not jump');
  callbacks.onPause({blockId:'procedure-b'});
  assert.deepEqual(centered[2],['procedure-b',true],'following resumes after explicit return');
  el('blocklyDiv').listeners.wheel();
  callbacks.onPause({blockId:'main'});
  assert.equal(centered.length,3,'wheel navigation must stay in pupil control');
  el('zoomOut').listeners.click();
  assert.deepEqual(commands,[['zoom',-1]]);
  assert.equal(centered.length,3,'zoom must not force recenter');
  el('runtimeDetail').textContent='En pause';
  context.runtimeRunning=false;
  context.runtimeTerminal=true;
  context.onWorkspaceChange({type:'viewport_change',isUiEvent:false});
  context.onWorkspaceChange({type:'move',oldParentId:null,newParentId:null});
  context.onWorkspaceChange({type:'anything',isUiEvent:true});
  assert.equal(boundChecks,0,'view changes must not invoke AST field bounds');
  assert.equal(el('runtimeDetail').textContent,'En pause','view changes must not signal program modification');
  events['webeeblocks-runtime-v2']({detail:{state:'TERMINÉ'}});
  assert.equal(wk.isReadOnly(),false,'terminal state must restore editability');
  assert.equal(el('blocklyDiv').inert,false);
  callbacks.onFinish();
  assert.equal(el('debugShowCurrent').disabled,true);
  assert.equal(el('stepNext').disabled,true);
  assert.equal(el('stepContinue').disabled,true);
}


async function proveResetFromPausedDebugger() {
  // STOP must be acknowledged by the native backend before RESET may be sent.
  // A JS-only debugger promise release is not sufficient native authority.
  const controls={};
  function el(id) {
    if (!controls[id]) controls[id]={id,disabled:false,hidden:false,checked:false,textContent:'',
      addEventListener(){},setAttribute(){}};
    return controls[id];
  }
  function deferred() {
    let resolve,reject;
    const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
    return {promise,resolve,reject};
  }
  const nativeStop=deferred(),nativeReset=deferred(),interpreterWait=deferred();
  const calls=[],errors=[];
  const mockDebug={
    enabled:true,waiter:{},begin(){this.enabled=true;this.waiter={};return {};},
    cancel() {calls.push('cancel-debugger');this.waiter=null;
      const error=new Error('interrupted');error.code='USER_STOPPED';
      interpreterWait.reject(error);
    },
    finish() {this.enabled=false;this.waiter=null;}
  };
  const context={
    console:{log(){},error(e){errors.push(e);}},
    Blockly:{Theme:{defineTheme(){return{};}},Themes:{Classic:{}},Events:{UI:'ui',BLOCK_MOVE:'move'},Blocks:{},
      serialization:{workspaces:{save(){return {blocks:['unchanged']};}}}},
    document:{currentScript:null,getElementById:el,body:{dataset:{}},createElement(){return{};}},
    window:{dispatchEvent(){},addEventListener(){}},
    CustomEvent:function(type,init){this.type=type;this.detail=init&&init.detail;},
    WebeeBlocksRuntimeOutcome:{
      classify(e){return {state:'ARRÊTÉ',detail:String(e&&e.code||''),machineCode:e&&e.code};},
      isRetryable(){return false;},
      async readMissionFailure(){throw Error('STOP must not request a mission outcome');},
      async evaluateMission(){throw Error('cancelled program must not evaluate mission');}
    },
    WebeeBlocksActivityContract:{
      async execute(profile,workspace,compiler,interpreter,runtime,options) {
        options.onAst({version:1,program:[]});
        await interpreterWait.promise;
      }
    },
    WebeeBlocksSemanticAst:{},WebeeBlocksInterpreter:{},WebeeBlocksActivities:{BLOCK_CATALOG:{}},
    WebeeBlocksActivityProfiles:{},WebeeBlocksWwiBackend:function(){},
    setTimeout,clearTimeout,Promise
  };
  vm.createContext(context);
  vm.runInContext(mainSource,context,{filename:'blockly_v2/main.js'});
  context.runtimeProfile={runtime:{maxSteps:100}};
  context.workspace={};
  context.runtimeDebug=mockDebug;
  context.runtimeBackend={
    ready:true,capabilities:{simulationDebug:true,simulationStop:true,simulationReset:true},
    async stopSimulation(){calls.push('native-STOP');await nativeStop.promise;},
    async resetSimulation(){calls.push('native-RESET');await nativeReset.promise;}
  };
  el('stepMode').checked=true;
  const execution=context.runProgram();
  assert.equal(context.runtimeRunning,true,'runtime did not enter active program');
  context.updateRuntimeActions();
  assert.equal(el('resetSimulation').disabled,false,
    'RESET-with-STOP control must be available during a debugger pause');
  assert.equal(el('resetSimulation').textContent,'Arrêter puis réinitialiser');

  const reset=context.resetSimulation();
  assert.deepEqual(calls,['cancel-debugger','native-STOP']);
  await Promise.resolve();await Promise.resolve();
  assert(!calls.includes('native-RESET'),
    'RESET executed before acknowledgement of independent native STOP');
  nativeStop.resolve();
  for(let turn=0;turn<100 && !calls.includes('native-RESET');turn++)
    await new Promise(resolve=>setTimeout(resolve,0));
  assert(calls.includes('native-RESET'),
    'native STOP ACK + settled interpreter must permit RESET');
  assert.equal(context.runtimeRunning,false);
  nativeReset.resolve();
  await reset;
  await execution;
  assert.deepEqual(calls,['cancel-debugger','native-STOP','native-RESET']);
  assert.equal(context.runtimeTerminal,false,'RESET did not return simulation to ready state');
  assert.equal(context.runtimeStopRequested,false,'RESET retained stopped latch');
  assert.equal(el('runtimeState').textContent,'PRÊT');
  assert.equal(errors.length,1,'STOP should be represented by one expected interrupted program');

  // A denied native STOP must never be followed by a RESET request.
  const denied=deferred(),pending=deferred(),refusedCalls=[];
  const secondObserver={enabled:true,waiter:{},
    begin(){this.waiter={};return {};},
    cancel(){this.waiter=null;const error=new Error('STOP');error.code='USER_STOPPED';pending.reject(error);},
    finish(){this.waiter=null;}
  };
  const context2=Object.assign({},context);
  // The fresh context must not reuse global lexical bindings or the first runtime.
  const contextFresh={
    ...context,
    document:{currentScript:null,getElementById:el,body:{dataset:{}},createElement(){return {};}},
    window:{dispatchEvent(){},addEventListener(){}},
    WebeeBlocksActivityContract:{async execute(p,w,c,i,b,options){options.onAst({});await pending.promise;}}
  };
  vm.createContext(contextFresh);
  vm.runInContext(mainSource,contextFresh,{filename:'blockly_v2/main.js second scenario'});
  contextFresh.runtimeProfile={runtime:{maxSteps:100}};
  contextFresh.workspace={};
  contextFresh.runtimeDebug=secondObserver;
  contextFresh.runtimeBackend={
    ready:true,capabilities:{simulationDebug:true,simulationStop:true,simulationReset:true},
    async stopSimulation(){refusedCalls.push('STOP');await denied.promise;},
    async resetSimulation(){refusedCalls.push('RESET');}
  };
  const execute2=contextFresh.runProgram();
  const reset2=contextFresh.resetSimulation();
  denied.reject(new Error('native STOP refused'));
  await reset2;await execute2;
  assert.deepEqual(refusedCalls,['STOP'],'rejected STOP must block native RESET');
}

(async()=>{
  await require('./test_runtime_v2_breakpoints.js')();
  await proveResetFromPausedDebugger();
  proveReadonlyStepNavigation();
  await proveProgramInvalidRetryWithoutReset();
  await proveOutcomePendingBlocksResetAndLateVerdicts();
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
  var physical=new WwiBackend({send:m=>sent.push(m)},{timeoutMs:500,simulationDebug:false});assert.notStrictEqual(physical.capabilities.simulationDebug,true);assert.deepStrictEqual(physical.capabilities.rangeDirections,['front','back','left','right','up']);assert.deepStrictEqual(physical.capabilities.moveDirections,['forward','back','left','right']);
  console.log('PASS: native read-only Blockly scrolling, explicit current-block return and no recenter after manual navigation.');
  console.log('PASS: invalid programs are retryable through the real UI runtime without reset, execution state stays coherent, Continue is pause-only, observability remains optional, semantic stepping hides branch outcomes, raw sensor is fresh, movement waits for its own step, and machine codes remain testable.');
})().catch(e=>{console.error(e.stack||e);process.exit(1);});
