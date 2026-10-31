'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const WwiProjectFileTransport = require('../../plugins/robot_windows/blockly/webeeblocks/project_file_wwi_transport.js');

async function testR3ClaimProtocol() {
  const p='WEBEEBLOCKS_RUNTIME_V2 ',sent=[];
  const a=new WwiBackend({send:m=>sent.push(m)},{timeoutMs:1000});
  const b=new WwiBackend({send:m=>sent.push(m)},{timeoutMs:1000});
  assert.notStrictEqual(a.authorityKey,b.authorityKey);
  await assert.rejects(a.setLight('blue'),e=>e.code==='AUTH_REQUIRED');
  const firstEpoch='a'.repeat(32), secondEpoch='b'.repeat(32);
  const claimed=a.claimAuthority();
  let m=sent.at(-1).match(/REQUEST (\d+) AUTH_EPOCH ([0-9a-f]{64})$/);
  assert(m, 'must request a correlated native epoch before claim');
  a.handleMessage(p+'RESPONSE '+m[1]+' AUTH_EPOCH '+'0'.repeat(64)+' '+firstEpoch);
  assert.strictEqual(a.authorized,false,'stale epoch correlation granted authority');
  a.handleMessage(p+'RESPONSE '+m[1]+' AUTH_EPOCH '+m[2]+' '+firstEpoch);
  await Promise.resolve();
  const claim=sent.at(-1).match(/REQUEST (\d+) AUTH_CLAIM ([0-9a-f]{64}) ([0-9a-f]{64})$/);
  assert(claim && claim[2]===a.authorityKey && claim[2].startsWith(firstEpoch));
  a.handleMessage(p+'RESPONSE '+claim[1]+' AUTH_OK '+'0'.repeat(64));
  assert.strictEqual(a.authorized,false);
  a.handleMessage(p+'RESPONSE '+claim[1]+' AUTH_OK '+claim[3]);
  await claimed;
  const stale=a.authorityKey;
  const light=a.setLight('red');
  const lightMessage=sent.at(-1).match(/ REQUEST (\d+) AUTH ([0-9a-f]{64}) LIGHT red$/);
  assert(lightMessage && lightMessage[2]===stale);
  a.handleMessage(p+'RESPONSE '+lightMessage[1]+' OK');
  await light;
  const denied=b.claimAuthority();
  m=sent.at(-1).match(/REQUEST (\d+) AUTH_EPOCH ([0-9a-f]{64})$/);
  assert(m);
  b.handleMessage(p+'RESPONSE '+m[1]+' AUTH_EPOCH '+m[2]+' '+secondEpoch);
  await Promise.resolve();
  const n=sent.at(-1).match(/REQUEST (\d+) AUTH_CLAIM ([0-9a-f]{64}) ([0-9a-f]{64})$/);
  assert(n && n[2].startsWith(secondEpoch) && n[2]!==stale,
    'new C incarnation must not reuse old bearer');
  b.handleMessage(p+'RESPONSE '+n[1]+' ERR AUTH_DENIED');
  await assert.rejects(denied,e=>e.code==='AUTH_DENIED');
  assert.strictEqual(b.authorized,false);
  assert.notStrictEqual(firstEpoch,secondEpoch);
}

async function testBackendReadyHandshake() {
  const sent = [];
  const backend = new WwiBackend({send: message => sent.push(String(message))}, {timeoutMs: 1000});

  const first = backend.waitUntilReady();
  const second = backend.waitUntilReady();
  assert.deepStrictEqual(sent, ['WEBEEBLOCKS_RUNTIME_V2 HELLO'],
    'concurrent readiness waiters must share one non-effect liveness probe');
  assert.strictEqual(backend.readyWaiters.length, 2);

  assert.strictEqual(backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY HELLO'), true);
  await Promise.all([first, second]);
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(backend.readyWaiters.length, 0);

  const sentBeforeReadyNoop = sent.length;
  await backend.waitUntilReady();
  assert.strictEqual(sent.length, sentBeforeReadyNoop,
    'already-ready backend must not emit a new liveness probe');
}

async function testHelloReplyDoesNotForgeRestart() {
  const prefix = 'WEBEEBLOCKS_RUNTIME_V2 ';
  for (const replyBeforeAck of [true, false]) {
    const sent = [];
    const backend = new WwiBackend({send:m=>sent.push(m)}, {
      simulationScenes:true, simulationReset:true, timeoutMs:1000
    });
    backend.authorized = true; // Mock C grant for legacy liveness oracle.
    backend.handleMessage(prefix + 'READY HELLO');
    assert.strictEqual(backend.ready, false, 'unsolicited liveness reply created readiness');
    const ready = backend.waitUntilReady();
    backend.handleMessage(prefix + 'READY');
    await ready;
    const epoch = backend.timeObservationEpoch;
    const scene = backend.prepareActivity({id:'progression-sequence-v1', runtime:{scene:'sequence-v1'}});
    const request = sent[1].match(/REQUEST (\d+) AUTH [0-9a-f]{64} SCENE sequence-v1 ([0-9a-f]{64})$/);
    assert(request);
    if (replyBeforeAck) backend.handleMessage(prefix + 'READY HELLO');
    backend.handleMessage(prefix + 'RESPONSE ' + request[1] + ' SCENE_OK ' + request[2]);
    if (!replyBeforeAck) backend.handleMessage(prefix + 'READY HELLO'); // .then still queued
    await scene;
    assert.strictEqual(backend.sceneIdentity, 'sequence-v1');
    assert.strictEqual(backend.timeObservationEpoch, epoch);

    const range = backend.readRange('front');
    backend.handleMessage(prefix + 'READY HELLO');
    backend.handleMessage(prefix + 'RESPONSE 2 VALUE 0.5');
    assert.strictEqual(await range, 0.5, 'liveness cancelled an ordinary pending request');
    const revoked = assert.rejects(backend.readRange('front'), e=>e.code==='RESET_CANCELLED');
    backend.handleMessage(prefix + 'READY'); // genuine process-start signal still revokes
    backend.handleMessage(prefix + 'READY HELLO');
    backend.handleMessage(prefix + 'RESPONSE 3 VALUE 0.5');
    await revoked;
    assert.strictEqual(backend.sceneIdentity, null);
    assert.strictEqual(backend.timeObservationEpoch, epoch + 1);

    backend.authorized = true; // Simulated native grant after real restart.
    const reset = backend.resetSimulation();
    backend.handleMessage(prefix + 'READY HELLO');
    assert.strictEqual(backend.ready, false, 'late liveness reply completed a pending RESET');
    backend.handleMessage(prefix + 'RESPONSE 4 OK');
    await reset;
  }
}

async function testBackendResetContract() {
  const sent = [];
  const backend = new WwiBackend({send: message => sent.push(String(message))}, {
    timeoutMs: 1000,
    simulationDebug: true,
    simulationReset: true
  });

  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY');
  backend.authorized = true; // Mock C admission for legacy RESET oracle.
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(backend.capabilities.simulationReset, true);

  const oldRequest = backend.move('forward', 0.2).then(
    () => { throw new Error('old request unexpectedly resolved'); },
    error => error
  );
  assert.match(sent[0], / REQUEST 1 AUTH [0-9a-f]{64} MOVE forward /);
  assert.strictEqual(Object.keys(backend.pending).length, 1);

  const reset = backend.resetSimulation();
  const cancelled = await oldRequest;
  assert.strictEqual(cancelled.code, 'RESET_CANCELLED');
  assert.strictEqual(backend.ready, false);
  assert.strictEqual(Object.keys(backend.pending).length, 1);
  assert.match(sent[1], / REQUEST 2 AUTH [0-9a-f]{64} RESET$/);

  // A response from the pre-reset generation must be harmless.
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK');
  assert.strictEqual(Object.keys(backend.pending).length, 1);
  assert.strictEqual(backend.ready, false);

  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK');
  await reset;
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(Object.keys(backend.pending).length, 0);

  // A bounded native reset failure must leave the browser backend retryable.
  const timedOutReset = backend.resetSimulation().then(
    () => { throw new Error('timed-out reset unexpectedly resolved'); },
    error => error
  );
  assert.match(sent[2], / REQUEST 3 AUTH [0-9a-f]{64} RESET$/);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 ERR RESET_TIMEOUT');
  const resetError = await timedOutReset;
  assert.strictEqual(resetError.code, 'RESET_TIMEOUT');
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(Object.keys(backend.pending).length, 0);

  const retryReset = backend.resetSimulation();
  assert.match(sent[3], / REQUEST 4 AUTH [0-9a-f]{64} RESET$/);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 OK');
  await retryReset;
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(Object.keys(backend.pending).length, 0);

  const physical = new WwiBackend({send: () => {}}, {timeoutMs: 1000});
  assert.notStrictEqual(physical.capabilities.simulationReset, true);
  await assert.rejects(() => physical.resetSimulation(), /simulation reset unavailable/);
}

async function testProjectFileOperationsOutliveReadinessTimeout() {
  const sent = [];
  const transport = new WwiProjectFileTransport(
    {send: message => sent.push(String(message))},
    {timeoutMs: 5}
  );

  function requestId() {
    const match = sent.at(-1).match(/^WEBEEBLOCKS_FILE_BROKER_V1 REQUEST (\d+) /);
    assert(match, sent.at(-1));
    return Number(match[1]);
  }

  let pending = transport.waitUntilReady();
  let id = requestId();
  transport.handleMessage(
    `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} CAPABILITIES {"protocol":1,"provider":"qt6-native-dialog","operationsReady":true,"sameFileSave":true,"canonicalExtension":".wbb"}`
  );
  await pending;

  pending = transport.open();
  await Promise.resolve();
  id = requestId();
  await new Promise(resolve => setTimeout(resolve, 20));
  assert(transport.pending[id], 'Open expired on the readiness timeout');
  transport.handleMessage(
    `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} OPEN OK delayed_open ${WwiProjectFileTransport.encodeText('delayed.wbb')} ${WwiProjectFileTransport.encodeText('{"ok":1}')}`
  );
  const opened = await pending;
  assert.strictEqual(opened.handle.reference, 'delayed_open');

  pending = transport.saveAs('delayed.wbb', '{"ok":2}');
  await Promise.resolve();
  id = requestId();
  await new Promise(resolve => setTimeout(resolve, 20));
  assert(transport.pending[id], 'Save As expired on the readiness timeout');
  transport.handleMessage(
    `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} SAVE_AS OK delayed_save ${WwiProjectFileTransport.encodeText('delayed.wbb')}`
  );
  const saved = await pending;
  assert.strictEqual(saved.handle.reference, 'delayed_save');

  pending = transport.save(saved.handle, saved.name, '{"ok":3}');
  await Promise.resolve();
  id = requestId();
  await new Promise(resolve => setTimeout(resolve, 20));
  assert(transport.pending[id], 'same-file Save expired after its disk effect could have committed');
  transport.handleMessage(
    `WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ${id} SAVE OK delayed_save ${WwiProjectFileTransport.encodeText('delayed.wbb')}`
  );
  const resaved = await pending;
  assert.strictEqual(resaved.handle.reference, 'delayed_save');

  const unavailable = new WwiProjectFileTransport({send: () => {}}, {timeoutMs: 5});
  await assert.rejects(
    unavailable.waitUntilReady(),
    error => error && error.code === 'TIMEOUT'
  );
  assert.strictEqual(Object.keys(unavailable.pending).length, 0, 'readiness timeout stayed pending');
}

async function testProjectOpenKeepsResetRequirementAndLocksDuringReset() {
  const source = fs.readFileSync(path.join(__dirname, '../../plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
  let loadHandler = null;
  let runtimeStatusHandler = null;
  let openHandler = null;
  let statusCalls = 0;
  let actionUpdates = 0;
  let openCalls = 0;

  function button(id) {
    return {
      id,
      disabled: false,
      addEventListener(type, handler) {
        if (id === 'projectOpen' && type === 'click') openHandler = handler;
      }
    };
  }

  const elements = {
    projectActivity: button('projectActivity'),
    projectOpen: button('projectOpen'),
    projectSave: button('projectSave'),
    projectSaveAs: button('projectSaveAs'),
    projectFileState: {textContent: '', dataset: {}},
    activityTitle: {textContent: ''},
    activityGoal: {textContent: ''},
    runtimeDetail: {textContent: ''},
    blocklyDiv: {inert: false}
  };
  const manager = {
    nativeFileSystemAccess: true,
    hasCurrentTarget: () => false,
    currentName: () => null,
    open: async () => { openCalls += 1; return {name: 'opened.wbb'}; },
    saveAs: async () => ({name: 'saved.wbb'}),
    save: async () => ({name: 'saved.wbb'})
  };
  const context = {
    console,
    setTimeout,
    clearTimeout,
    CustomEvent: function CustomEvent(type, options) { this.type = type; this.detail = options && options.detail; },
    window: {
      addEventListener(type, handler) {
        if (type === 'load') loadHandler = handler;
        if (type === 'webeeblocks-runtime-v2') runtimeStatusHandler = handler;
      },
      dispatchEvent() {}
    },
    document: {
      body: {dataset: {}},
      getElementById(id) { return elements[id]; }
    },
    workspace: {updateToolbox() {}},
    runtimeProfile: {id: 'reactive-obstacle-v2', brief: {visible: false}},
    runtimeTerminal: true,
    robotWindow: {send() {}, receive() {}},
    runtimeBackend: {ready: true, waitUntilReady: async () => {}},
    runtimeProjectPending: false,
    Blockly: {},
    WebeeBlocksActivityProfiles: {},
    WebeeBlocksActivities: {DOCUMENT: {}, BLOCK_CATALOG: {}},
    WebeeBlocksSemanticAst: {},
    WebeeBlocksActivityContract: {applyFieldBounds() {}},
    WebeeBlocksProjectFiles: {
      createBrowserTransport: () => ({nativeFileSystemAccess: true, mode: 'browser-native'}),
      createManager: () => manager,
      normalizeName: name => name
    },
    buildToolbox: () => ({}),
    setRuntimeStatus() { statusCalls += 1; },
    updateRuntimeActions() { actionUpdates += 1; }
  };
  context.window.window = context.window;

  vm.runInNewContext(source, context, {filename: 'project_ui.js'});
  assert.strictEqual(typeof loadHandler, 'function');
  assert.strictEqual(typeof runtimeStatusHandler, 'function');
  loadHandler();
  // Project-file transport selection is asynchronous now that Firefox may
  // negotiate the local WWI broker. Let the established browser-native path
  // finish initialization before exercising the reset interlock.
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.strictEqual(typeof openHandler, 'function');

  runtimeStatusHandler({detail: {state: 'RÉINITIALISATION'}});
  assert.strictEqual(elements.blocklyDiv.inert, true, 'Blockly surface must be inert while reset stabilizes');
  assert.strictEqual(elements.projectOpen.disabled, true, 'Open must be disabled while reset stabilizes');
  openHandler();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.strictEqual(openCalls, 0, 'late Open event must be rejected while reset is locked');

  runtimeStatusHandler({detail: {state: 'PRÊT'}});
  assert.strictEqual(elements.blocklyDiv.inert, false, 'Blockly surface must unlock after reset leaves pending state');
  assert.strictEqual(elements.projectOpen.disabled, false, 'Open must unlock after reset leaves pending state');

  openHandler();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.strictEqual(openCalls, 1, 'Open must work again after reset lock is released');
  assert.strictEqual(context.runtimeTerminal, true, 'opening a project must not clear terminal/reset-required state');
  assert.strictEqual(statusCalls, 0, 'opening while terminal must not publish PRÊT');
  assert.ok(actionUpdates >= 1, 'opening while terminal must refresh action gating');
  assert.match(elements.runtimeDetail.textContent, /réinitialisez la simulation/);

  let finishOpen;
  manager.open = async () => { openCalls += 1; await new Promise(resolve => {finishOpen=resolve;}); return {name:'opened.wbb'}; };
  openHandler();
  await new Promise(resolve => setTimeout(resolve,0));
  assert.strictEqual(context.runtimeProjectPending,true,'project preparation did not hold execution gating');
  runtimeStatusHandler({detail:{state:'PRÊT'}}); // scene ACK, project not applied yet
  assert.strictEqual(elements.blocklyDiv.inert,true,'scene ACK unlocked edits before project application');
  assert.strictEqual(elements.projectOpen.disabled,true,'scene ACK unlocked another Open before project application');
  finishOpen();
  await new Promise(resolve => setTimeout(resolve,0));
  assert.strictEqual(context.runtimeProjectPending,false,'completed project operation kept execution locked');
  assert.strictEqual(elements.blocklyDiv.inert,false);
}

function testStartupHandshakeSourceContract() {
  const brokerSource = fs.readFileSync(
    path.join(__dirname, '../../controllers/crazyflie_runtime_v2/file_broker_runtime.cpp'), 'utf8');
  assert.match(brokerSource, /WEBEEBLOCKS_RUNTIME_V2 HELLO/);
  assert.match(brokerSource, /WEBEEBLOCKS_RUNTIME_V2 READY/);
  assert.match(brokerSource, /if \(isRuntimeHello\(message\)\) \{[\s\S]*wb_robot_wwi_send_text\(kRuntimeHelloReady\);[\s\S]*continue;/,
    'controller receive seam must answer HELLO without forging a startup READY or forwarding an action');

  const projectSource = fs.readFileSync(
    path.join(__dirname, '../../plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
  const runtimeReadyIndex = projectSource.indexOf('await runtimeBackend.waitUntilReady();');
  const brokerCreateIndex = projectSource.indexOf('new window.WebeeBlocksProjectFileWwiTransport');
  assert(runtimeReadyIndex >= 0, 'Firefox project path must wait for Runtime readiness');
  assert(brokerCreateIndex >= 0, 'Firefox project path must still construct the WWI file broker transport');
  assert(runtimeReadyIndex < brokerCreateIndex,
    'short file-broker readiness timeout must not start before the controller receive loop is live');
}

function testNativeAirborneIdleSafetyContract() {
  const source = fs.readFileSync(
    path.join(__dirname, '../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'), 'utf8');
  // Do not accept a dead-code guard after the pre-existing active-command path.
  const guardStart = source.indexOf('if (command == CMD_IDLE && airborne &&');
  const activeStart = source.indexOf('if (command != CMD_IDLE && command != CMD_RESET &&');
  assert(guardStart >= 0 && activeStart > guardStart,
    'airborne idle unsafe attitude must latch fail-safe before motor PID dispatch');
  const guard = source.slice(guardStart, activeStart);
  assert.match(guard, /fabs\(actual\.roll\) > 1\.2 \|\| fabs\(actual\.pitch\) > 1\.2/);
  for (const effect of ['stop_motors(m1, m2, m3, m4);',
    'airborne = 0;', 'simulation_clock_revoke(&program_clock);',
    'failsafe_latched = 1;', 'active_id = -1;', 'continue;']) {
    assert(guard.includes(effect), 'airborne idle guard missing effect: ' + effect);
  }
  assert.doesNotMatch(guard, /response_(?:ok|error|value)\(/,
    'no pending request exists while airborne idle: never forge a WWI reply');
  const fixture = fs.readFileSync(
    path.join(__dirname, 'fixtures/airborne_idle_failsafe_driver.c'), 'utf8');
  assert.match(fixture, /wb_supervisor_field_set_sf_rotation\(rotation, tilt\)/);
  assert.match(fixture, /strcmp\(detail, "RESET_REQUIRED"\)/);
  assert.match(fixture, /motors_stopped\(\)/);
  const runner = fs.readFileSync(
    path.join(__dirname, 'run_progression_sequence_mission.py'), 'utf8');
  assert.match(runner, /--case airborne-idle/);
  assert.match(runner, /--out \/workspace\/ci-artifacts\/progression-sequence-mission\/airborne-idle-failsafe/);
}

function testNativeCompletedIdStopContract() {
  const source = fs.readFileSync(path.join(__dirname, '../..', 'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'), 'utf8');
  // RESET already releases its id. Every completed motion must likewise
  // invalidate the one-shot pending id before a later STOP can arrive.
  const completed = [...source.matchAll(/response_ok\(active_id\);\s*command = CMD_IDLE;\s*active_id = -1;\s*\/\/ Completed request must not be canceled again by a later STOP\./g)];
  assert.strictEqual(completed.length, 6, 'all six completed motion types must revoke stale IDs');
  const changed = source.replace('active_id = -1;  // Completed request must not be canceled again by a later STOP.',
                                 '/* hypothetical stale completed id */');
  assert.strictEqual([...changed.matchAll(/response_ok\(active_id\);\s*command = CMD_IDLE;\s*active_id = -1;\s*\/\/ Completed request must not be canceled again by a later STOP\./g)].length, 5,
                     'the missing-clearing mutant must be detected');
  const runner = fs.readFileSync(path.join(__dirname, 'run_progression_sequence_mission.py'), 'utf8');
  assert.match(runner, /--case idle-stop/, 'native Webots STOP/ACK regression must remain wired to progression');
}


function testNativeWebotsWwiSequenceOracle() {
  // Evaluate the ACTUAL CI browser normalizer and sequence oracle shipped
  // in the Python HTML fixture, not a duplicate permissive test parser.
  const source = fs.readFileSync(path.join(__dirname, 'prepare_runtime_v2_webots.py'), 'utf8');
  const normalize = source.match(/  function normalizeWwiRequest\(message\) \{[\s\S]*?\n  \}/);
  const sequence = source.match(/  function assertWwiRequestSequence\(messages\) \{[\s\S]*?\n  \}/);
  assert(normalize && sequence, 'strict real-browser WWI oracle missing');
  const check = new Function(normalize[0] + '\n' + sequence[0] + '\nreturn assertWwiRequestSequence;')();
  const hex = 'a'.repeat(64);
  const status = i => 'WEBEEBLOCKS_RUNTIME_V2 REQUEST ' + i +
    ' RECOVERY_STATUS ' + '0'.repeat(64) + ' ' + i.toString(16).padStart(64, '0');
  const physical = [
    'SCENE legacy-v1 ' + hex, 'TAKEOFF 0.50000000000000000',
    'RANGE front', 'MOVE left 0.29999999999999999', 'RANGE front',
    'MOVE forward 0.29999999999999999', 'RANGE front',
    'MOVE left 0.29999999999999999', 'LAND'
  ];
  const makeMessages = (count=1) => [
    ...Array.from({length:count},(_,i)=>status(i+1)),
    ...physical.map((cmd,i)=>'WEBEEBLOCKS_RUNTIME_V2 REQUEST ' + (count+i+1) + ' ' + cmd)
  ];
  assert.equal(check(makeMessages()).length, 10, 'native guardian handshake is NOT optional');
  assert.equal(check(makeMessages(3)).length, 12, 'bounded native status retries must be visible');
  assert.throws(()=>check(makeMessages().slice(1)), /missing, duplicated or unbounded native status challenge/, 'missing guardian is a failure');
  assert.throws(()=>check(makeMessages(4)), /unbounded native status challenge/, 'unbounded retries are forbidden');
  assert.throws(()=>check(makeMessages().map(x=>x.replace('RECOVERY_STATUS ' + '0'.repeat(64),
      'RECOVERY_STATUS ' + 'a'.repeat(64)))), /unexpected WWI request command/, 'unknown token cannot pass');
  assert.throws(()=>check(makeMessages().map(x=>x.replace('RECOVERY_STATUS ' + '0'.repeat(64) + ' ' + '0'.repeat(63) + '1',
      'RECOVERY_STATUS ' + '0'.repeat(64) + ' broken'))), /unexpected WWI request command/, 'malformed nonce rejected');
  assert.throws(()=>check(makeMessages().map(x=>x.replace('REQUEST 2 SCENE','REQUEST 17 SCENE'))),
    /unexpected WWI request ids/, 'stale/noncontiguous WWI ids fail');
  const reordered = makeMessages(); [reordered[0],reordered[1]] = [reordered[1],reordered[0]];
  assert.throws(()=>check(reordered), /unexpected WWI request sequence/, 'guardian MUST precede the flight scene');
}

function testNativeResetTimeoutSourceContract() {
  const source = fs.readFileSync(path.join(__dirname, '../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'), 'utf8');
  assert.match(source, /#define RESET_TIMEOUT [0-9.]+/);
  assert.match(source, /command == CMD_RESET && now - action_start > RESET_TIMEOUT/);
  assert.match(source, /response_error\(active_id, "RESET_TIMEOUT"\)/);
  assert.match(source, /failsafe_latched = 1;/);
  // Scope assertions to the request and the timed stability branch.
  // Dead code or declarations elsewhere cannot masquerade as real samples.
  const resetRequest = source.match(/if \(request.kind == REQUEST_RESET\) \{([\s\S]*?)if \(failsafe_latched\) \{/);
  const resetLoop = source.match(/if \(command == CMD_RESET\) \{([\s\S]*?)if \(command == CMD_TAKEOFF\) \{/);
  assert(resetRequest && resetLoop, 'native RESET branches missing');
  for (const name of ['reset_pose_bad_samples', 'reset_motion_bad_samples', 'reset_both_ready_samples']) {
    assert(source.includes('unsigned long ' + name + ' = 0;'));
    assert(resetRequest[1].includes(name + ' = 0;'), 'RESET must clear ' + name);
  }
  assert(resetRequest[1].includes('reset_max_stable = 0.0;'));
  assert.match(resetLoop[1], /if \(!pose_ready\)\s*\+\+reset_pose_bad_samples;/);
  assert.match(resetLoop[1], /if \(!motion_ready\)\s*\+\+reset_motion_bad_samples;/);
  assert.match(resetLoop[1], /if \(pose_ready && motion_ready\) \{\s*\+\+reset_both_ready_samples;/);
  assert.match(resetLoop[1], /if \(now - stable_since > reset_max_stable\)/);
  assert.match(resetLoop[1], /if \(now - stable_since >= RESET_WINDOW\)/);
  assert.match(source, /pose_bad=%lu motion_bad=%lu/);
  assert.match(source, /both_ready=%lu max_stable=%\.6f/);
}

(async () => {
  await testBackendReadyHandshake();
  await testR3ClaimProtocol();
  await testHelloReplyDoesNotForgeRestart();
  await testBackendResetContract();
  await require('./test_runtime_v2_recovery.js')();
  testNativeWebotsWwiSequenceOracle();
  await require('./test_window_renewal.js')();
  await require('./test_window_renewal_timing.js')();
  // The observability fixture must wait for native witness authorization,
  // not merely backend.ready; run the real CI fixture's adversarial gate test.
  require('./test_observability_authorization_gate.js');
  await testProjectFileOperationsOutliveReadinessTimeout();
  await testProjectOpenKeepsResetRequirementAndLocksDuringReset();
  testStartupHandshakeSourceContract();
  testNativeResetTimeoutSourceContract();
  testNativeAirborneIdleSafetyContract();
  testNativeCompletedIdStopContract();
  console.log('PASS: startup readiness is actively recoverable, file-broker readiness starts only after Runtime readiness, reset cancels stale requests, project-file effects stay attached while readiness stays bounded, reset stays retryable, Blockly/Open lock while pending, and project reset gating remains simulation-only.');
})().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
