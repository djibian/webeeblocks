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
  ['webeeblocks_v2_range', 'math_arithmetic'],
  ['logic_compare', 'controls_if', 'variables_set', 'variables_get', 'math_change'],
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
// A7 unlocks both valid logical and conditional-loop options, not just a
// subset of the choices already drawn on the Blockly blocks.
function verifyAllowedField(activity, type, field, value) {
  const {profile, options} = pages[activity - 1];
  const workspace = new Blockly.Workspace();
  try {
    const block = workspace.newBlock(type);
    block.setFieldValue(value, field);
    if (type === 'logic_operation') {
      const conditional = workspace.newBlock('controls_if');
      conditional.getInput('IF0').connection.connect(block.outputConnection);
    }
    assert.equal(block.getFieldValue(field), value);
    Contract.preflightWorkspace(profile, workspace);
    const saved = Projects.encodeProject(profile, workspace, options);
    Projects.validateProjectText(saved, profile, options);
  } finally {
    workspace.dispose();
  }
}
verifyAllowedField(7, 'logic_operation', 'OP', 'OR');
verifyAllowedField(7, 'controls_whileUntil', 'MODE', 'UNTIL');
for (const mode of ['WHILE', 'UNTIL'])
  assert(pages[6].profile.fieldOptions.controls_whileUntil.MODE.includes(mode));
for (const mode of ['AND', 'OR'])
  assert(pages[6].profile.fieldOptions.logic_operation.OP.includes(mode));
for (const op of ['ADD', 'MINUS', 'MULTIPLY', 'DIVIDE'])
  assert(pages[3].profile.fieldOptions.math_arithmetic.OP.includes(op));
for (const type of ['logic_compare', 'controls_if']) {
  assert(!pages[3].profile.toolbox.includes(type), type + ' must not be unlocked in A4');
  assert(pages[4].profile.toolbox.includes(type), type + ' must be unlocked in A5');
  const unavailable = new Blockly.Workspace();
  try {
    unavailable.newBlock(type);
    assert.throws(() => Contract.preflightWorkspace(pages[3].profile, unavailable),
      /block forbidden by profile/);
    assert(Contract.preflightWorkspace(pages[4].profile, unavailable));
  } finally {
    unavailable.dispose();
  }
}

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
const Interpreter = require(dir + 'interpreter');
const Outcome = require(dir + 'runtime_outcome');
function numeric(workspace, value) {
  const block = workspace.newBlock('math_number');
  block.setFieldValue(String(value), 'NUM');
  return block;
}
async function provePupilVocabulary() {
  // A4: a real pupil-built sensor MINUS safety margin is a valid movement
  // expression. The exact .wbb survives a new window and the AST interpreter
  // executes the computed displacement, not a hard-coded distance.
  const a4 = pages[3];
  const w = new Blockly.Workspace();
  try {
    const takeoff = w.newBlock('webeeblocks_v2_takeoff');
    const forward = w.newBlock('webeeblocks_v2_move');
    const left = w.newBlock('webeeblocks_v2_move');
    const land = w.newBlock('webeeblocks_v2_land');
    const minus = w.newBlock('math_arithmetic');
    const sensed = w.newBlock('webeeblocks_v2_range');
    minus.setFieldValue('MINUS', 'OP');
    sensed.setFieldValue('front', 'DIRECTION');
    minus.getInput('A').connection.connect(sensed.outputConnection);
    minus.getInput('B').connection.connect(numeric(w, 0.70).outputConnection);
    takeoff.getInput('HEIGHT').connection.connect(numeric(w, 0.50).outputConnection);
    forward.getInput('DISTANCE').connection.connect(minus.outputConnection);
    left.setFieldValue('left', 'DIRECTION');
    left.getInput('DISTANCE').connection.connect(numeric(w, 0.50).outputConnection);
    takeoff.nextConnection.connect(forward.previousConnection);
    forward.nextConnection.connect(left.previousConnection);
    left.nextConnection.connect(land.previousConnection);
    Contract.preflightWorkspace(a4.profile, w);
    const ast = Compiler.compileWorkspace(w);
    Contract.preflightAst(a4.profile, ast);
    assert.equal(ast.program[1].distance_m.kind, 'arithmetic');
    assert.equal(ast.program[1].distance_m.op, 'MINUS');
    const saved = Projects.encodeProject(a4.profile, w, a4.options);
    assert.deepEqual(Projects.validateProjectText(saved, a4.profile, a4.options).ast, ast);
    const old = new Blockly.Workspace();
    try {
      Blockly.serialization.workspaces.load(Blockly.serialization.workspaces.save(w), old);
      assert.deepEqual(Compiler.compileWorkspace(old), ast);
    } finally {
      old.dispose();
    }
    assert.throws(() => Contract.preflightWorkspace(pages[2].profile, w), /block forbidden by profile/);
    const effects = [];
    const backend = {
      async takeoff(height) { effects.push(['takeoff', height]); },
      async readRange(direction) { assert.equal(direction, 'front'); return 1.0; },
      async move(direction, distance) { effects.push([direction, distance]); },
      async land() { effects.push(['land']); }
    };
    await Interpreter.run(ast, backend, {maxSteps: 500});
    assert.deepEqual(effects.map(effect => effect[0]), ['takeoff', 'forward', 'left', 'land']);
    assert.equal(effects[0][1], 0.5);
    assert(Math.abs(effects[1][1] - 0.3) < 1e-9, 'sensor-minus-margin distance must remain precise');
    assert.equal(effects[2][1], 0.5);
  } finally {
    w.dispose();
  }

  // A5: the conditional structure and comparison both compile and pass the
  // current profile; the A4 profile refuses them without relaxing its oracle.
  const a5 = pages[4];
  const conditional = new Blockly.Workspace();
  try {
    const decision = conditional.newBlock('controls_if');
    decision.loadExtraState({elseIfCount: 1, hasElse: true});
    for (let i = 0; i <= 1; i++) {
      const compare = conditional.newBlock('logic_compare');
      compare.setFieldValue(i ? 'GTE' : 'LT', 'OP');
      compare.getInput('A').connection.connect(numeric(conditional, i).outputConnection);
      compare.getInput('B').connection.connect(numeric(conditional, 1).outputConnection);
      decision.getInput('IF' + i).connection.connect(compare.outputConnection);
    }
    assert(Contract.preflightWorkspace(a5.profile, conditional));
    assert.equal(Compiler.compileStatement(decision).else[0].kind, 'if');
    assert.throws(() => Contract.preflightWorkspace(a4.profile, conditional), /block forbidden by profile/);
  } finally {
    conditional.dispose();
  }

  // A7: OR is not merely a visible field; it feeds a bounded UNTIL loop and
  // produces executable AST without forcing a particular pupil syntax.
  const a7 = pages[6];
  const w7 = new Blockly.Workspace();
  try {
    const takeoff = w7.newBlock('webeeblocks_v2_takeoff');
    const bounded = w7.newBlock('controls_whileUntil');
    const logic = w7.newBlock('logic_operation');
    const land = w7.newBlock('webeeblocks_v2_land');
    takeoff.getInput('HEIGHT').connection.connect(numeric(w7, 0.5).outputConnection);
    bounded.setFieldValue('UNTIL', 'MODE');
    bounded.setFieldValue('2', 'MAX_ITERATIONS');
    logic.setFieldValue('OR', 'OP');
    for (const input of ['A', 'B']) {
      const compare = w7.newBlock('logic_compare');
      compare.setFieldValue(input === 'A' ? 'LT' : 'GT', 'OP');
      compare.getInput('A').connection.connect(numeric(w7, input === 'A' ? 1 : 0).outputConnection);
      compare.getInput('B').connection.connect(numeric(w7, input === 'A' ? 2 : 3).outputConnection);
      logic.getInput(input).connection.connect(compare.outputConnection);
    }
    bounded.getInput('BOOL').connection.connect(logic.outputConnection);
    takeoff.nextConnection.connect(bounded.previousConnection);
    bounded.nextConnection.connect(land.previousConnection);
    Contract.preflightWorkspace(a7.profile, w7);
    const ast = Compiler.compileWorkspace(w7);
    Contract.preflightAst(a7.profile, ast);
    assert.equal(ast.program[1].mode, 'UNTIL');
    assert.equal(ast.program[1].condition.op, 'OR');
    const file = Projects.encodeProject(a7.profile, w7, a7.options);
    assert.deepEqual(Projects.validateProjectText(file, a7.profile, a7.options).ast, ast);
    const effects = [];
    await Interpreter.run(ast, {
      capabilities: {conditionalLoops: true},
      async takeoff() { effects.push('takeoff'); },
      async land() { effects.push('land'); }
    }, {maxSteps: 500});
    assert.deepEqual(effects, ['takeoff', 'land']);
  } finally {
    w7.dispose();
  }

  // Exhausting the same physical safety limit must not masquerade as a
  // retryable preflight error or lose its intelligible pupil diagnosis.
  const infinite = {
    version: 1, semantics: 'webeeblocks-ast-v1',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {kind: 'while', mode: 'WHILE', max_iterations: 2,
        condition: {kind: 'compare', op: 'LT',
          left: {kind: 'number', value: 1}, right: {kind: 'number', value: 2}},
        body: [{kind: 'move', direction: 'forward', distance_m: 0.1}]},
      {kind: 'land'}
    ]
  };
  let loopError;
  const trace = [];
  try {
    await Interpreter.run(infinite, {
      capabilities: {conditionalLoops: true},
      async takeoff() { trace.push('takeoff'); },
      async move() { trace.push('move'); },
      async land() { trace.push('land'); }
    }, {maxSteps: 500});
  } catch (error) {
    loopError = error;
  }
  assert(loopError, 'loop iteration limit must interrupt execution');
  assert.equal(loopError.code, 'LOOP_ITERATION_LIMIT');
  assert.match(loopError.studentDetail, /2 itérations/);
  assert(!Outcome.isRetryable(loopError), 'an interrupted flight must require reset');
  const classified = Outcome.classify(loopError);
  assert.equal(classified.state, 'ARRÊTÉ');
  assert.match(classified.detail, /Réinitialisez/);
  assert.deepEqual(trace, ['takeoff', 'move', 'move']);
  assert.deepEqual(page().profile, a8.profile, 'A8 changed after teaching-profile tests');
}
provePupilVocabulary().then(() => {
  console.log('PASS seven Grand Prix vocabulary profiles, A4 sensor arithmetic, A5 conditionals, A7 OR/UNTIL, loop safety diagnostic and A8 unchanged');
}).catch(error => { console.error(error); process.exitCode = 1; });

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
