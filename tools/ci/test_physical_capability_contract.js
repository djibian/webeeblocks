'use strict';
const assert = require('assert');
const PhysicalCapabilities = require('../../plugins/robot_windows/blockly/webeeblocks/physical_capability_contract.js');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js');
const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities.js');

const profile = Profiles.resolveById(
  Activities.DOCUMENT,
  'progression-simple-decision-v1',
  Activities.BLOCK_CATALOG
);
const broadProfile = Profiles.resolveById(
  Activities.DOCUMENT,
  'progression-autonomous-strategy-v1',
  Activities.BLOCK_CATALOG
);
const reactiveProfile = Profiles.resolveById(
  Activities.DOCUMENT,
  'reactive-obstacle-v2',
  Activities.BLOCK_CATALOG
);

const facts = {
  statements: new Set(['takeoff','move','if','land']),
  ranges: new Set(['front']),
  moveDirections: new Set(['forward','left']),
  verticalDirections: new Set()
};

function ast(program) {
  return {version: 1, semantics: 'webeeblocks-ast-v1', program};
}

const descriptor = {
  transport: 'crazyradio',
  connected: true,
  executionAuthority: false,
  identity: {
    family: 'crazyflie',
    model: 'crazyflie-2.1',
    modelEvidence: 'verified'
  },
  hardware: ['flow-deck-v2','multi-ranger-deck'],
  capabilities: {
    actions: ['takeoff','move','land'],
    rangeDirections: ['front'],
    moveDirections: ['forward','left'],
    verticalDirections: []
  }
};

(async function() {
  let reads = 0;
  const observed = await PhysicalCapabilities.inspect({
    async readCapabilities() {
      reads += 1;
      return descriptor;
    }
  });
  assert.strictEqual(reads, 1);
  assert.deepStrictEqual(observed, descriptor);
  assert.strictEqual(PhysicalCapabilities.preflight(profile, facts, observed), true);

  const unprovenModel = JSON.parse(JSON.stringify(descriptor));
  unprovenModel.identity.model = null;
  unprovenModel.identity.modelEvidence = 'unproven';
  const observedUnproven = await PhysicalCapabilities.inspect({
    async readCapabilities() { return unprovenModel; }
  });
  assert.strictEqual(observedUnproven.identity.model, null);
  assert.strictEqual(observedUnproven.identity.modelEvidence, 'unproven');
  assert.throws(
    () => PhysicalCapabilities.preflight(profile, facts, observedUnproven),
    /exact physical model evidence unavailable: crazyflie-2.1/
  );

  const claimedUnprovenModel = JSON.parse(JSON.stringify(unprovenModel));
  claimedUnprovenModel.identity.model = 'crazyflie-2.1';
  assert.throws(
    () => PhysicalCapabilities.normalizeDescriptor(claimedUnprovenModel),
    /unproven exact model must be null/
  );

  const encodedAirframe = JSON.parse(JSON.stringify(descriptor));
  encodedAirframe.hardware.push('crazyflie-2.1');
  assert.throws(
    () => PhysicalCapabilities.normalizeDescriptor(encodedAirframe),
    /exact airframe identity must not be encoded as generic hardware evidence/
  );

  const missingUnusedDeck = JSON.parse(JSON.stringify(descriptor));
  missingUnusedDeck.hardware = ['flow-deck-v2'];
  assert.strictEqual(
    PhysicalCapabilities.preflight(profile, facts, missingUnusedDeck),
    true,
    'an unused optional deck must not block when the exact required capabilities are available'
  );

  const minimalFacts = {
    statements: new Set(['takeoff','land']),
    ranges: new Set(),
    moveDirections: new Set(),
    verticalDirections: new Set()
  };
  const minimalDescriptor = JSON.parse(JSON.stringify(descriptor));
  minimalDescriptor.hardware = ['flow-deck-v2'];
  minimalDescriptor.capabilities.actions = ['takeoff','land'];
  minimalDescriptor.capabilities.rangeDirections = [];
  minimalDescriptor.capabilities.moveDirections = [];
  assert.strictEqual(
    PhysicalCapabilities.preflight(broadProfile, minimalFacts, minimalDescriptor),
    true,
    'broad profile optional decks must not become global prerequisites for a smaller AST'
  );

  const requiredLightFacts = {
    statements: new Set(['takeoff','set_light','land']),
    ranges: new Set(),
    moveDirections: new Set(),
    verticalDirections: new Set()
  };
  assert.throws(
    () => PhysicalCapabilities.preflight(broadProfile, requiredLightFacts, minimalDescriptor),
    /physical action capability unavailable: set_light/,
    'a capability actually required by the AST must still fail closed'
  );

  const missingRange = JSON.parse(JSON.stringify(descriptor));
  missingRange.capabilities.rangeDirections = [];
  assert.throws(
    () => PhysicalCapabilities.preflight(profile, facts, missingRange),
    /physical range capability unavailable: front/
  );

  await assert.rejects(
    () => PhysicalCapabilities.inspect({
      async readCapabilities() { return descriptor; },
      takeoff() {}
    }),
    /forbidden authority method: takeoff/
  );

  const unauthorized = JSON.parse(JSON.stringify(descriptor));
  unauthorized.executionAuthority = true;
  await assert.rejects(
    () => PhysicalCapabilities.inspect({
      async readCapabilities() { return unauthorized; }
    }),
    /executionAuthority=false/
  );

  const disconnected = JSON.parse(JSON.stringify(descriptor));
  disconnected.connected = false;
  await assert.rejects(
    () => PhysicalCapabilities.inspect({
      async readCapabilities() { return disconnected; }
    }),
    /connection is not established/
  );

  const wrongTransport = JSON.parse(JSON.stringify(descriptor));
  wrongTransport.transport = 'unknown';
  await assert.rejects(
    () => PhysicalCapabilities.inspect({
      async readCapabilities() { return wrongTransport; }
    }),
    /unsupported transport/
  );


  const nested = ast([
    {kind: 'takeoff', height_m: 0.8},
    {kind: 'move', direction: 'back', distance_m: 0.2},
    {kind: 'set_variable', variable: {id: 'd', name: 'distance'}, value: {kind: 'range', direction: 'front', unit: 'm'}},
    {kind: 'if', condition: {kind: 'compare', op: 'LT', left: {kind: 'range', direction: 'right', unit: 'm'}, right: {kind: 'number', value: 1}}, then: [
      {kind: 'vertical', direction: 'up', distance_m: 0.2},
      {kind: 'set_light', color: 'red'}
    ], else: [
      {kind: 'repeat', count: 2, body: [{kind: 'turn', angle_deg: 45}, {kind: 'wait', seconds: 0.2}]}
    ]},
    {kind: 'land'}
  ]);
  const derived = PhysicalCapabilities.deriveFacts(nested);
  assert.deepStrictEqual([...derived.statements].sort(), ['if','land','move','repeat','set_light','set_variable','takeoff','turn','vertical','wait']);
  assert.deepStrictEqual([...derived.ranges].sort(), ['front','right']);
  assert.deepStrictEqual([...derived.moveDirections], ['back']);
  assert.deepStrictEqual([...derived.verticalDirections], ['up']);

  const flowOnly = JSON.parse(JSON.stringify(descriptor));
  flowOnly.hardware = ['flow-deck-v2'];
  flowOnly.capabilities.rangeDirections = [];
  const noOptionalDeckIntent = ast([
    {kind: 'takeoff', height_m: 0.8},
    {kind: 'move', direction: 'forward', distance_m: 0.2},
    {kind: 'land'}
  ]);
  const compatible = PhysicalCapabilities.preflightAst(reactiveProfile, noOptionalDeckIntent, flowOnly);
  assert.strictEqual(compatible.compatible, true, 'unused optional decks must not reject physical compatibility');
  assert.strictEqual(compatible.executionAuthority, false, 'capability preflight must never grant execution authority');

  const lightIntent = ast([
    {kind: 'takeoff', height_m: 0.8},
    {kind: 'set_light', color: 'red'},
    {kind: 'land'}
  ]);
  assert.throws(
    () => PhysicalCapabilities.preflightAst(reactiveProfile, lightIntent, flowOnly),
    error => error && error.code === 'PHYSICAL_CAPABILITY_MISMATCH' &&
      /programme n’a pas été envoyé/.test(error.studentDetail) &&
      /set_light/.test(error.studentDetail) && /flow-deck-v2/.test(error.studentDetail),
    'used Color LED capability must fail closed with a detected-hardware diagnostic'
  );

  const rangeIntent = ast([
    {kind: 'takeoff', height_m: 0.8},
    {kind: 'set_variable', variable: {id: 'd', name: 'distance'}, value: {kind: 'range', direction: 'front', unit: 'm'}},
    {kind: 'land'}
  ]);
  assert.throws(
    () => PhysicalCapabilities.preflightAst(reactiveProfile, rangeIntent, flowOnly),
    error => error && error.code === 'PHYSICAL_CAPABILITY_MISMATCH' && /range capability unavailable: front/.test(error.message),
    'used Multi-ranger capability must fail closed when freshly observed descriptor lacks it'
  );

  const forwardOnly = JSON.parse(JSON.stringify(flowOnly));
  forwardOnly.capabilities.moveDirections = ['forward'];
  const backIntent = ast([
    {kind: 'takeoff', height_m: 0.8},
    {kind: 'move', direction: 'back', distance_m: 0.2},
    {kind: 'land'}
  ]);
  assert.throws(
    () => PhysicalCapabilities.preflightAst(reactiveProfile, backIntent, forwardOnly),
    error => error && error.code === 'PHYSICAL_CAPABILITY_MISMATCH' && /move direction unavailable: back/.test(error.message)
  );

  const explicitHardware = JSON.parse(JSON.stringify(reactiveProfile));
  explicitHardware.physicalHardwareRequired = ['multi-ranger-deck'];
  assert.throws(
    () => PhysicalCapabilities.preflightAst(explicitHardware, noOptionalDeckIntent, flowOnly),
    error => error && error.code === 'PHYSICAL_CAPABILITY_MISMATCH' && /required hardware unavailable: multi-ranger-deck/.test(error.message),
    'genuine unconditional physical prerequisites remain expressible explicitly'
  );

  assert.throws(
    () => PhysicalCapabilities.preflightAst(reactiveProfile, noOptionalDeckIntent, unprovenModel),
    error => error && error.code === 'PHYSICAL_CAPABILITY_MISMATCH' && /exact physical model evidence unavailable: crazyflie-2.1/.test(error.message),
    'exact Crazyflie 2.1 identity remains mandatory on the new AST-derived path'
  );

  assert.throws(
    () => PhysicalCapabilities.deriveFacts(ast([{kind: 'future_command'}])),
    /unsupported AST statement kind/,
    'unknown AST capabilities must fail closed rather than be ignored'
  );

  console.log('PASS live physical capability preflight derives exact AST needs without granting execution authority');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
