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
// Contract-level roundtrip across all lessons using the existing project-file
// manager and actual Blockly 13.2.1. Native dialogs and Webots still require
// separate Windows/Linux graphical acceptance.
async function verifySameFileSaveOpen() {
  for (const {profile, options} of pages) {
    const live = new Blockly.Workspace();
    const reference = {value: profile};
    const fileHandle = {id: profile.id};
    const state = {bytes: null, name: null, saves: 0, opens: 0};
    const transport = {
      nativeFileSystemAccess: true,
      async saveAs(name, text) {
        assert.equal(state.saves, 0, 'Save As must be the first file write');
        state.bytes = text;
        state.name = name;
        state.saves++;
        return {handle: fileHandle, name, mode: 'test'};
      },
      async save(handle, name, text) {
        assert.strictEqual(handle, fileHandle, 'Save must reuse selected target');
        assert.equal(name, state.name);
        state.bytes = text;
        state.saves++;
        return {handle, name, mode: 'test'};
      },
      async open() {
        assert(state.bytes && state.name, 'nothing saved for reopening');
        state.opens++;
        return {handle: fileHandle, name: state.name, text: state.bytes, mode: 'test'};
      },
      async release() {}
    };
    const manager = Projects.createManager({
      ...options, workspace: live, transport,
      getProfile: () => reference.value,
      setProfile: next => { reference.value = next; }
    });
    try {
      const starter = Projects.createStarterText(profile.id);
      await manager.openTemplateText(profile.id + '.wbb', starter);
      assert.equal(manager.hasCurrentTarget(), false, 'starter is never a save target');
      const takeoff = live.newBlock('webeeblocks_v2_takeoff');
      const move = live.newBlock('webeeblocks_v2_move');
      const land = live.newBlock('webeeblocks_v2_land');
      for (const [motion, input, value] of [
        [takeoff, 'HEIGHT', .9], [move, 'DISTANCE', .2]
      ]) {
        const number = live.newBlock('math_number');
        number.setFieldValue(String(value), 'NUM');
        motion.getInput(input).connection.connect(number.outputConnection);
      }
      move.setFieldValue('forward', 'DIRECTION');
      takeoff.nextConnection.connect(move.previousConnection);
      move.nextConnection.connect(land.previousConnection);
      const expected = manager.encodeCurrent();
      const validated = Projects.validateProjectText(expected, profile, options);
      assert(validated.ast && validated.ast.program.length === 3);
      await manager.saveAs('eleve-' + profile.id + '.wbb');
      assert.equal(manager.hasCurrentTarget(), true);
      assert.equal(state.bytes, expected);
      await manager.save();
      assert.equal(state.bytes, expected, 'Save changed a clean project');
      assert.equal(state.saves, 2);
      live.clear(); // Simulate leaving the program before Open.
      assert.equal(live.getAllBlocks().length, 0);
      const opened = await manager.open();
      assert.equal(opened.name, state.name);
      assert.equal(state.opens, 1);
      assert.equal(manager.encodeCurrent(), expected,
        'Open must recover the exact editable .wbb without changing project bytes');
      assert.deepEqual(Compiler.compileWorkspace(live), validated.ast,
        'reopened Blockly program must preserve its executable AST');
      assert.equal(reference.value.id, profile.id);
    } finally {
      live.dispose();
    }
  }
}
verifySameFileSaveOpen().then(() => {
  console.log('PASS seven cumulative profiles, selectable blank starters, same-file Save/Open and A8 isolation');
}, error => { console.error(error); process.exitCode = 1; });
