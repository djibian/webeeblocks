'use strict';

const assert = require('assert');
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

  const asserted = await bridge.assertCurrentWorkspace({});
  assert.strictEqual(asserted.compatible, true);
  assert.strictEqual(asserted.executionAuthority, false);
  assert.strictEqual(asserted.preflight.astBinding, result.astBinding);
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

  console.log('PASS non-authority physical submission bridge preserves exact AST and live connection epoch');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
