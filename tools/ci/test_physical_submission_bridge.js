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
  let epochReadHook = null;
  let challengeWaiter = null;
  const challengeQueue = [];
  let assertionWaiter = null;
  const assertionQueue = [];
  const token = 'unit-test-secret';

  function response(payload, ok, status) {
    return {
      ok: ok === undefined ? true : ok,
      status: status === undefined ? 200 : status,
      async json() { return JSON.parse(JSON.stringify(payload)); }
    };
  }

  function enqueueChallenge(challengeId) {
    const payload = {challengeId: challengeId, executionAuthority: false};
    if (challengeWaiter) {
      const resolve = challengeWaiter;
      challengeWaiter = null;
      resolve(response(payload));
    } else {
      challengeQueue.push(payload);
    }
  }

  function waitForAssertion() {
    if (assertionQueue.length)
      return Promise.resolve(assertionQueue.shift());
    return new Promise(resolve => { assertionWaiter = resolve; });
  }

  function recordAssertion(payload) {
    if (assertionWaiter) {
      const resolve = assertionWaiter;
      assertionWaiter = null;
      resolve(payload);
    } else {
      assertionQueue.push(payload);
    }
  }

  function delayNextEpochRead() {
    let startedResolve;
    let releaseResolve;
    const started = new Promise(resolve => { startedResolve = resolve; });
    const released = new Promise(resolve => { releaseResolve = resolve; });
    epochReadHook = async function() {
      startedResolve();
      await released;
    };
    return {started: started, release: releaseResolve};
  }

  async function fakeFetch(url, options) {
    assert.strictEqual(options.headers.Authorization, 'Bearer ' + token);
    if (url.endsWith('/v1/preflight-challenge')) {
      assert.strictEqual(options.method, 'GET');
      if (challengeQueue.length)
        return response(challengeQueue.shift());
      return new Promise(resolve => { challengeWaiter = resolve; });
    }
    if (url.endsWith('/v1/preflight-assertion')) {
      assert.strictEqual(options.method, 'POST');
      assert.strictEqual(options.headers['Content-Type'], 'application/json');
      const payload = JSON.parse(options.body);
      recordAssertion(payload);
      return response({accepted: true, executionAuthority: false});
    }
    assert.strictEqual(options.method, 'GET');
    if (url.endsWith('/v1/capabilities')) {
      capabilityReads += 1;
      return response(descriptor);
    }
    if (url.endsWith('/v1/connection-epoch')) {
      epochReads += 1;
      if (epochReadHook) {
        const hook = epochReadHook;
        epochReadHook = null;
        await hook();
      }
      return response({connectionEpoch: epoch});
    }
    return response({error: 'not-found'}, false, 404);
  }

  const adapter = HttpAdapter.create({
    baseUrl: 'http://127.0.0.1:8765/',
    token: token,
    fetchImpl: fakeFetch
  });
  assert.deepStrictEqual(
    Object.keys(adapter).sort(),
    ['readCapabilities', 'readConnectionEpoch', 'readCurrentProgramChallenge', 'submitCurrentProgramAssertion']
  );
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
  await assert.rejects(
    () => bridge.assertCurrentWorkspace({}),
    /physical preflight is required/,
    'workspace mismatch must clear the stored exact-AST binding'
  );
  await bridge.preflightWorkspace({});
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
    /bridge request failed \(401\): unauthorized/
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


  // Production handoff answers a host-created challenge only by running the real
  // exact-current #249 re-assertion; the challenge does not carry expected data.
  const exactAssertionPromise = waitForAssertion();
  enqueueChallenge('challenge-exact');
  const exactAssertion = await exactAssertionPromise;
  assert.strictEqual(exactAssertion.challengeId, 'challenge-exact');
  assert.strictEqual(exactAssertion.ok, true);
  assert.strictEqual(exactAssertion.executionAuthority, false);
  assert.strictEqual(exactAssertion.profileId, global.runtimeProfile.id);
  assert.strictEqual(exactAssertion.astBinding, productPreflight.astBinding);
  assert.strictEqual(exactAssertion.connectionEpoch, 'connection-product');

  // A changed AST cannot be turned into a positive host assertion.
  currentAst = program(0.3);
  const astFailurePromise = waitForAssertion();
  enqueueChallenge('challenge-ast-change');
  const astFailure = await astFailurePromise;
  assert.strictEqual(astFailure.challengeId, 'challenge-ast-change');
  assert.strictEqual(astFailure.ok, false);
  assert.strictEqual(astFailure.executionAuthority, false);
  currentAst = program(0.2);
  await assert.rejects(
    () => productBridge.assertCurrentProgram(),
    /physical preflight is required/,
    'challenge-time AST mismatch must invalidate the old #249 binding'
  );
  await productBridge.preflightCurrentProgram();

  // A changed activity profile likewise fails at the real #249 runtime boundary.
  const handoffProfile = global.runtimeProfile;
  global.runtimeProfile = Profiles.resolveById(
    Activities.DOCUMENT,
    'progression-precise-movement-v1',
    Activities.BLOCK_CATALOG
  );
  const profileFailurePromise = waitForAssertion();
  enqueueChallenge('challenge-profile-change');
  const profileFailure = await profileFailurePromise;
  assert.strictEqual(profileFailure.ok, false);
  assert.strictEqual(profileFailure.executionAuthority, false);
  global.runtimeProfile = handoffProfile;
  await assert.rejects(
    () => productBridge.assertCurrentProgram(),
    /physical preflight is required/,
    'challenge-time profile mismatch must invalidate the old #249 binding'
  );
  await productBridge.preflightCurrentProgram();

  // Reconnect/epoch drift cannot produce a positive assertion for the old session.
  epoch = 'connection-product-changed';
  const epochFailurePromise = waitForAssertion();
  enqueueChallenge('challenge-epoch-change');
  const epochFailure = await epochFailurePromise;
  assert.strictEqual(epochFailure.ok, false);
  assert.strictEqual(epochFailure.executionAuthority, false);
  epoch = 'connection-product';
  await productBridge.preflightCurrentProgram();

  const workspaceDelay = delayNextEpochRead();
  const pendingWorkspaceAssertion = productBridge.assertCurrentProgram();
  await workspaceDelay.started;
  currentAst = program(0.3);
  workspaceDelay.release();
  await assert.rejects(
    pendingWorkspaceAssertion,
    /workspace changed during physical re-assertion/,
    'workspace mutation while epoch re-assertion is pending must fail closed'
  );
  currentAst = program(0.2);
  await assert.rejects(
    () => productBridge.assertCurrentProgram(),
    /physical preflight is required/,
    'async workspace mismatch must invalidate the prior physical preflight'
  );
  await productBridge.preflightCurrentProgram();

  const preflightProfile = global.runtimeProfile;
  const profileDelay = delayNextEpochRead();
  const pendingProfileAssertion = productBridge.assertCurrentProgram();
  await profileDelay.started;
  global.runtimeProfile = Profiles.resolveById(
    Activities.DOCUMENT,
    'progression-precise-movement-v1',
    Activities.BLOCK_CATALOG
  );
  profileDelay.release();
  await assert.rejects(
    pendingProfileAssertion,
    /activity profile changed during physical re-assertion/,
    'profile mutation while epoch re-assertion is pending must fail closed'
  );
  global.runtimeProfile = preflightProfile;
  await assert.rejects(
    () => productBridge.assertCurrentProgram(),
    /physical preflight is required/,
    'async profile mismatch must invalidate the prior physical preflight'
  );
  await productBridge.preflightCurrentProgram();

  currentAst = program(0.4);
  await assert.rejects(
    () => productBridge.assertCurrentProgram(),
    /workspace changed since physical preflight/,
    'live student workspace mutation must invalidate production physical binding'
  );
  productBridge.clear();

  console.log('PASS non-authority physical submission bridge provides fresh host-initiated exact-current #249 evidence');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
