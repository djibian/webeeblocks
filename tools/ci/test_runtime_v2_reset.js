'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');

async function testBackendResetContract() {
  const sent = [];
  const backend = new WwiBackend({send: message => sent.push(String(message))}, {
    timeoutMs: 1000,
    simulationDebug: true,
    simulationReset: true
  });

  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY');
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(backend.capabilities.simulationReset, true);

  const oldRequest = backend.move('forward', 0.2).then(
    () => { throw new Error('old request unexpectedly resolved'); },
    error => error
  );
  assert.match(sent[0], / REQUEST 1 MOVE forward /);
  assert.strictEqual(Object.keys(backend.pending).length, 1);

  const reset = backend.resetSimulation();
  const cancelled = await oldRequest;
  assert.strictEqual(cancelled.code, 'RESET_CANCELLED');
  assert.strictEqual(backend.ready, false);
  assert.strictEqual(Object.keys(backend.pending).length, 1);
  assert.match(sent[1], / REQUEST 2 RESET$/);

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
  assert.match(sent[2], / REQUEST 3 RESET$/);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 ERR RESET_TIMEOUT');
  const resetError = await timedOutReset;
  assert.strictEqual(resetError.code, 'RESET_TIMEOUT');
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(Object.keys(backend.pending).length, 0);

  const retryReset = backend.resetSimulation();
  assert.match(sent[3], / REQUEST 4 RESET$/);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 OK');
  await retryReset;
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(Object.keys(backend.pending).length, 0);

  const physical = new WwiBackend({send: () => {}}, {timeoutMs: 1000});
  assert.notStrictEqual(physical.capabilities.simulationReset, true);
  await assert.rejects(() => physical.resetSimulation(), /simulation reset unavailable/);
}

async function testProjectOpenKeepsResetRequirement() {
  const source = fs.readFileSync(path.join(__dirname, '../../plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
  let loadHandler = null;
  let openHandler = null;
  let statusCalls = 0;
  let actionUpdates = 0;

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
    projectOpen: button('projectOpen'),
    projectSave: button('projectSave'),
    projectSaveAs: button('projectSaveAs'),
    projectFileState: {textContent: '', dataset: {}},
    activityTitle: {textContent: ''},
    activityGoal: {textContent: ''},
    runtimeDetail: {textContent: ''}
  };
  const manager = {
    nativeFileSystemAccess: true,
    hasCurrentTarget: () => false,
    currentName: () => null,
    open: async () => ({name: 'opened.wbb'}),
    saveAs: async () => ({name: 'saved.wbb'}),
    save: async () => ({name: 'saved.wbb'})
  };
  const context = {
    console,
    setTimeout,
    clearTimeout,
    CustomEvent: function CustomEvent(type, options) { this.type = type; this.detail = options && options.detail; },
    window: {
      addEventListener(type, handler) { if (type === 'load') loadHandler = handler; },
      dispatchEvent() {}
    },
    document: {
      body: {dataset: {}},
      getElementById(id) { return elements[id]; }
    },
    workspace: {updateToolbox() {}},
    runtimeProfile: {id: 'reactive-obstacle-v2', brief: {visible: false}},
    runtimeTerminal: true,
    runtimeBackend: {ready: true},
    Blockly: {},
    WebeeBlocksActivityProfiles: {},
    WebeeBlocksActivities: {DOCUMENT: {}, BLOCK_CATALOG: {}},
    WebeeBlocksSemanticAst: {},
    WebeeBlocksActivityContract: {applyFieldBounds() {}},
    WebeeBlocksProjectFiles: {
      createBrowserTransport: () => ({}),
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
  loadHandler();
  assert.strictEqual(typeof openHandler, 'function');
  openHandler();
  await new Promise(resolve => setTimeout(resolve, 0));

  assert.strictEqual(context.runtimeTerminal, true, 'opening a project must not clear terminal/reset-required state');
  assert.strictEqual(statusCalls, 0, 'opening while terminal must not publish PRÊT');
  assert.ok(actionUpdates >= 1, 'opening while terminal must refresh action gating');
  assert.match(elements.runtimeDetail.textContent, /réinitialisez la simulation/);
}

function testNativeResetTimeoutSourceContract() {
  const source = fs.readFileSync(path.join(__dirname, '../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'), 'utf8');
  assert.match(source, /#define RESET_TIMEOUT [0-9.]+/);
  assert.match(source, /command == CMD_RESET && now - action_start > RESET_TIMEOUT/);
  assert.match(source, /response_error\(active_id, "RESET_TIMEOUT"\)/);
  assert.match(source, /failsafe_latched = 1;/);
}

(async () => {
  await testBackendResetContract();
  await testProjectOpenKeepsResetRequirement();
  testNativeResetTimeoutSourceContract();
  console.log('PASS: reset cancels stale requests, remains retryable after timeout, project open preserves reset gating, and physical backend reset stays unavailable.');
})().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
