'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Blockly = require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
const dir = '../../plugins/robot_windows/blockly/webeeblocks/';
global.Blockly = Blockly;
require(dir + 'crazyflie_v2');
const Compiler = require(dir + 'semantic_ast');
delete global.Blockly;
const Activities = require(dir + 'activities');
const Profiles = require(dir + 'activity_profiles');
const Contract = require(dir + 'activity_contract');
const Projects = require(dir + 'project_files');
const Progression = require(dir + 'grand_prix_progression');

const setup = fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/setup.js', 'utf8');
function page(lesson = null, progression = Progression) {
  const context = {
    WebeeBlocksActivities: Activities,
    WebeeBlocksGrandPrixProgression: progression,
    WebeeBlocksRuntimeOutcome: {classify() {}},
    WebeeBlocksWwiBackend: function() {},
    Blockly: {inject() {}},
    document: {currentScript: {getAttribute(name) {
      assert.equal(name, 'data-progression-activity');
      return lesson;
    }}}
  };
  context.window = context;
  vm.runInNewContext(setup, context);
  const activitiesDocument = context.WebeeBlocksActivities.DOCUMENT;
  const profile = Profiles.resolveById(activitiesDocument, context.WebeeBlocksInitialActivityId,
    Activities.BLOCK_CATALOG);
  return {profile, options: {Blockly, profiles: Profiles, activitiesDocument,
    blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Compiler, activityContract: Contract}};
}

const expectedIntroductions = [
  ['webeeblocks_v2_takeoff', 'webeeblocks_v2_move', 'webeeblocks_v2_turn',
    'webeeblocks_v2_speed', 'math_number', 'webeeblocks_v2_land'],
  ['webeeblocks_v2_vertical'],
  ['controls_repeat_ext'],
  ['webeeblocks_v2_range', 'logic_compare', 'controls_if'],
  ['variables_set', 'variables_get', 'math_change'],
  ['logic_operation'],
  ['controls_whileUntil', 'procedures_defnoreturn', 'procedures_callnoreturn']
];
const pages = expectedIntroductions.map((blocks, index) => {
  const activity = index + 1;
  const entry = page(String(activity));
  const {profile, options} = entry;
  assert.equal(profile.id, 'progression-grand-prix-a' + activity + '-v1');
  assert.equal(profile.starterVisible, true, 'blank activity starter must be available');
  assert.deepEqual(Array.from(options.activitiesDocument.activities).filter(candidate =>
    candidate.id.startsWith('progression-') && candidate.starterVisible !== false &&
    candidate.world === profile.world).map(candidate => candidate.id), [profile.id],
  'the classroom chooser must expose only the selected lesson, never A8 or another world');
  assert.equal(profile.evaluation.oracle, 'grand-prix-route-v2');
  const previous = expectedIntroductions.slice(0, index).flat();
  assert.deepEqual(profile.toolbox.filter(type => !previous.includes(type)), blocks);
  assert.deepEqual(profile.toolbox, [...previous, ...blocks]);
  assert.deepEqual(profile.runtime.moveDirections, activity < 4 ? ['forward', 'back'] :
    ['forward', 'back', 'left', 'right']);
  assert.deepEqual(profile.runtime.verticalDirections, activity === 1 ? [] : ['up', 'down']);
  assert.deepEqual(profile.runtime.rangeDirections, activity < 4 ? [] : ['front', 'back', 'left', 'right']);
  const starter = Projects.createStarterText(profile.id);
  const opened = Projects.validateProjectText(starter, profile, options);
  assert.deepEqual(opened.project.workspace.blocks.blocks, []);
  assert.equal(opened.ast, null);
  assert.deepEqual(Object.keys(opened.project.activity).sort(), ['id', 'semantics']);
  return entry;
});
assert.equal(new Set(pages.map(({profile}) => profile.world)).size, 7);
const a8 = page();
assert.equal(a8.profile.id, 'progression-grand-prix-route-v2');
assert.equal(a8.profile.world, 'worlds/grand_prix_route_v2.wbt');
assert(a8.profile.toolbox.includes('webeeblocks_v2_until'));
assert.deepEqual(page(null, null).profile, a8.profile, 'A8 needs no progression module');
for (const invalid of ['', '0', '8', '1.0', 'a1', '01'])
  assert.throws(() => page(invalid), /Profil pédagogique Grand Prix indisponible/);
assert.throws(() => page('1', null), /Profil pédagogique Grand Prix indisponible/);

function verifyField(pageNumber, type, field, accepted, rejected) {
  const {profile, options} = pages[pageNumber - 1];
  const workspace = new Blockly.Workspace();
  try {
    const block = workspace.newBlock(type);
    block.setFieldValue(accepted, field);
    if (type === 'logic_operation') {
      const conditional = workspace.newBlock('controls_if');
      conditional.getInput('IF0').connection.connect(block.outputConnection);
    }
    const project = Projects.encodeProject(profile, workspace, options);
    const parsed = Projects.parseProject(project);
    const top = parsed.workspace.blocks.blocks[0];
    const saved = type === 'logic_operation' ? top.inputs.IF0.block : top;
    assert.equal(saved.fields[field], accepted);
    Projects.validateProjectText(project, profile, options);
    saved.fields[field] = rejected;
    assert.throws(() => Projects.validateProjectText(JSON.stringify(parsed), profile, options),
      /workspace field forbidden by profile/);
    block.setFieldValue(rejected, field);
    assert.throws(() => Contract.preflightWorkspace(profile, workspace), /field option forbidden by profile/);
  } finally {
    workspace.dispose();
  }
}
verifyField(1, 'webeeblocks_v2_move', 'DIRECTION', 'back', 'left');
verifyField(6, 'logic_operation', 'OP', 'AND', 'OR');
verifyField(7, 'controls_whileUntil', 'MODE', 'WHILE', 'UNTIL');

const a1 = pages[0];
const workspace = new Blockly.Workspace();
try {
  const takeoff = workspace.newBlock('webeeblocks_v2_takeoff');
  const move = workspace.newBlock('webeeblocks_v2_move');
  const land = workspace.newBlock('webeeblocks_v2_land');
  for (const [action, socket, value] of [[takeoff, 'HEIGHT', .9], [move, 'DISTANCE', .2]]) {
    const number = workspace.newBlock('math_number');
    number.setFieldValue(String(value), 'NUM');
    action.getInput(socket).connection.connect(number.outputConnection);
  }
  move.setFieldValue('back', 'DIRECTION');
  takeoff.nextConnection.connect(move.previousConnection);
  move.nextConnection.connect(land.previousConnection);
  const beforeSave = Compiler.compileWorkspace(workspace);
  const text = Projects.encodeProject(a1.profile, workspace, a1.options);
  assert.deepEqual(Projects.validateProjectText(text, page('1').profile, a1.options).ast, beforeSave);
  assert.throws(() => Projects.validateProjectText(text, a8.profile, a8.options), /activity id must resolve exactly once/);
  assert.throws(() => Projects.validateProjectText(text, pages[1].profile, {
    ...a1.options, activitiesDocument: {version: 1, activities: [a1.profile, pages[1].profile]}
  }), /incompatible with the current Webots world/);
} finally {
  workspace.dispose();
}
assert.deepEqual(pages[6].profile.parameterBounds.controls_whileUntil.MAX_ITERATIONS,
  {min: 1, max: 100, step: 1});
assert.deepEqual(page().profile, a8.profile, 'generating lessons altered the A8 contract');
console.log('PASS seven cumulative Grand Prix profiles, real Blockly, portable starters and field refusal');
