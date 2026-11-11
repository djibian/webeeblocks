#!/usr/bin/env node
'use strict';

// The real product toolbox produces editable numerical shadows. Verify their
// Blockly connections, exact AST, portable .wbb state and old explicit numbers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../..');
const Blockly = require(path.join(__dirname, 'node_modules/blockly'));
require(path.join(__dirname, 'node_modules/blockly/blocks'));
global.Blockly = Blockly;
require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js'));
delete global.Blockly;
const Activities = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Ast = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));
const Contract = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const Project = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/project_files.js'));
const source = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
const begin = source.indexOf('function categoryLabel(category) {');
const end = source.indexOf('function receiveMessage(value) {', begin);
assert(begin >= 0 && end > begin, 'toolbox functions available');
const context = {
  document: {createElement: tag => Blockly.utils.xml.createElement(tag)},
  WebeeBlocksActivities: Activities, WEBEEBLOCKS_CREATE_VARIABLE_CALLBACK: 'CREATE_VARIABLE',
  Blockly
};
vm.runInNewContext(source.slice(begin, end), context, {timeout: 1000});
const toolbox = profile => context.buildToolbox(profile);
const getBlock = (xml, type) => Array.from(xml.getElementsByTagName('block'))
  .find(node => node.getAttribute('type') === type);
function shadowValue(block, socket) {
  const value = Array.from(block.childNodes).find(node =>
    node.nodeType === 1 && node.tagName.toLowerCase() === 'value' &&
    node.getAttribute('name') === socket);
  assert(value, block.getAttribute('type') + '.' + socket + ' missing value');
  const shadow = Array.from(value.childNodes).find(node =>
    node.nodeType === 1 && node.tagName.toLowerCase() === 'shadow');
  assert(shadow && shadow.getAttribute('type') === 'math_number', socket + ' missing numeric shadow');
  const field = Array.from(shadow.childNodes).find(node =>
    node.nodeType === 1 && node.tagName.toLowerCase() === 'field' &&
    node.getAttribute('name') === 'NUM');
  assert(field, socket + ' missing editable NUM field');
  return Number(field.textContent);
}
function clamp(profile, preferred) {
  const limits = profile.parameterBounds?.math_number?.NUM || {};
  return Math.max(Number.isFinite(limits.min) ? limits.min : preferred,
    Math.min(preferred, Number.isFinite(limits.max) ? limits.max : preferred));
}
function motionDefault(profile, type) {
  const key = type === 'webeeblocks_v2_takeoff' ? 'takeoff.height_m' :
    type === 'webeeblocks_v2_vertical' ? 'vertical.distance_m' : 'move.distance_m';
  const n = type === 'webeeblocks_v2_takeoff' ? 0.5 :
    type === 'webeeblocks_v2_vertical' ? 0.2 : 0.3;
  const bounds = profile.runtime.astBounds[key] || {};
  return Math.max(Number.isFinite(bounds.min) ? bounds.min : n,
    Math.min(n, Number.isFinite(bounds.max) ? bounds.max : n));
}
const defaults = {
  controls_repeat_ext: {TIMES: 3},
  variables_set: {VALUE: 0},
  math_change: {DELTA: 1},
  logic_compare: {A: 0, B: 1},
  math_arithmetic: {A: 1, B: 1}
};
for (const id of [
  'progression-sequence-v1', 'progression-repeat-v1',
  'progression-simple-decision-v1', 'progression-memory-v1',
  'progression-autonomous-strategy-v1'
]) {
  const profile = Profiles.resolveById(Activities.DOCUMENT, id, Activities.BLOCK_CATALOG);
  const xml = toolbox(profile);
  assert.equal(xml.getAttribute('type'), null, 'toolbox must be an XML root');
  if (profile.toolbox.includes('math_number'))
    assert.equal(getBlock(xml, 'math_number'), undefined, id + ': number remains in flyout');
  for (const [type, sockets] of Object.entries(defaults)) {
    if (!profile.toolbox.includes(type)) continue;
    const block = getBlock(xml, type);
    assert(block, id + ': missing ' + type);
    for (const [socket, preferred] of Object.entries(sockets))
      assert.equal(shadowValue(block, socket), clamp(profile, preferred),
        id + ': ' + type + '.' + socket);
  }
  for (const type of ['webeeblocks_v2_takeoff', 'webeeblocks_v2_move', 'webeeblocks_v2_vertical']) {
    if (!profile.toolbox.includes(type)) continue;
    assert.equal(shadowValue(getBlock(xml, type), type === 'webeeblocks_v2_takeoff' ? 'HEIGHT' : 'DISTANCE'),
      motionDefault(profile, type), id + ': existing motion default changed');
  }
  for (const type of ['webeeblocks_v2_turn', 'webeeblocks_v2_wait', 'webeeblocks_v2_speed']) {
    if (profile.toolbox.includes(type))
      assert.equal(getBlock(xml, type).getElementsByTagName('shadow').length, 0,
        'numeric field unexpectedly converted into an expression: ' + type);
  }
}
// Exercise actual Blockly XML deserialization, not only a synthetic DOM assertion.
const profile = Profiles.resolveById(Activities.DOCUMENT, 'progression-memory-v1', Activities.BLOCK_CATALOG);
const xml = toolbox(profile);
const ws = new Blockly.Workspace();
function add(type) {
  const before = new Set(ws.getTopBlocks(false).map(b => b.id));
  const rootXml = Blockly.utils.xml.createElement('xml');
  const original = getBlock(xml, type);
  assert(original, 'profile toolbox must contain ' + type);
  rootXml.appendChild(original.cloneNode(true));
  Blockly.Xml.domToWorkspace(rootXml, ws);
  const block = ws.getTopBlocks(false).find(b => !before.has(b.id));
  assert(block && block.type === type, 'Blockly did not create ' + type);
  return block;
}
const set = add('variables_set'), takeoff = add('webeeblocks_v2_takeoff');
const change = add('math_change'), decision = add('controls_if');
const compare = add('logic_compare'), range = add('webeeblocks_v2_range');
const arithmetic = add('math_arithmetic'), move = add('webeeblocks_v2_move');
const land = add('webeeblocks_v2_land'), get = add('variables_get');
for (const [block, socket] of [[set,'VALUE'],[change,'DELTA'],[compare,'A'],[compare,'B'],
  [arithmetic,'A'],[arithmetic,'B'],[takeoff,'HEIGHT'],[move,'DISTANCE']])
  assert(block.getInputTargetBlock(socket)?.isShadow(), block.type + '.' + socket + ' must start editable');
const setShadow = set.getInputTargetBlock('VALUE');
set.getInput('VALUE').connection.connect(get.outputConnection);
assert.equal(set.getInputTargetBlock('VALUE'), get, 'variable must replace literal');
assert.equal(setShadow.getParent(), null, 'replaced shadow must not stay connected');
get.outputConnection.disconnect();
assert.equal(set.getInputTargetBlock('VALUE')?.type, 'math_number', 'disconnect must restore shadow');
get.dispose(); // Detached value is not part of the program's single main sequence.
assert.equal(ws.getBlocksByType('variables_get', false).length, 0, 'detached variable must be removed');
set.getInput('VALUE').connection.connect(arithmetic.outputConnection);
compare.getInput('A').connection.connect(range.outputConnection);
decision.getInput('IF0').connection.connect(compare.outputConnection);
decision.getInput('DO0').connection.connect(move.previousConnection);
set.nextConnection.connect(takeoff.previousConnection);
takeoff.nextConnection.connect(change.previousConnection);
change.nextConnection.connect(decision.previousConnection);
decision.nextConnection.connect(land.previousConnection);
Contract.preflightWorkspace(profile, ws);
const ast = Ast.compileWorkspace(ws);
assert.equal(ast.program[0].kind, 'set_variable');
assert.equal(ast.program[0].value.kind, 'arithmetic');
assert.equal(ast.program[0].value.left.value, clamp(profile, 1));
assert.equal(ast.program[0].value.right.value, clamp(profile, 1));
assert.equal(ast.program[1].height_m, motionDefault(profile, 'webeeblocks_v2_takeoff'));
assert.equal(ast.program[2].value.right.value, clamp(profile, 1));
assert.equal(ast.program[3].condition.left.kind, 'range');
assert.equal(ast.program[3].condition.right.value, clamp(profile, 1));
assert.equal(ast.program[3].then[0].distance_m, motionDefault(profile, 'webeeblocks_v2_move'));
const deps = {Blockly, profiles: Profiles, activitiesDocument: Activities.DOCUMENT,
  blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Ast, activityContract: Contract};
const encoded = Project.encodeProject(profile, ws, deps);
assert.equal(Project.parseProject(encoded).format, 'webeeblocks-project');
const validated = Project.validateProjectText(encoded, profile, deps);
assert.deepEqual(validated.ast, ast, 'Save/Open changed numerical constants or expressions');
const reopened = new Blockly.Workspace();
Blockly.serialization.workspaces.load(Project.parseProject(encoded).workspace, reopened);
assert.deepEqual(Ast.compileWorkspace(reopened), ast, '.wbb restore changed AST');
assert(reopened.getBlocksByType('math_number', false).some(b => b.isShadow()),
  'number shadows must survive .wbb reopening');
// Legacy explicit number blocks are valid and must not become shadows on opening.
const old = new Blockly.Workspace();
const explicit = old.newBlock('math_number');
explicit.setFieldValue('0.25', 'NUM');
const oldState = Blockly.serialization.workspaces.save(old);
const oldCopy = new Blockly.Workspace();
Blockly.serialization.workspaces.load(oldState, oldCopy);
assert.equal(oldCopy.getTopBlocks(false)[0].getFieldValue('NUM'), 0.25);
assert.equal(oldCopy.getTopBlocks(false)[0].isShadow(), false);
oldCopy.dispose(); old.dispose(); reopened.dispose(); ws.dispose();
console.log('PASS toolbox defaults: profiles, replacements, AST constants/expressions, .wbb Save/Open, legacy literals');
