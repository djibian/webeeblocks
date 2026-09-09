'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const HttpAdapter = require('../../plugins/robot_windows/blockly/webeeblocks/physical_capability_http_adapter.js');
const SubmissionBridge = require('../../plugins/robot_windows/blockly/webeeblocks/physical_submission_bridge.js');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js');
const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities.js');

const profile = Profiles.resolveById(
  Activities.DOCUMENT,
  'reactive-obstacle-v2',
  Activities.BLOCK_CATALOG
);

const descriptor = {
  transport: 'crazyradio',
  connected: true,
  executionAuthority: false,
  identity: {family: 'crazyflie', model: 'crazyflie-2.1', modelEvidence: 'verified'},
  hardware: ['flow-deck-v2'],
  capabilities: {
    actions: ['takeoff', 'move', 'land'],
    rangeDirections: [],
    moveDirections: ['forward'],
    verticalDirections: []
  }
};

function program(distance) {
  return {
    version: 1,
    semantics: 'webeeblocks-ast-v1',
    program: [
      {kind: 'takeoff', height_m: 0.8},
      {kind: 'move', direction: 'forward', distance_m: distance},
      {kind: 'land'}
    ]
  };
}

(async function() {
  let epoch = 'connection-1';
  let currentAst = program(0.2);
  let capabilityReads = 0;
  let epochReads = 0;
  const token = 'unit-test-secret';

  async function fakeFetch(url, options) {
    assert.strictEqual(options.method, 'GET');
    assert.strictEqual(options.headers.Authorization, 'Bearer ' + token);
    if (url.endsWith('/v1/capabilities')) {
      capabilityReads += 1;
      return {ok: true, status: 200, async json() { return JSON.parse(JSON.stringify(descriptor)); }};
    }
    if (url.endsWith('/v1/connection-epoch')) {
      epochReads += 1;
      return {ok: true, status: 200, async json() { return {connectionEpoch: epoch}; }};
    }
    return {ok: false, status: 404, async json() { return {error: 'not-found'}; }};
  }

  const adapter = HttpAdapter.create({
    baseUrl: 'http://127.0.0.1:8765/',
    token: token,
    fetchImpl: fakeFetch
  });
  assert.deepStrictEqual(Object.keys(adapter).sort(), ['readCapabilities', 'readConnectionEpoch']);
  assert.strictEqual(Object.isFrozen(adapter), true);

  const bridge = SubmissionBridge.create(profile, adapter, () => JSON.parse(JSON.stringify(currentAst)));
  assert.strictEqual(bridge.executionAuthority, false);
  for (const forbidden of ['takeoff','land','move','vertical','turn','setLight','arm','setpoint','sendSetpoint','thrust'])
    assert.strictEqual(typeof bridge[forbidden], 'undefined', 'bridge exposes authority method: ' + forbidden);

  const result = await bridge.preflightWorkspace({});
  assert.strictEqual(result.compatible, true);
  assert.strictEqual(result.executionAuthority, false);
  assert.strictEqual(result.connectionEpoch, 'connection-1');
  assert.strictEqual(capabilityReads, 1);
  assert.strictEqual(epochReads, 2, 'preflight must bracket the descriptor with one stable epoch');

  result.connectionEpoch = 'caller-tampered-epoch';
  const asserted = await bridge.assertCurrentWorkspace({});
  assert.strictEqual(asserted.compatible, true);
  assert.strictEqual(asserted.executionAuthority, false);
  assert.notStrictEqual(asserted.preflight, result, 'internal exact-session ticket must not alias caller-owned result');
  assert.strictEqual(asserted.preflight.connectionEpoch, 'connection-1');
  assert.strictEqual(Object.isFrozen(asserted.preflight), true);
  assert.strictEqual(epochReads, 3, 'pre-effect reassertion must re-read the current epoch');

  currentAst = program(0.3);
  await assert.rejects(
    () => bridge.assertCurrentWorkspace({}),
    /workspace changed since physical preflight/,
    'changed program must invalidate the stored exact-AST binding'
  );

  currentAst = program(0.2);
  epoch = 'connection-2';
  await assert.rejects(
    () => bridge.assertCurrentWorkspace({}),
    /connection changed since physical preflight/,
    'reconnect must invalidate the stored session binding'
  );

  bridge.clear();
  await assert.rejects(
    () => bridge.assertCurrentWorkspace({}),
    /physical preflight is required/,
    'cleared binding must fail closed'
  );

  const failingAdapter = HttpAdapter.create({
    baseUrl: 'http://127.0.0.1:8765',
    token: token,
    fetchImpl: async () => ({ok: false, status: 401, async json() { return {error: 'unauthorized'}; }})
  });
  await assert.rejects(
    () => failingAdapter.readCapabilities(),
    /bridge read failed \(401\): unauthorized/
  );

  const productHtml = fs.readFileSync(path.join(__dirname, '../../plugins/robot_windows/blockly_v2/blockly_v2.html'), 'utf8');
  for (const script of [
    'physical_capability_contract.js',
    'physical_capability_http_adapter.js',
    'physical_submission_bridge.js',
    'physical_preflight_runtime.js'
  ])
    assert(productHtml.includes(script), 'student runtime must load ' + script);
  assert(productHtml.indexOf('main.js') < productHtml.indexOf('physical_preflight_runtime.js'),
    'physical runtime bridge must bind after main student runtime globals exist');

  global.WebeeBlocksPhysicalCapabilityHttpAdapter = HttpAdapter;
  global.WebeeBlocksPhysicalSubmissionBridge = SubmissionBridge;
  global.WebeeBlocksSemanticAst = {compileWorkspace: () => JSON.parse(JSON.stringify(currentAst))};
  global.runtimeProfile = profile;
  global.workspace = {};
  delete require.cache[require.resolve('../../plugins/robot_windows/blockly_v2/physical_preflight_runtime.js')];
  require('../../plugins/robot_windows/blockly_v2/physical_preflight_runtime.js');
  const productBridge = global.WebeeBlocksPhysicalPreflight;
  assert.strictEqual(productBridge.executionAuthority, false);
  for (const forbidden of ['takeoff','land','move','vertical','turn','setLight','arm','setpoint','sendSetpoint','thrust'])
    assert.strictEqual(typeof productBridge[forbidden], 'undefined', 'product bridge exposes authority method: ' + forbidden);

  epoch = 'connection-product';
  currentAst = program(0.2);
  productBridge.configure({baseUrl: 'http://127.0.0.1:8765', token: token, fetchImpl: fakeFetch});
  const productPreflight = await productBridge.preflightCurrentProgram();
  assert.strictEqual(productPreflight.connectionEpoch, 'connection-product');
  const productAssertion = await productBridge.assertCurrentProgram();
  assert.strictEqual(productAssertion.executionAuthority, false);
  assert.strictEqual(productAssertion.preflight.connectionEpoch, 'connection-product');

  currentAst = program(0.4);
  await assert.rejects(
    () => productBridge.assertCurrentProgram(),
    /workspace changed since physical preflight/,
    'live student workspace mutation must invalidate production physical binding'
  );
  productBridge.clear();

  console.log('PASS non-authority physical submission bridge binds the live student AST to one Crazyradio connection epoch');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
