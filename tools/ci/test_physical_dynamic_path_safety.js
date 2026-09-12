'use strict';
const assert = require('assert');
const Safety = require('../physical/physical_dynamic_path_safety.js');
const PhysicalCapabilities = require('../../plugins/robot_windows/blockly/webeeblocks/physical_capability_contract.js');

function binding(program) {
  return PhysicalCapabilities.bindAst({version: 1, semantics: 'webeeblocks-ast-v1', program});
}

const representative = binding([
  {kind: 'takeoff', height_m: 0.8},
  {kind: 'set_variable', variable: {id: 'limit', name: 'limite'}, value: {kind: 'range', direction: 'front', unit: 'm'}},
  {kind: 'repeat', count: 2, body: [
    {kind: 'if', condition: {
      kind: 'logic', op: 'AND',
      left: {kind: 'compare', op: 'LT', left: {kind: 'range', direction: 'left', unit: 'm'}, right: {kind: 'variable_get', variable: {id: 'limit', name: 'limite'}}},
      right: {kind: 'compare', op: 'GT', left: {kind: 'range', direction: 'right', unit: 'm'}, right: {kind: 'number', value: 0.2}}
    }, then: [
      {kind: 'vertical', direction: 'up', distance_m: 0.2},
      {kind: 'set_light', color: 'green'},
      {kind: 'move', direction: 'left', distance_m: 0.3}
    ], else: [
      {kind: 'vertical', direction: 'down', distance_m: 0.1},
      {kind: 'turn', angle_deg: 45},
      {kind: 'wait', seconds: 0.2},
      {kind: 'set_speed', speed_m_s: 0.2}
    ]}
  ]},
  {kind: 'land'}
]);
const proof = Safety.proveBoundPhysicalProgram(representative);
assert.strictEqual(proof.compatible, true);
assert.strictEqual(proof.executionAuthority, false);
assert.strictEqual(proof.astBinding, representative);
assert.strictEqual(proof.initialNominalAltitudeM, 0.8);
assert.ok(Math.abs(proof.terminalNominalAltitudeMinM - 0.6) < 1e-12);
assert.ok(Math.abs(proof.terminalNominalAltitudeMaxM - 1.2) < 1e-12);
assert.ok(Object.isFrozen(proof), 'safety proof must be immutable and non-authority');

assert.throws(() => Safety.proveBoundPhysicalProgram(binding([
  {kind: 'takeoff', height_m: 0.8},
  {kind: 'if', condition: {kind: 'compare', op: 'EQ', left: {kind: 'number', value: 0}, right: {kind: 'number', value: 1}}, then: [
    {kind: 'vertical', direction: 'up', distance_m: 0.8}
  ], else: []},
  {kind: 'land'}
])), /can leave the established 0\.2-1\.5 m nominal-altitude envelope/,
'pre-takeoff proof must fail closed when any conservatively reachable branch can exceed altitude bounds');

assert.throws(() => Safety.proveBoundPhysicalProgram(binding([
  {kind: 'takeoff', height_m: 0.4},
  {kind: 'repeat', count: 3, body: [{kind: 'vertical', direction: 'down', distance_m: 0.1}]},
  {kind: 'land'}
])), /can leave the established 0\.2-1\.5 m nominal-altitude envelope/,
'repeat expansion must prove every intermediate nominal altitude, not only the terminal statement shape');

for (const [statement, pattern] of [
  [{kind: 'move', direction: 'forward', distance_m: 2.1}, /distance_m violates established physical bounds/],
  [{kind: 'vertical', direction: 'up', distance_m: 0.9}, /distance_m violates established physical bounds/],
  [{kind: 'turn', angle_deg: 180}, /angle_deg violates established physical bounds/],
  [{kind: 'wait', seconds: 5.1}, /seconds violates established physical bounds/],
  [{kind: 'set_speed', speed_m_s: 0.36}, /speed_m_s violates established physical bounds/],
  [{kind: 'set_light', color: 'purple'}, /color violates the established Runtime v2 palette/]
]) {
  assert.throws(() => Safety.proveBoundPhysicalProgram(binding([
    {kind: 'takeoff', height_m: 0.8}, statement, {kind: 'land'}
  ])), pattern);
}

const extraFieldAst = {version: 1, semantics: 'webeeblocks-ast-v1', program: [
  {kind: 'takeoff', height_m: 0.8},
  {kind: 'move', direction: 'forward', distance_m: 0.2, callerHint: 'ignore-me'},
  {kind: 'land'}
]};
assert.throws(
  () => Safety.proveBoundPhysicalProgram(PhysicalCapabilities.bindAst(extraFieldAst)),
  /contains unsupported fields/,
  'physical effect statements must not admit caller-selected extra fields even when the shared interpreter ignores them'
);
assert.throws(
  () => Safety.proveBoundPhysicalProgram(' ' + representative),
  /non-empty trimmed string/,
  'trusted host must consume the exact canonical binding, not reparsed equivalent text'
);

assert.throws(() => Safety.proveBoundPhysicalProgram(binding([
  {kind: 'takeoff', height_m: 0.8},
  {kind: 'if', condition: {kind: 'future_expression'}, then: [], else: []},
  {kind: 'land'}
])), /shared interpreter rejected AST/,
'dynamic safety proof must reuse the authoritative shared interpreter validation rather than silently accepting new semantics');

console.log('PASS exact shared-interpreter AST receives conservative pre-takeoff dynamic physical path proof without action authority');
