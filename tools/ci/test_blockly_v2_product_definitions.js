#!/usr/bin/env node
'use strict';

// Test product-owned block semantics, not the whitespace of their JS source.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = path.resolve(
  __dirname, '../../plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js'
);
const registrations = [];
const procedure = {
  init() {
    this.originalInitCalls = (this.originalInitCalls || 0) + 1;
  }
};
const Blockly = {
  Blocks: {procedures_defnoreturn: procedure},
  defineBlocksWithJsonArray(definitions) {
    registrations.push(JSON.parse(JSON.stringify(definitions)));
  }
};
function loadDefinitions() {
  vm.runInNewContext(fs.readFileSync(source, 'utf8'), {Blockly}, {
    filename: source, timeout: 1000
  });
}
loadDefinitions();
assert.equal(registrations.length, 1, 'product definitions registered exactly once');

const definitions = registrations[0];
const expectedTypes = [
  'webeeblocks_v2_takeoff', 'webeeblocks_v2_land', 'webeeblocks_v2_move',
  'webeeblocks_v2_vertical', 'webeeblocks_v2_turn', 'webeeblocks_v2_wait',
  'webeeblocks_v2_speed', 'webeeblocks_v2_light', 'webeeblocks_v2_elapsed',
  'webeeblocks_v2_range', 'webeeblocks_v2_until'
];
function verifyDefinitions(blocks) {
  assert.equal(blocks.length, expectedTypes.length, 'exact product block count');
  assert.deepEqual(blocks.map(block => block.type).sort(), [...expectedTypes].sort(),
    'no missing, extra or duplicate product block types');
  const counts = Object.create(null);
  for (const block of blocks) counts[block.style] = (counts[block.style] || 0) + 1;
  for (const [style, count] of Object.entries({
    flight_blocks: 7, control_blocks: 1, sensor_blocks: 2, loop_blocks: 1
  })) {
    assert.equal(counts[style], count, `${style} block count`);
  }
  assert.equal(Object.keys(counts).length, 4, 'no unexpected block style');

  const range = blocks.find(block => block.type === 'webeeblocks_v2_range');
  assert.equal(range.message0, 'distance %1', 'range label without a redundant unit');
  assert.equal(range.output, 'Number', 'range output');
  assert.equal(range.style, 'sensor_blocks', 'range style');

  assert.deepEqual(blocks.find(block => block.type === 'webeeblocks_v2_elapsed'), {
    type: 'webeeblocks_v2_elapsed',
    message0: 'temps simulé depuis le départ (s)',
    output: 'Number',
    style: 'sensor_blocks'
  }, 'the exact elapsed-time block contract');
}
verifyDefinitions(definitions);

// Deliberately corrupt three properties to demonstrate rejection.
function mutated(type, patch) {
  return definitions.map(block => block.type === type ? {...block, ...patch} : {...block});
}
assert.throws(() => verifyDefinitions(mutated('webeeblocks_v2_range', {
  message0: 'distance %1 (m)'
})), /range label/);
assert.throws(() => verifyDefinitions(mutated('webeeblocks_v2_takeoff', {
  style: 'sensor_blocks'
})), /block count/);
assert.throws(() => verifyDefinitions(mutated('webeeblocks_v2_elapsed', {
  output: 'Boolean'
})), /elapsed-time block contract/);

// Preserve Blockly procedure initialization, with no parameter mutator.
assert.equal(procedure.webeeblocksNoParameters, true);
const instance = {setMutator(value) {this.mutator = value;}};
procedure.init.call(instance);
assert.equal(instance.originalInitCalls, 1);
assert.equal(instance.mutator, null);
const initialized = procedure.init;
loadDefinitions();
assert.equal(procedure.init, initialized, 'procedure init is wrapped at most once');

console.log('PASS product Blockly blocks: definitions, styles, labels, elapsed time, procedures');
