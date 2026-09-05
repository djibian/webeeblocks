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

const facts = {
  statements: new Set(['takeoff','move','if','land']),
  ranges: new Set(['front']),
  moveDirections: new Set(['forward','left']),
  verticalDirections: new Set()
};

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

  const missingDeck = JSON.parse(JSON.stringify(descriptor));
  missingDeck.hardware = ['flow-deck-v2'];
  assert.throws(
    () => PhysicalCapabilities.preflight(profile, facts, missingDeck),
    /required hardware unavailable: multi-ranger-deck/
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

  console.log('PASS read-only physical capability handshake separates evidence from execution authority');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
