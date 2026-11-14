'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '../..');
const Blockly = require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const SemanticAst = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));
const ActivityContract = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const ProjectFiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/project_files.js'));
const WwiProjectFileTransport = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/project_file_wwi_transport.js'));
const WwiBackend = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));

require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
global.Blockly=Blockly;require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js'));delete global.Blockly;
function setMotionNumber(block,name,value){
  let literal=block.getInputTargetBlock(name);
  if(!literal){literal=block.workspace.newBlock('math_number');block.getInput(name).connection.connect(literal.outputConnection);}
  literal.setFieldValue(String(value),'NUM');
}

function buildWorkspace(distance) {
  const workspace = new Blockly.Workspace();
  const takeoff = workspace.newBlock('webeeblocks_v2_takeoff');
  const move = workspace.newBlock('webeeblocks_v2_move');
  const land = workspace.newBlock('webeeblocks_v2_land');
  setMotionNumber(takeoff,'HEIGHT',1);
  move.setFieldValue('forward', 'DIRECTION');
  setMotionNumber(move,'DISTANCE',distance);
  takeoff.nextConnection.connect(move.previousConnection);
  move.nextConnection.connect(land.previousConnection);
  return workspace;
}

function ast(workspace, profile) {
  ActivityContract.preflightWorkspace(profile, workspace);
  const value = SemanticAst.compileWorkspace(workspace);
  ActivityContract.preflightAst(profile, value);
  return value;
}

function memoryTransport() {
  const state = {writes:[], releases:[], openText:null, currentText:null};
  const handle = {name:'eleve.wbb', token:'same-target'};
  return {
    state,
    nativeFileSystemAccess:true,
    async open() {
      if (state.openText === null) throw new Error('no open fixture');
      return {handle, name:handle.name, text:state.openText, mode:'test'};
    },
    async saveAs(name, text) {
      state.currentText = text;
      state.writes.push({kind:'saveAs',name,text,handle});
      return {handle,name,mode:'test'};
    },
    async save(target, name, text) {
      assert.strictEqual(target, handle, 'Save must reuse chosen file handle');
      state.currentText = text;
      state.writes.push({kind:'save',name,text,handle:target});
      return {handle:target,name,mode:'test'};
    },
    async release(target) { state.releases.push(target); }
  };
}

function managerFor(workspace, profileRef, transport) {
  return ProjectFiles.createManager({
    Blockly,
    profiles:Profiles,
    activitiesDocument:Activities.DOCUMENT,
    blockCatalog:Activities.BLOCK_CATALOG,
    semanticAst:SemanticAst,
    activityContract:ActivityContract,
    workspace,
    getProfile:() => profileRef.value,
    setProfile:profile => { profileRef.value = profile; },
    transport
  });
}

function sceneAck(backend, id) {
  const pending=backend.pending[id];
  assert(pending && /^[0-9a-f]{64}$/.test(pending.sceneNonce),'missing native scene correlation');
  return 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+id+' SCENE_OK '+pending.sceneNonce;
}

function activityProfile(id) {
  return Profiles.resolveById(Activities.DOCUMENT, id, Activities.BLOCK_CATALOG);
}

async function proveScenePreparation() {
  const messages = [];
  const backend = new WwiBackend({send: m => messages.push(m)}, {simulationScenes:true,timeoutMs:1000});
  const sequence = Profiles.resolveById(Activities.DOCUMENT, 'progression-sequence-v1', Activities.BLOCK_CATALOG);
  const pending = backend.prepareActivity(sequence);
  assert.match(messages[0], / REQUEST 1 SCENE sequence-v1 [0-9a-f]{64}$/);
  backend.handleMessage(sceneAck(backend,1));
  await pending;
  // Reject missing/unsupported scene metadata even if the numeric ID resembles
  // a known activity; a forged profile cannot silently select legacy content.
  for (const scene of [undefined, '', '../../', 'unknown-v2']) {
    const profile = {id:'progression-sequence-v1', runtime:scene === undefined ? {} : {scene}};
    await assert.rejects(() => backend.prepareActivity(profile),
      error => error && error.code === 'SCENE_UNAVAILABLE');
  }
  assert.strictEqual(messages.length, 1, 'invalid profile triggered native scene import');

  // The new school profile must still receive a nonce-bound native SCENE_OK.
  const stagedAltitude = activityProfile('progression-altitude-v1');
  assert.strictEqual(Profiles.validateProfile(stagedAltitude, Activities.BLOCK_CATALOG), true);
  const preparingAltitude = backend.prepareActivity(stagedAltitude);
  assert.match(messages.at(-1), / REQUEST 2 SCENE altitude-v1 [0-9a-f]{64}$/);
  assert.strictEqual(backend.sceneIdentity, null, 'unsolicited native altitude READY');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK');
  assert.strictEqual(backend.sceneIdentity, null, 'legacy OK unexpectedly authenticated the scene');
  backend.handleMessage(sceneAck(backend, 2));
  await preparingAltitude;
  assert.strictEqual(backend.sceneIdentity, 'altitude-v1');

  // The orientation vocabulary is staged, but no pupil profile selects it.
  // Even a legacy OK must not attest the world: only an exact native scene ACK.
  const stagedOrientation = JSON.parse(JSON.stringify(sequence));
  stagedOrientation.runtime.scene = 'orientation-v1';
  assert.strictEqual(Profiles.validateProfile(stagedOrientation, Activities.BLOCK_CATALOG), true);
  assert(!Activities.DOCUMENT.activities.some(p => p.runtime.scene === 'orientation-v1'));
  const preparingOrientation = backend.prepareActivity(stagedOrientation);
  assert.match(messages.at(-1), / REQUEST 3 SCENE orientation-v1 [0-9a-f]{64}$/);
  assert.strictEqual(backend.sceneIdentity, null, 'orientation claimed before native ACK');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK');
  assert.strictEqual(backend.sceneIdentity, null, 'legacy OK authenticated orientation');
  backend.handleMessage(sceneAck(backend, 3));
  await preparingOrientation;
  assert.strictEqual(backend.sceneIdentity, 'orientation-v1');

  const unavailable = new WwiBackend({send: () => {throw new Error('unexpected send');}});
  await assert.rejects(() => unavailable.prepareActivity(sequence), /scenes unavailable/);
  backend.simulationStopped = true;
  await assert.rejects(() => backend.prepareActivity(sequence), e => e.code === 'USER_STOPPED');
  assert.strictEqual(messages.length, 3);

  const sent = [];
  const racing = new WwiBackend({send:m=>sent.push(m)}, {simulationScenes:true,simulationReset:true,timeoutMs:1000});
  const preparing = racing.prepareActivity(sequence);
  await assert.rejects(()=>racing.prepareActivity(activityProfile('reactive-obstacle-v2')), e=>e.code==='SCENE_BUSY');
  assert.strictEqual(sent.length,1,'overlapping selection sent a second scene command');
  racing.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 VALUE 1');
  await assert.rejects(preparing,/invalid scene acknowledgement/);
  assert.strictEqual(racing.sceneIdentity,null);
  const old = racing.prepareActivity(sequence);
  const cancelled = assert.rejects(old,e=>e.code==='RESET_CANCELLED');
  racing.handleMessage(sceneAck(racing,2));
  const resetting = racing.resetSimulation(); // ACK received, callback still queued.
  racing.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK');
  await cancelled; await resetting;
  assert.strictEqual(racing.sceneIdentity,null,'late scene ACK survived RESET');
  const recovered = racing.prepareActivity(sequence);
  racing.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK'); // stale response
  assert.strictEqual(racing.sceneIdentity,null);
  racing.handleMessage(sceneAck(racing,4)); await recovered;
  assert.strictEqual(racing.sceneIdentity,'sequence-v1');

  racing.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY');
  assert.strictEqual(racing.sceneIdentity,null,'native READY retained scene evidence');
  const restarting = racing.prepareActivity(sequence);
  const revoked = assert.rejects(restarting,e=>e.code==='RESET_CANCELLED');
  racing.handleMessage(sceneAck(racing,5));
  racing.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY'); // ACK callback still queued.
  await revoked;
  assert.strictEqual(racing.sceneIdentity,null,'old ACK survived native READY');
  const beforeAck = racing.prepareActivity(sequence);
  const rejected = assert.rejects(beforeAck,e=>e.code==='RESET_CANCELLED');
  racing.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY');
  racing.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 6 OK');
  await rejected;
  assert.strictEqual(racing.sceneIdentity,null);
  const afterRestart = racing.prepareActivity(sequence);
  racing.handleMessage(sceneAck(racing,7));
  await afterRestart;
  assert.strictEqual(racing.sceneIdentity,'sequence-v1');

  const live = buildWorkspace(0.2), ref = {value:Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG)};
  let releasePreparation;
  let rejectPreparation;
  const waiting = new Promise((resolve,reject) => {releasePreparation=resolve;rejectPreparation=reject;});
  let preparationCalls=0;
  const manager = ProjectFiles.createManager({
    Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,blockCatalog:Activities.BLOCK_CATALOG,
    semanticAst:SemanticAst,activityContract:ActivityContract,workspace:live,
    getProfile:()=>ref.value,setProfile:p=>{ref.value=p;},transport:memoryTransport(),
    prepareProfile:async p=>{assert.strictEqual(p.id,sequence.id);preparationCalls++;await waiting;}
  });
  const before = Blockly.serialization.workspaces.save(live);
  const opening = manager.openTemplateText('activite.wbb',ProjectFiles.createStarterText(sequence.id));
  await Promise.resolve();
  assert.strictEqual(preparationCalls,1);
  assert.deepStrictEqual(Blockly.serialization.workspaces.save(live),before,'workspace mutated before scene ACK');
  rejectPreparation(new Error('partial scene import'));
  await assert.rejects(()=>opening,/partial scene import/);
  assert.deepStrictEqual(Blockly.serialization.workspaces.save(live),before,'failed preparation erased project');
  assert.strictEqual(ref.value.id,'reactive-obstacle-v2');
  live.dispose();
}

async function proveSceneRollback() {
  for (const mode of ['template','open']) for (const restorationFails of [false,true]) {
    const live = buildWorkspace(0.2), original = Profiles.resolveById(Activities.DOCUMENT,'reactive-obstacle-v2',Activities.BLOCK_CATALOG);
    const ref = {value:original}, transport = memoryTransport();
    let selected = original.id, failLoad = false;
    const causal = new Error('live project application failed'), restoration = new Error('legacy scene restoration failed');
    const manager = ProjectFiles.createManager({
      Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,blockCatalog:Activities.BLOCK_CATALOG,
      semanticAst:SemanticAst,activityContract:ActivityContract,workspace:live,
      getProfile:()=>ref.value,setProfile:p=>{if(failLoad && p.id==='progression-sequence-v1'){failLoad=false;throw causal;}ref.value=p;},transport,
      prepareProfile:async p=>{if(restorationFails && failLoad===false && p.id===original.id)throw restoration;selected=p.id;}
    });
    await manager.saveAs('original.wbb');
    const before = Blockly.serialization.workspaces.save(live);
    const text = ProjectFiles.createStarterText('progression-sequence-v1');
    transport.state.openText = text; failLoad=true;
    await assert.rejects(mode==='open'?manager.open():manager.openTemplateText('activity.wbb',text),error=>error===causal);
    assert.strictEqual(ref.value.id,original.id);
    assert.deepStrictEqual(Blockly.serialization.workspaces.save(live),before);
    assert(manager.hasCurrentTarget(),'failed project application lost original save target');
    if(restorationFails) assert.strictEqual(causal.sceneRestorationError,restoration,'restoration error lost');
    else assert.strictEqual(selected,original.id,'workspace restored but scene still selected for rejected project');
    await manager.save(); // original target remains usable
    live.dispose();
  }
}

async function proveSceneReattachment() {
  const starters = fs.readdirSync(path.join(ROOT,'activities/progression')).filter(name=>name.endsWith('.wbb')).sort();
  const sequence = 'progression-sequence-v1';
  const flush = async () => { for(let i=0;i<8;i++) await Promise.resolve(); };
  // One native controller outlives both Robot Window/backend instances.
  function nativeController(initialScene) {
    return {scene:initialScene, requests:[], attach() {
      const controller=this;
      let backend;
      backend=new WwiBackend({send(message) {
        if(message==='WEBEEBLOCKS_RUNTIME_V2 HELLO') {
          backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY'); return;
        }
        const match=message.match(/^WEBEEBLOCKS_RUNTIME_V2 REQUEST (\d+) SCENE (sequence-v1|legacy-v1) ([0-9a-f]{64})$/);
        assert(match,'unexpected native scene request: '+message);
        controller.scene=match[2];
        controller.requests.push({backend,id:Number(match[1]),scene:match[2],nonce:match[3]});
      }},{simulationScenes:true,simulationReset:true,simulationStop:true,timeoutMs:1000});
      return backend;
    }, ack(request, payload='OK') {
      request.backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+request.id+' '+(payload==='OK'?'SCENE_OK '+request.nonce:payload));
    }};
  }
  for(const starter of starters.slice(1)) for(const mode of ['template','open']) for(const inverse of [false,true]) {
    const text=fs.readFileSync(path.join(ROOT,'activities/progression',inverse?starters[0]:starter),'utf8');
    const destination=JSON.parse(text).activity.id;
    const source=inverse?JSON.parse(fs.readFileSync(path.join(ROOT,'activities/progression',starter),'utf8')).activity.id:sequence;
    const native=nativeController('legacy-v1'), first=native.attach();
    await first.waitUntilReady();
    const selecting=first.prepareActivity(activityProfile(source));
    if(native.requests.length)native.ack(native.requests.at(-1));
    await selecting;
    assert.strictEqual(native.scene,inverse?'legacy-v1':'sequence-v1');
    const backend=native.attach(); await backend.waitUntilReady();
    assert.strictEqual(backend.sceneIdentity,null,'READY presumed the surviving native scene');
    const workspace=buildWorkspace(0.2), ref={value:Profiles.resolveById(Activities.DOCUMENT,'reactive-obstacle-v2',Activities.BLOCK_CATALOG)};
    const transport=memoryTransport(); transport.state.openText=text;
    let profileChanges=0;
    const manager=ProjectFiles.createManager({Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,
      blockCatalog:Activities.BLOCK_CATALOG,semanticAst:SemanticAst,activityContract:ActivityContract,workspace,
      getProfile:()=>ref.value,setProfile:p=>{profileChanges++;ref.value=p;},transport,
      prepareProfile:p=>backend.prepareActivity(p)});
    await manager.saveAs('original.wbb');
    const before=Blockly.serialization.workspaces.save(workspace), count=native.requests.length;
    let applied=false;
    const opening=(mode==='open'?manager.open():manager.openTemplateText(starter,text)).then(value=>{applied=true;return value;});
    await flush();
    assert.strictEqual(native.requests.length,count+1,'reattachment skipped native selection for '+destination);
    const request=native.requests.at(-1);
    assert.strictEqual(request.scene,inverse?'sequence-v1':'legacy-v1');
    assert.strictEqual(backend.sceneIdentity,null,'unacknowledged scene became known');
    assert.strictEqual(profileChanges,0); assert.strictEqual(applied,false);
    assert.deepStrictEqual(Blockly.serialization.workspaces.save(workspace),before);
    assert.strictEqual(manager.currentName(),'original.wbb'); assert(manager.hasCurrentTarget());
    await assert.rejects(backend.prepareActivity(activityProfile(source)),e=>e.code==='SCENE_BUSY');
    backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+(request.id+999)+' OK');
    await flush(); assert.strictEqual(applied,false,'wrong request ID applied project');
    assert.strictEqual(native.requests.length,count+1,'concurrent preparation was sent');
    native.ack(request); await opening;
    assert.strictEqual(backend.sceneIdentity,native.scene); assert.strictEqual(ref.value.id,destination);
    assert.strictEqual(manager.hasCurrentTarget(),mode==='open');
    assert.strictEqual(manager.currentName(),mode==='open'?'eleve.wbb':null);
    assert.strictEqual(workspace.getAllBlocks(false).length,0);
    // A duplicate old reply cannot change an already established scene.
    native.ack(request,'ERR SCENE_UNAVAILABLE');
    assert.strictEqual(backend.sceneIdentity,native.scene);
    workspace.dispose();
  }
  for(const payload of ['VALUE 1','STATE achieved','ERR SCENE_UNAVAILABLE']) {
    const native=nativeController('sequence-v1'), backend=native.attach(); await backend.waitUntilReady();
    const selecting=backend.prepareActivity(activityProfile('progression-precise-movement-v1'));
    const rejected=assert.rejects(selecting); native.ack(native.requests.at(-1),payload); await rejected;
    assert.strictEqual(backend.sceneIdentity,null,'wrong ACK established a scene');
  }
  // Real production instances restart numeric IDs. Route OLD replies to the
  // CURRENT receiver, as main.js does, before its own native acknowledgement.
  const lateNative=nativeController('legacy-v1'), oldBackend=lateNative.attach();
  await oldBackend.waitUntilReady();
  const oldSelection=oldBackend.prepareActivity(activityProfile(sequence));
  const oldRequest=lateNative.requests.at(-1);
  const current=lateNative.attach(); await current.waitUntilReady();
  const currentSelection=current.prepareActivity(activityProfile('progression-precise-movement-v1'));
  const currentRequest=lateNative.requests.at(-1);
  assert.strictEqual(oldRequest.id,currentRequest.id);
  assert.notStrictEqual(oldRequest.nonce,currentRequest.nonce);
  current.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+oldRequest.id+' OK');
  current.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+oldRequest.id+' SCENE_OK '+oldRequest.nonce);
  await flush(); assert.strictEqual(current.sceneIdentity,null,'foreign connection ACK confirmed scene');
  assert(current.pending[currentRequest.id],'foreign ACK consumed the current request');
  lateNative.ack(currentRequest);await currentSelection;
  assert.strictEqual(current.sceneIdentity,'legacy-v1');
  lateNative.ack(oldRequest);await oldSelection;

  const sent=[], delayed=new WwiBackend({send:m=>sent.push(m)},{simulationScenes:true,simulationStop:true,timeoutMs:30});
  await assert.rejects(delayed.prepareActivity(activityProfile(sequence)),/request timeout/);
  assert.strictEqual(delayed.sceneIdentity,null);
  const retry=delayed.prepareActivity(activityProfile('progression-precise-movement-v1'));
  delayed.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK');
  await flush(); assert.strictEqual(delayed.sceneIdentity,null,'timed-out ACK confirmed later selection');
  delayed.handleMessage(sceneAck(delayed,2)); await retry;
  const preparing=delayed.prepareActivity(activityProfile(sequence));
  const cancelled=assert.rejects(preparing,e=>e.code==='RESET_CANCELLED');
  const stopping=delayed.stopSimulation();
  delayed.handleMessage(sceneAck(delayed,3));
  delayed.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 OK');
  await cancelled; await stopping; assert.strictEqual(delayed.sceneIdentity,null);
  console.log('PASS scene reattachment: 28 Start/Open transitions across activities 1-8, ACK-before-application, targets, concurrency, wrong/late replies, timeout and STOP');
}

async function proveProjectStartupRace() {
  for (const failReady of [false,true]) {
    const listeners = {}, timers = [], elements = {};
    let created = 0, releaseReady, rejectReady;
    const readiness = new Promise((resolve,reject)=>{releaseReady=resolve;rejectReady=reject;});
    const document = {body:{dataset:{}},getElementById:id=>elements[id] || (elements[id]={dataset:{},addEventListener(){}})};
    const context = {
      window:{addEventListener:(name,fn)=>{listeners[name]=fn;},dispatchEvent(){}},document,
      workspace:{},runtimeProfile:{id:'reactive-obstacle-v2'},
      WebeeBlocksProjectFiles:{createBrowserTransport:()=>({nativeFileSystemAccess:true}),
        createManager:()=>{created++;return {nativeFileSystemAccess:true,hasCurrentTarget:()=>false};}},
      Blockly:{},WebeeBlocksActivityProfiles:{},WebeeBlocksActivities:{DOCUMENT:{},BLOCK_CATALOG:{}},
      WebeeBlocksSemanticAst:{},WebeeBlocksActivityContract:{},
      CustomEvent:function(){},console:{error(){},warn(){}},Date,
      setTimeout:fn=>{timers.push(fn);}
    };
    vm.runInNewContext(fs.readFileSync(path.join(ROOT,'plugins/robot_windows/blockly_v2/project_ui.js'),'utf8'),context);
    const flush = async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
    listeners.load(); await flush();
    assert.strictEqual(created,0,'Chrome exposed project loading before Robot Window import');
    context.robotWindow={send(){},receive(){}};
    context.runtimeBackend={waitUntilReady:()=>readiness};
    timers.shift()(); await flush();
    assert.strictEqual(created,0,'Chrome exposed project loading before native READY');
    if(failReady) rejectReady(new Error('native READY failed')); else releaseReady();
    await flush();
    assert.strictEqual(created,failReady?0:1);
    assert.strictEqual(document.body.dataset.projectFileMode,failReady?'unavailable':'browser-native');
    if(failReady)assert.strictEqual(elements.projectOpen.disabled,true);
  }
}

async function expectRejectedWithoutMutation(manager, transport, text, workspace, profileRef, label) {
  const beforeAst = ast(workspace, profileRef.value);
  const beforeState = Blockly.serialization.workspaces.save(workspace);
  transport.state.openText = text;
  let rejected = false;
  try { await manager.open(); } catch (error) { rejected = true; }
  assert(rejected, label + ' must reject');
  assert.deepStrictEqual(ast(workspace, profileRef.value), beforeAst, label + ' changed AST');
  assert.deepStrictEqual(Blockly.serialization.workspaces.save(workspace), beforeState, label + ' changed workspace');
}

function validatePickerOptions(options) {
  assert(options && Array.isArray(options.types) && options.types.length > 0, 'picker types missing');
  for (const type of options.types) {
    for (const [mime, extensions] of Object.entries(type.accept || {})) {
      assert(/^[^/]+\/[^/]+$/.test(mime), 'invalid picker MIME type');
      for (const extension of extensions) {
        // Chrome rejects overlong native suffixes before any WebeeBlocks
        // interpretation. Keep this check first so the historical
        // `.webeeblocks.json` regression is causally represented, then still
        // validate the syntax of all suffixes that fit the native limit.
        assert(Array.from(extension).length <= 16, 'picker extension exceeds native limit');
        assert(/^\.[A-Za-z0-9]+$/.test(extension), 'invalid picker extension ' + extension);
      }
    }
  }
}

function fakeNativeBrowser() {
  const state = {options:[], writes:0, bytes:'', nextOpenName:'eleve.wbb'};
  const handle = {
    name:'eleve.wbb',
    async createWritable() {
      return {
        async write(text) { state.bytes = String(text); state.writes += 1; },
        async close() {},
        async abort() { throw new Error('successful write was unexpectedly aborted'); }
      };
    },
    async getFile() { return {name:state.nextOpenName, text:async () => state.bytes}; }
  };
  const browserWindow = {
    async showSaveFilePicker(options) {
      validatePickerOptions(options);
      state.options.push({kind:'save', options});
      return handle;
    },
    async showOpenFilePicker(options) {
      validatePickerOptions(options);
      state.options.push({kind:'open', options});
      return [handle];
    }
  };
  return {state, handle, browserWindow};
}

async function exerciseBrowserBoundary() {
  assert.throws(() => validatePickerOptions({
    types:[{accept:{'application/json':['.webeeblocks.json']}}]
  }), /native limit/, 'historical compound suffix must be rejected');

  const fake = fakeNativeBrowser();
  const transport = ProjectFiles.createBrowserTransport(fake.browserWindow, {});
  assert.strictEqual(transport.nativeFileSystemAccess, true);
  const saved = await transport.saveAs('eleve.webeeblocks.json', '{"ok":1}');
  assert.strictEqual(saved.name, 'eleve.wbb');
  assert.strictEqual(fake.state.writes, 1);
  const saveOptions = fake.state.options[0].options;
  assert.strictEqual(saveOptions.suggestedName, 'eleve.wbb');
  assert.deepStrictEqual(saveOptions.types[0].accept, {'application/json':['.wbb']});

  for (const name of ['projet.wbb','ancien.webeeblocks.json','legacy.json']) {
    fake.state.nextOpenName = name;
    const opened = await transport.open();
    assert.strictEqual(opened.name, name, 'opened OS filename must be preserved exactly');
  }
  const openOptions = fake.state.options.find(entry => entry.kind === 'open').options;
  assert.deepStrictEqual(openOptions.types[0].accept, {'application/json':['.wbb','.json']});
  await transport.save(fake.handle, 'eleve.wbb', '{"ok":2}');
  assert.strictEqual(fake.state.writes, 2, 'Save must write the selected handle');

  const unavailable = ProjectFiles.createBrowserTransport({}, {});
  assert.strictEqual(unavailable.nativeFileSystemAccess, false);
  await assert.rejects(unavailable.open(), /use Google Chrome/);
  await assert.rejects(unavailable.saveAs('x', '{}'), /use Google Chrome/);
  assert(!ProjectFiles.createBrowserTransport.toString().includes('Blob'), 'Blob fallback must not exist');
  assert(!ProjectFiles.createBrowserTransport.toString().includes("createElement('input')"), 'input upload fallback must not exist');
}

async function exerciseBrowserWriteAtomicity() {
  // Native File System Access uses a temporary file until close(). A write
  // failure must never close/commit partial bytes over a student's old .wbb.
  for (const operation of ['saveAs', 'save']) {
    for (const failAt of ['write', 'close']) {
      for (const abortFails of [false, true]) {
        const oldBytes = 'previous valid student project';
        let disk = oldBytes;
        let staged = null;
        const events = [];
        const primary = new Error('simulated ' + failAt + ' failure');
        const secondary = new Error('simulated abort failure');
        const handle = {
          name: 'eleve.wbb',
          async createWritable() {
            staged = disk;
            return {
              async write(text) {
                events.push('write');
                staged = String(text).slice(0, 7);
                if (failAt === 'write') throw primary;
              },
              async close() {
                events.push('close');
                if (failAt === 'close') throw primary;
                disk = staged; // Closing after a failed write would corrupt it.
              },
              async abort() {
                events.push('abort');
                if (abortFails) throw secondary;
                staged = null;
              }
            };
          }
        };
        const transport = ProjectFiles.createBrowserTransport({
          async showSaveFilePicker() { return handle; },
          async showOpenFilePicker() { return [handle]; }
        }, {});
        const saving = operation === 'saveAs'
          ? transport.saveAs('eleve.wbb', 'replacement project')
          : transport.save(handle, 'eleve.wbb', 'replacement project');
        await assert.rejects(saving, error => {
          assert.strictEqual(error, primary, 'abort masked the original write/close failure');
          if (abortFails) assert.strictEqual(error.abortError, secondary);
          return true;
        });
        assert.strictEqual(disk, oldBytes, 'failed write committed partial bytes');
        assert.deepStrictEqual(events, failAt === 'write'
          ? ['write', 'abort'] : ['write', 'close', 'abort'],
          'failed write must abort, never close afterward');
      }
    }
  }

  for (const operation of ['saveAs', 'save']) {
    // A frozen host exception must retain its identity if abort also rejects.
    const primary = Object.freeze(new Error('immutable file write failure'));
    let abortCalled = 0, closeCalled = 0;
    const handle = {
      name: 'eleve.wbb',
      async createWritable() {
        return {
          async write() { throw primary; },
          async close() { closeCalled++; },
          async abort() { abortCalled++; throw new Error('secondary abort failure'); }
        };
      }
    };
    const transport = ProjectFiles.createBrowserTransport({
      async showSaveFilePicker() { return handle; },
      async showOpenFilePicker() { return [handle]; }
    }, {});
    await assert.rejects(operation === 'saveAs'
      ? transport.saveAs('eleve.wbb', '{}')
      : transport.save(handle, 'eleve.wbb', '{}'), error => error === primary,
    'secondary abort failure must not mask an immutable write failure');
    assert.strictEqual(abortCalled, 1);
    assert.strictEqual(closeCalled, 0, 'failed immutable write closed the target');
  }

  for (const missingMethod of ['write', 'close', 'abort']) {
    let unexpectedWrites = 0;
    const incompleteHandle = {
      name: 'eleve.wbb',
      async createWritable() {
        const stream = {
          async write() { unexpectedWrites++; },
          async close() { unexpectedWrites++; },
          async abort() { unexpectedWrites++; }
        };
        delete stream[missingMethod];
        return stream;
      }
    };
    const transport = ProjectFiles.createBrowserTransport({
      async showSaveFilePicker() { return incompleteHandle; },
      async showOpenFilePicker() { return [incompleteHandle]; }
    }, {});
    await assert.rejects(transport.saveAs('eleve.wbb', '{}'),
      /transactional file stream unavailable/, 'incomplete stream must fail closed');
    assert.strictEqual(unexpectedWrites, 0,
      'stream missing ' + missingMethod + ' was allowed to write/close');
  }

  console.log('PASS browser atomic Save/Save As: failed write/close aborts, original error and bytes preserved, no non-transactional fallback');
}

async function exerciseWwiBusyDiscovery() {
  const sent = [];
  let transport;
  const robotWindow = {send(message) {
    sent.push(String(message));
    const id = sent.at(-1).match(/REQUEST (\d+)/)[1];
    if (!sent.at(-1).endsWith(' CAPABILITIES')) return;
    const payload = sent.length <= 2 ? 'ERR BUSY' :
      'CAPABILITIES {"protocol":1,"provider":"qt6-native-dialog","operationsReady":true,"sameFileSave":true,"canonicalExtension":".wbb"}';
    Promise.resolve().then(() => transport.handleMessage(
      `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} ${payload}`));
  }};
  transport = new WwiProjectFileTransport(robotWindow, {timeoutMs:1000});
  const ready = transport.waitUntilReady();
  assert.strictEqual(transport.waitUntilReady(), ready, 'bootstrap must stay shared while BUSY');
  await ready;
  assert.strictEqual(sent.length, 3, 'retry discovery after each BUSY and stop at rest');
  assert(sent.every(message => message.endsWith(' CAPABILITIES')), 'discovery must not replay file effects');
  assert.strictEqual(transport.waitUntilReady(), ready, 'successful discovery remains cached');

  let failing;
  let failedRequests = 0;
  failing = new WwiProjectFileTransport({send(message) {
    failedRequests++;
    const id = String(message).match(/REQUEST (\d+)/)[1];
    Promise.resolve().then(() => failing.handleMessage(
      `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} ERR UNAVAILABLE`));
  }}, {timeoutMs:1000});
  await assert.rejects(failing.waitUntilReady(), error => error && error.code === 'UNAVAILABLE');
  assert.strictEqual(failedRequests, 1, 'only BUSY permits a discovery retry');

  for (const request of [
    () => transport.open(),
    () => transport.saveAs('probe.wbb', '{}'),
    () => transport.save({kind:'wwi',reference:'existing'}, 'probe.wbb', '{}')
  ]) {
    const before = sent.length;
    const pending = request();
    await Promise.resolve();
    const id = sent.at(-1).match(/REQUEST (\d+)/)[1];
    transport.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} ERR BUSY`);
    await assert.rejects(pending, error => error && error.code === 'BUSY');
    await new Promise(resolve => setTimeout(resolve, 300));
    assert.strictEqual(sent.length, before + 1, 'refused file effects must never be replayed');
  }
}

async function exerciseWwiDiscoveryRecovery() {
  const capabilities = 'CAPABILITIES {"protocol":1,"provider":"qt6-native-dialog","operationsReady":true,"sameFileSave":true,"canonicalExtension":".wbb"}';
  const requests = [];
  let available = false;
  let transport;
  transport = new WwiProjectFileTransport({send(message) {
    requests.push(message);
    const match = String(message).match(/^WEBEEBLOCKS_FILE_BROKER_V1 REQUEST (\d+) CAPABILITIES$/);
    assert(match, 'discovery must never replay file operations');
    Promise.resolve().then(() => transport.handleMessage(
      `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${match[1]} ${available ? capabilities : 'ERR UNAVAILABLE'}`));
  }}, {timeoutMs:1000});

  const first = transport.waitUntilReady();
  assert.strictEqual(transport.waitUntilReady(), first, 'concurrent discovery shares one attempt');
  await assert.rejects(first, error => error && error.code === 'UNAVAILABLE');
  assert.strictEqual(requests.length, 1, 'failure must not trigger automatic retry');

  // A later explicit Open/Save should be able to rediscover a recovered broker.
  available = true;
  const second = transport.waitUntilReady();
  assert.notStrictEqual(second, first, 'a failed discovery must not poison all future operations');
  await second;
  assert.strictEqual(requests.length, 2, 'explicit retry must issue a fresh discovery');
  assert.strictEqual(transport.waitUntilReady(), second, 'successful discovery remains cached');

  // A malformed/insufficient capability advertisement must not be cached as
  // a permanent failure either. The native response is rechecked on request.
  let advertisementCount = 0;
  let incomplete;
  incomplete = new WwiProjectFileTransport({send(message) {
    advertisementCount++;
    const match = String(message).match(/^WEBEEBLOCKS_FILE_BROKER_V1 REQUEST (\d+) CAPABILITIES$/);
    assert(match);
    const payload = advertisementCount === 1 ?
      'CAPABILITIES {"protocol":1,"operationsReady":false}' : capabilities;
    Promise.resolve().then(() => incomplete.handleMessage(
      `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${match[1]} ${payload}`));
  }}, {timeoutMs:1000});
  await assert.rejects(incomplete.waitUntilReady(), error => error && error.code === 'CAPABILITY_UNAVAILABLE');
  await incomplete.waitUntilReady();
  assert.strictEqual(advertisementCount, 2, 'capability mismatch must be recoverable by explicit discovery');

  // A lost reply may arrive after the timeout: its old ID must not qualify
  // the next attempt or cause any file operation to be retried.
  let afterTimeout;
  const timedRequests = [];
  afterTimeout = new WwiProjectFileTransport({send(message) {
    timedRequests.push(message);
    const match = String(message).match(/^WEBEEBLOCKS_FILE_BROKER_V1 REQUEST (\d+) CAPABILITIES$/);
    assert(match);
    if (timedRequests.length === 2) Promise.resolve().then(() => {
      const oldId = Number(match[1]) - 1;
      afterTimeout.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${oldId} ERR UNAVAILABLE`);
      assert(afterTimeout.pending[match[1]], 'stale reply consumed the current discovery');
      afterTimeout.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${match[1]} ${capabilities}`);
    });
  }}, {timeoutMs:25});
  await assert.rejects(afterTimeout.waitUntilReady(), error => error && error.code === 'TIMEOUT');
  assert.strictEqual(timedRequests.length, 1, 'timeout must not trigger automatic retry');
  await afterTimeout.waitUntilReady();
  assert.strictEqual(timedRequests.length, 2, 'explicit retry after timeout must reach broker');
  assert(timedRequests.every(message => message.endsWith(' CAPABILITIES')));
}

async function exerciseWwiBoundary() {
  const sent = [];
  const robotWindow = {send(message) { sent.push(String(message)); }};
  const transport = new WwiProjectFileTransport(robotWindow, {timeoutMs:1000});
  assert.strictEqual(transport.nativeFileSystemAccess, true);
  assert.strictEqual(transport.mode, 'wwi-native');

  function requestId() {
    const match = sent.at(-1).match(/^WEBEEBLOCKS_FILE_BROKER_V1 REQUEST (\d+) /);
    assert(match, sent.at(-1));
    return match[1];
  }

  let pending = transport.waitUntilReady();
  let id = requestId();
  assert(transport.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} CAPABILITIES {"protocol":1,"provider":"qt6-native-dialog","operationsReady":true,"sameFileSave":true,"canonicalExtension":".wbb"}`));
  await pending;

  const openedText = '{"format":"webeeblocks-project"}\n';
  pending = transport.open();
  await Promise.resolve();
  id = requestId();
  transport.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} OPEN OK opaque_open_1 ${WwiProjectFileTransport.encodeText('élève.wbb')} ${WwiProjectFileTransport.encodeText(openedText)}`);
  const opened = await pending;
  assert.deepStrictEqual(opened.handle, {kind:'wwi',reference:'opaque_open_1'});
  assert.strictEqual(opened.name, 'élève.wbb');
  assert.strictEqual(opened.text, openedText);

  pending = transport.saveAs('élève.wbb', '{"ok":2}\n');
  await Promise.resolve();
  id = requestId();
  assert(sent.at(-1).includes(' SAVE_AS '));
  assert(!sent.at(-1).includes('{"ok":2}'), 'WWI request leaked raw project bytes');
  transport.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} SAVE_AS OK opaque_saveas_2 ${WwiProjectFileTransport.encodeText('élève.wbb')}`);
  const saved = await pending;
  assert.deepStrictEqual(saved.handle, {kind:'wwi',reference:'opaque_saveas_2'});

  pending = transport.save(saved.handle, saved.name, '{"ok":3}\n');
  await Promise.resolve();
  id = requestId();
  assert(sent.at(-1).includes(' SAVE opaque_saveas_2 '), 'Save did not reuse opaque same-file reference');
  transport.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} SAVE OK opaque_saveas_2 ${WwiProjectFileTransport.encodeText('élève.wbb')}`);
  const resaved = await pending;
  assert.deepStrictEqual(resaved.handle, saved.handle);

  pending = transport.open();
  await Promise.resolve();
  id = requestId();
  transport.handleMessage(`WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} OPEN CANCELLED`);
  await assert.rejects(pending, error => error && error.name === 'AbortError');

  await assert.rejects(transport.save({kind:'wwi',reference:'../path'}, 'x.wbb', '{}'), error => error && error.code === 'TARGET_UNAVAILABLE');
  assert.strictEqual(transport.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY'), false, 'broker consumed runtime traffic');
}

// #826: real Blockly 13, .wbb manager and AST roundtrip for the stable
// variable-course activity profile. Host route switching, native Webots and
// OS file dialogs are NOT exercised by this test.
async function proveVariableProfileRealBlocklyRoundTrip() {
  const source = fs.readFileSync(path.join(ROOT,
    'plugins/robot_windows/grand_prix_route_v2/setup.js'), 'utf8');
  const context = {
    WebeeBlocksActivities: {BLOCK_CATALOG:Activities.BLOCK_CATALOG, DOCUMENT:Activities.DOCUMENT},
    WebeeBlocksRuntimeOutcome: {classify:() => null},
    Blockly: {inject:(_element, options) => options},
    WebeeBlocksWwiBackend: function() {}
  };
  context.window = context;
  vm.runInNewContext(source, context);
  const document = context.WebeeBlocksActivities.DOCUMENT;
  const profile = Profiles.resolveById(document, context.WebeeBlocksInitialActivityId,
    Activities.BLOCK_CATALOG);
  assert.strictEqual(profile.id, 'progression-grand-prix-route-v2');
  assert.strictEqual(profile.world, 'worlds/grand_prix_route_v2.wbt');

  const transport = memoryTransport();
  const profileRef = {value:profile};
  const create = workspace => ProjectFiles.createManager({
    Blockly, profiles:Profiles, activitiesDocument:document,
    blockCatalog:Activities.BLOCK_CATALOG,
    semanticAst:SemanticAst, activityContract:ActivityContract,
    workspace, getProfile:()=>profileRef.value,
    setProfile:p=>{profileRef.value=p;}, transport
  });
  const original = buildWorkspace(0.3);
  const initialAst = ast(original, profile);
  const manager = create(original);
  assert.strictEqual(manager.hasCurrentTarget(), false);
  await manager.saveAs('grand-prix-variable');
  await manager.save();
  const bytes = transport.state.currentText;
  const project = ProjectFiles.parseProject(bytes);
  assert.deepStrictEqual(Object.keys(project.activity).sort(), ['id', 'semantics']);
  assert.strictEqual(project.activity.id, profile.id);

  // Recreate the editor with the same logical profile and stored file.
  // Host-course selection is a distinct, not-yet-tested integration boundary.
  const reopenedWorkspace = new Blockly.Workspace();
  const reopened = create(reopenedWorkspace);
  transport.state.openText = bytes;
  await reopened.open();
  assert.strictEqual(reopened.hasCurrentTarget(), true);
  assert.deepStrictEqual(ast(reopenedWorkspace, profileRef.value), initialAst);
  await reopened.save();
  assert.strictEqual(transport.state.currentText, bytes,
    'Save after real Blockly Open changed the same .wbb without an edit');

  // A historical U project is a different profile: reject it atomically,
  // preserving the editable workspace and current Save target.
  const before = Blockly.serialization.workspaces.save(reopenedWorkspace);
  transport.state.openText = ProjectFiles.createStarterText('progression-grand-prix-u-v1');
  await assert.rejects(()=>reopened.open(), /exactly once/);
  assert.deepStrictEqual(Blockly.serialization.workspaces.save(reopenedWorkspace), before);
  assert.strictEqual(reopened.hasCurrentTarget(), true);
  assert.strictEqual(transport.state.currentText, bytes);
  original.dispose();
  reopenedWorkspace.dispose();
}

// Real Blockly 13 profile and project-file boundary for the new school A2.
// Native Webots collision/success remains a distinct independent CI witness.
async function proveAltitudeBlocklyProjectRoundTrip(){
  const profile=activityProfile('progression-altitude-v1');
  const w=new Blockly.Workspace();
  const takeoff=w.newBlock('webeeblocks_v2_takeoff');
  const speed=w.newBlock('webeeblocks_v2_speed');
  const forward1=w.newBlock('webeeblocks_v2_move');
  const climb=w.newBlock('webeeblocks_v2_vertical');
  const forward2=w.newBlock('webeeblocks_v2_move');
  const land=w.newBlock('webeeblocks_v2_land');
  setMotionNumber(takeoff,'HEIGHT',0.45);
  speed.setFieldValue('0.14','SPEED');
  forward1.setFieldValue('forward','DIRECTION');
  setMotionNumber(forward1,'DISTANCE',0.32);
  climb.setFieldValue('up','DIRECTION');
  setMotionNumber(climb,'DISTANCE',0.36);
  forward2.setFieldValue('forward','DIRECTION');
  setMotionNumber(forward2,'DISTANCE',1.03);
  const nodes=[takeoff,speed,forward1,climb,forward2,land];
  for(let i=0;i<nodes.length-1;i++)
    nodes[i].nextConnection.connect(nodes[i+1].previousConnection);
  // In the real activity chooser, profile-specific FieldNumber constraints are
  // installed before pupils edit speed. The generic block rounds at 0.1 m/s;
  // Activity 2 explicitly permits 0.01 so the witnessed 0.14 is representable.
  ActivityContract.applyFieldBounds(profile,w);
  speed.setFieldValue('0.14','SPEED');
  assert.strictEqual(Number(speed.getFieldValue('SPEED')),0.14);
  const compiled=ast(w,profile);
  assert.deepStrictEqual(compiled.program,[
    {kind:'takeoff',height_m:0.45},{kind:'set_speed',speed_m_s:0.14},
    {kind:'move',direction:'forward',distance_m:0.32},
    {kind:'vertical',direction:'up',distance_m:0.36},
    {kind:'move',direction:'forward',distance_m:1.03},{kind:'land'}
  ]);
  const state={value:profile},transport=memoryTransport(),manager=managerFor(w,state,transport);
  assert.strictEqual(manager.hasCurrentTarget(),false);
  await assert.rejects(manager.save(),/no current file/);
  await manager.saveAs('altitude-eleve');
  assert.strictEqual(manager.hasCurrentTarget(),true);
  const original=transport.state.currentText;
  assert.strictEqual(ProjectFiles.parseProject(original).activity.id,profile.id);
  assert.strictEqual(transport.state.writes.length,1);
  forward2.getInputTargetBlock('DISTANCE').setFieldValue('0.9','NUM');
  transport.state.openText=original;
  await manager.open();
  assert.deepStrictEqual(ast(w,state.value),compiled,'real Blockly A2 Save As/Open AST drift');
  assert.strictEqual(manager.hasCurrentTarget(),true);
  assert.strictEqual(transport.state.writes.length,1,'Open caused hidden Save');
  const newForward=w.getBlocksByType('webeeblocks_v2_move',false).find(
    b=>Math.abs(Number(b.getInputTargetBlock('DISTANCE').getFieldValue('NUM'))-1.03)<1e-8);
  assert(newForward,'A2 second move missing after Open');
  newForward.getInputTargetBlock('DISTANCE').setFieldValue('1.0','NUM');
  const changed=ast(w,state.value);
  await manager.save();
  const saved=transport.state.currentText;
  assert.strictEqual(transport.state.writes.at(-1).kind,'save');
  transport.state.openText=saved;
  await manager.open();
  assert.deepStrictEqual(ast(w,state.value),changed,'real Blockly A2 same-file Save/Open drift');
  // Old pupils' precise-movement project must remain reopenable; no silent
  // remapping to altitude-v1, even after the new starter is displayed.
  transport.state.openText=ProjectFiles.createStarterText('progression-precise-movement-v1');
  await manager.open();
  assert.strictEqual(state.value.id,'progression-precise-movement-v1');
  assert.strictEqual(state.value.runtime.scene,'legacy-v1');
  assert.strictEqual(state.value.evaluation.oracle,'progression-precise-movement-v1');
  assert.strictEqual(manager.hasCurrentTarget(),true);
  assert.strictEqual(transport.state.writes.length,2,'old project Open was auto-saved');
  // New starter is a fresh template without a Save target.
  await manager.openTemplateText('progression-altitude-v1.wbb',
    ProjectFiles.createStarterText('progression-altitude-v1'));
  assert.strictEqual(state.value.id,profile.id);
  assert.strictEqual(manager.hasCurrentTarget(),false);
  await assert.rejects(manager.save(),/no current file/);
  w.dispose();
}

(async function() {
  await proveAltitudeBlocklyProjectRoundTrip();
  await proveVariableProfileRealBlocklyRoundTrip();
  await exerciseBrowserBoundary();
  await exerciseBrowserWriteAtomicity();
  await exerciseWwiBoundary();
  await exerciseWwiBusyDiscovery();
  await exerciseWwiDiscoveryRecovery();
  assert.strictEqual(ProjectFiles.EXTENSION, '.wbb');
  assert.strictEqual(ProjectFiles.normalizeName('eleve'), 'eleve.wbb');
  assert.strictEqual(ProjectFiles.normalizeName('eleve.webeeblocks.json'), 'eleve.wbb');
  assert.strictEqual(ProjectFiles.normalizeName('eleve.json'), 'eleve.wbb');

  const profileRef = {value:Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG)};
  const liveWorkspace = buildWorkspace(0.3);
  const transport = memoryTransport();
  const manager = managerFor(liveWorkspace, profileRef, transport);

  const initialAst = ast(liveWorkspace, profileRef.value);
  assert.strictEqual(manager.hasCurrentTarget(), false);
  await assert.rejects(manager.save(), /no current file/);
  assert.strictEqual(transport.state.writes.length, 0, 'Save without target reached transport');
  const saved = await manager.saveAs('eleve');
  assert.strictEqual(manager.hasCurrentTarget(), true);
  assert.strictEqual(saved.name, 'eleve.wbb');
  assert.strictEqual(transport.state.writes.length, 1);
  const project = JSON.parse(transport.state.currentText);
  assert.deepStrictEqual(Object.keys(project).sort(), ['activity','format','version','workspace']);
  assert.deepStrictEqual(Object.keys(project.activity).sort(), ['id','semantics']);
  assert.strictEqual(project.format, 'webeeblocks-project');
  assert.strictEqual(project.version, 1);
  assert.strictEqual(project.activity.id, 'reactive-obstacle-v2');
  assert.strictEqual(project.activity.semantics, 'webeeblocks-ast-v1');
  ['identity','attempt','result','score','debug','progress','history'].forEach(word => {
    assert(!transport.state.currentText.toLowerCase().includes('"' + word), 'forbidden project data: ' + word);
  });

  // Editing/compiling is deliberately persistence-inert.
  liveWorkspace.getBlocksByType('webeeblocks_v2_move', false)[0].getInputTargetBlock('DISTANCE').setFieldValue('0.8','NUM');
  ast(liveWorkspace, profileRef.value);
  assert.strictEqual(transport.state.writes.length, 1, 'workspace edit caused implicit persistence write');

  // Re-open the explicit Save As bytes and recover the exact full AST.
  transport.state.openText = transport.state.currentText;
  await manager.open();
  assert.deepStrictEqual(ast(liveWorkspace, profileRef.value), initialAst, 'round-trip AST differs');

  // Explicit Save updates the same chosen target; no hidden version/history file exists.
  liveWorkspace.getBlocksByType('webeeblocks_v2_move', false)[0].getInputTargetBlock('DISTANCE').setFieldValue('0.7','NUM');
  const editedAst = ast(liveWorkspace, profileRef.value);
  const writesBeforeSave = transport.state.writes.length;
  await manager.save();
  assert.strictEqual(transport.state.writes.length, writesBeforeSave + 1, 'explicit Save did not write once');
  assert.strictEqual(transport.state.writes.at(-1).kind, 'save');
  transport.state.openText = transport.state.currentText;
  liveWorkspace.getBlocksByType('webeeblocks_v2_move', false)[0].getInputTargetBlock('DISTANCE').setFieldValue('0.4','NUM');
  await manager.open();
  assert.deepStrictEqual(ast(liveWorkspace, profileRef.value), editedAst, 'Save bytes did not restore edited AST');

  const validText = manager.encodeCurrent();
  await expectRejectedWithoutMutation(manager, transport, '{bad json', liveWorkspace, profileRef, 'malformed JSON');
  const unknownVersion = JSON.parse(validText); unknownVersion.version = 999;
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(unknownVersion), liveWorkspace, profileRef, 'unknown version');
  const unknownActivity = JSON.parse(validText); unknownActivity.activity.id = 'unknown-profile';
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(unknownActivity), liveWorkspace, profileRef, 'unknown activity');
  const extraHistory = JSON.parse(validText); extraHistory.history = [{score:1}];
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(extraHistory), liveWorkspace, profileRef, 'unsupported history field');
  const invalidWorkspace = JSON.parse(validText); invalidWorkspace.workspace = {blocks:{languageVersion:0,blocks:[{type:'does_not_exist'}]}};
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(invalidWorkspace), liveWorkspace, profileRef, 'invalid workspace');
  const injectedProfile = Profiles.resolveById(Activities.DOCUMENT, 'progression-sequence-v1', Activities.BLOCK_CATALOG);
  const injected = {
    format:'webeeblocks-project',
    version:1,
    activity:{id:injectedProfile.id,semantics:'webeeblocks-ast-v1'},
    workspace:{blocks:{languageVersion:0,blocks:[{type:'webeeblocks_v2_move',fields:{DIRECTION:'right'},inputs:{DISTANCE:{block:{type:'math_number',fields:{NUM:0.3}}}}}]}}
  };
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(injected), liveWorkspace, profileRef, 'hidden dropdown injection');
  assert.strictEqual(transport.state.writes.length, writesBeforeSave + 1, 'failed opens caused persistence writes');

  // Starting a packaged activity is template import, not Open: the selected
  // starter and any previous project target are released, so Save cannot
  // overwrite either one. The student must explicitly choose Save As.
  transport.state.openText = fs.readFileSync(path.join(ROOT, 'activities/progression/01-sequence.wbb'), 'utf8');
  const releasesBeforeTemplate = transport.state.releases.length;
  const templateResult = await manager.openTemplate();
  assert.strictEqual(templateResult.ast, null, 'empty activity starter unexpectedly compiled as executable AST');
  assert.strictEqual(profileRef.value.id, 'progression-sequence-v1', 'activity starter did not apply its declared profile');
  assert.strictEqual(liveWorkspace.getAllBlocks(false).length, 0, 'activity starter did not restore its workspace');
  assert.strictEqual(manager.hasCurrentTarget(), false, 'activity starter was adopted as the student save target');
  assert.strictEqual(transport.state.releases.length, releasesBeforeTemplate + 1, 'activity starter target was not released');
  await assert.rejects(manager.save(), /no current file/, 'Save after activity start must require Save As');
  const writesBeforeTemplateSaveAs = transport.state.writes.length;
  await manager.saveAs('mon-activite');
  assert.strictEqual(manager.hasCurrentTarget(), true, 'Save As after activity start did not establish a student target');
  assert.strictEqual(transport.state.writes.length, writesBeforeTemplateSaveAs + 1, 'Save As after activity start did not write exactly once');

  // A student must be able to save unfinished work. It is a valid project even
  // though it is not yet a valid executable flight AST.
  const incompleteProfile = {value:Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG)};
  const incomplete = new Blockly.Workspace();
  const takeoffOnly = incomplete.newBlock('webeeblocks_v2_takeoff');
  setMotionNumber(takeoffOnly,'HEIGHT',0.8);
  const incompleteTransport = memoryTransport();
  const incompleteManager = managerFor(incomplete, incompleteProfile, incompleteTransport);
  await incompleteManager.saveAs('en-cours');
  assert.strictEqual(incompleteTransport.state.writes.length, 1, 'incomplete project was not explicitly saved');
  const incompleteBytes = incompleteTransport.state.currentText;
  incomplete.clear();
  incompleteTransport.state.openText = incompleteBytes;
  const reopenedIncomplete = await incompleteManager.open();
  assert.strictEqual(reopenedIncomplete.ast, null, 'incomplete project unexpectedly compiled as executable AST');
  assert.strictEqual(incomplete.getBlocksByType('webeeblocks_v2_takeoff', false).length, 1, 'incomplete workspace was not restored');
  assert.strictEqual(incompleteTransport.state.writes.length, 1, 'opening incomplete project caused a write');

  const uiSource = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
  assert(uiSource.includes("error.name === 'AbortError'"), 'UI must treat native cancellation neutrally');
  assert(uiSource.includes('!manager.hasCurrentTarget()'), 'UI must disable Save without a current handle');
  assert(uiSource.includes('manager.openTemplate()'), 'UI must expose activity starters as non-target templates');
  assert(uiSource.includes("getElementById('projectActivity')"), 'UI must expose a discoverable activity-start action');
  assert(uiSource.includes('createDirectTransport'), 'UI must select a direct browser-or-WWI transport');
  assert(uiSource.includes('project_file_wwi_transport.js'), 'UI must load local WWI transport for Firefox');
  assert(!uiSource.includes('utilisez Google Chrome'), 'UI must not hard-code Chrome as the only direct-file browser');
  assert(!uiSource.includes('Nouvelle copie'), 'UI must not advertise download copies');
  await proveScenePreparation();
  await proveSceneReattachment();
  await proveSceneRollback();
  await proveProjectStartupRace();
  console.log('PASS project-files: Chrome+WWI direct .wbb/options/same-handle/templates/state/fail-closed/profile-field-injection/no-fallback/no-autosave/scene-ACK-before-project-mutation');
})().catch(error => { console.error(error); process.exit(1); });
