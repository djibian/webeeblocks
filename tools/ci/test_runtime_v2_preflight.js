'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const ActivityContract = require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract.js');
const SemanticAst = require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast.js');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js');
const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities.js');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');

let actions = 0;
const backend = {
  takeoff: async () => { actions++; },
  land: async () => { actions++; },
  move: async () => { actions++; },
  vertical: async () => { actions++; },
  turn: async () => { actions++; },
  wait: async () => { actions++; },
  setSpeed: async () => { actions++; },
  readRange: async () => { actions++; return 0.4; }
};

async function mustReject(ast, pattern) {
  actions = 0;
  let rejected = false;
  try {
    await Interpreter.run(ast, backend);
  } catch (error) {
    rejected = pattern.test(String(error));
  }
  if (!rejected)
    throw new Error('malformed AST was not rejected as expected');
  if (actions !== 0)
    throw new Error('malformed AST reached backend before rejection: ' + actions);
}

function mustRejectStudentValidation(action, detailPattern) {
  let error = null;
  try { action(); } catch (caught) { error = caught; }
  assert(error, 'student program validation did not reject');
  assert.strictEqual(error.code, 'PROGRAM_INVALID');
  assert(detailPattern.test(error.studentDetail), 'unexpected student detail: ' + error.studentDetail);
  const outcome = Outcome.classify(error);
  assert.strictEqual(outcome.state, 'À CORRIGER');
  assert.strictEqual(outcome.machineCode, 'PROGRAM_INVALID');
  assert(detailPattern.test(outcome.detail), 'validation detail was not preserved in runtime outcome');
}

async function proveUnavailableBackendCapabilityIsStudentCorrectable() {
  let currentAst = {
    version: 1,
    semantics: 'webeeblocks-ast-v1',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {kind: 'turn', angle_deg: 90},
      {kind: 'land'}
    ]
  };
  let interpreterRuns = 0;
  let backendActions = 0;
  const testBackend = {
    capabilities: {
      actions: ['takeoff', 'move', 'land'],
      rangeDirections: ['front'],
      moveDirections: ['forward', 'left'],
      verticalDirections: []
    },
    async takeoff() { backendActions++; },
    async land() { backendActions++; },
    async turn() { backendActions++; }
  };
  const testInterpreter = {
    async run(ast, selectedBackend) {
      interpreterRuns++;
      for (const statement of ast.program) {
        if (statement.kind === 'takeoff') await selectedBackend.takeoff(statement.height_m);
        else if (statement.kind === 'turn') await selectedBackend.turn(statement.angle_deg);
        else if (statement.kind === 'land') await selectedBackend.land();
      }
    }
  };
  const profile = {
    toolbox: ['allowed'],
    parameterBounds: {},
    runtime: {
      allowedStatementKinds: ['takeoff', 'turn', 'land'],
      rangeDirections: [],
      moveDirections: [],
      verticalDirections: [],
      astBounds: {}
    }
  };
  const workspace = {getAllBlocks: () => [{type: 'allowed'}]};
  const compiler = {compileWorkspace: () => currentAst};

  let error = null;
  try {
    await ActivityContract.execute(profile, workspace, compiler, testInterpreter, testBackend);
  } catch (caught) { error = caught; }
  assert(error, 'unsupported visible backend capability was not rejected');
  assert.strictEqual(error.code, 'PROGRAM_INVALID');
  assert.strictEqual(error.studentDetail, 'Ce bloc n’est pas pris en charge dans cette simulation. Modifiez le programme avant de relancer.');
  assert.deepStrictEqual(Outcome.classify(error), {
    state: 'À CORRIGER',
    detail: 'Ce bloc n’est pas pris en charge dans cette simulation. Modifiez le programme avant de relancer.',
    machineCode: 'PROGRAM_INVALID'
  });
  assert.strictEqual(Outcome.isRetryable(error), true);
  assert.strictEqual(interpreterRuns, 0, 'unsupported capability reached interpreter');
  assert.strictEqual(backendActions, 0, 'unsupported capability executed backend action before rejection');

  currentAst = {
    version: 1,
    semantics: 'webeeblocks-ast-v1',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {kind: 'land'}
    ]
  };
  await ActivityContract.execute(profile, workspace, compiler, testInterpreter, testBackend);
  assert.strictEqual(interpreterRuns, 1, 'corrected program was not retryable without reset');
  assert.strictEqual(backendActions, 2, 'corrected program did not execute normally');
}


function proveProgressionStarterFiles() {
  const expected = [
    ['01-sequence.wbb', 'progression-sequence-v1'],
    ['02-precise-movement.wbb', 'progression-precise-movement-v1'],
    ['03-repeat.wbb', 'progression-repeat-v1'],
    ['04-simple-decision.wbb', 'progression-simple-decision-v1'],
    ['05-reactive.wbb', 'progression-reactive-v1'],
    ['06-multi-perception.wbb', 'progression-combined-decisions-v1'],
    ['07-memory.wbb', 'progression-memory-v1'],
    ['08-autonomous-strategy.wbb', 'progression-autonomous-strategy-v1']
  ];
  const directory = path.resolve(__dirname, '../../activities/progression');
  const files = fs.readdirSync(directory).filter(name => name.endsWith('.wbb')).sort();
  assert.deepStrictEqual(files, expected.map(entry => entry[0]),
    'progression starter filenames must provide one unambiguous ordered activity spine');
  for (const [filename, activityId] of expected) {
    const project = JSON.parse(fs.readFileSync(path.join(directory, filename), 'utf8'));
    assert.strictEqual(project.activity.id, activityId, filename + ' must target its numbered progression profile');
    assert.strictEqual(project.activity.semantics, 'webeeblocks-ast-v1', filename);
  }
}

function proveProgressionProfilesAndFieldOptions() {
  const p1 = Profiles.resolveById(Activities.DOCUMENT, 'progression-sequence-v1', Activities.BLOCK_CATALOG);
  const pPrecision = Profiles.resolveById(Activities.DOCUMENT, 'progression-precise-movement-v1', Activities.BLOCK_CATALOG);
  const p2 = Profiles.resolveById(Activities.DOCUMENT, 'progression-repeat-v1', Activities.BLOCK_CATALOG);
  const pDecision = Profiles.resolveById(Activities.DOCUMENT, 'progression-simple-decision-v1', Activities.BLOCK_CATALOG);
  const p3 = Profiles.resolveById(Activities.DOCUMENT, 'progression-reactive-v1', Activities.BLOCK_CATALOG);
  const p4 = Profiles.resolveById(Activities.DOCUMENT, 'progression-combined-decisions-v1', Activities.BLOCK_CATALOG);
  const p5 = Profiles.resolveById(Activities.DOCUMENT, 'progression-memory-v1', Activities.BLOCK_CATALOG);
  const p6 = Profiles.resolveById(Activities.DOCUMENT, 'progression-autonomous-strategy-v1', Activities.BLOCK_CATALOG);

  assert.strictEqual(p1.world, pPrecision.world);
  assert.strictEqual(pPrecision.world, p2.world);
  assert.strictEqual(p2.world, pDecision.world);
  assert.strictEqual(pDecision.world, p3.world);
  assert.strictEqual(p3.world, p4.world);
  assert.strictEqual(p4.world, p5.world);
  assert.strictEqual(p5.world, p6.world);
  assert(p1.toolbox.every(type => pPrecision.toolbox.includes(type)), 'precise-movement profile must reuse sequence blocks');
  assert(pPrecision.toolbox.every(type => p2.toolbox.includes(type)), 'repeat profile must reuse precise-movement blocks');
  assert(pPrecision.toolbox.every(type => pDecision.toolbox.includes(type)), 'simple-decision profile must reuse movement blocks');
  assert(!pDecision.toolbox.includes('controls_repeat_ext'), 'simple decision must stay focused before repeated reaction');
  assert(p2.toolbox.every(type => p3.toolbox.includes(type)), 'reactive profile must reuse repetition blocks');
  assert(pDecision.toolbox.every(type => p3.toolbox.includes(type)), 'reactive profile must combine simple decision with repetition');
  assert(p3.toolbox.every(type => p4.toolbox.includes(type)), 'profile 4 must be cumulative over profile 3');
  assert(p4.toolbox.every(type => p5.toolbox.includes(type)), 'profile 5 must be cumulative over profile 4');
  assert(p5.toolbox.every(type => p6.toolbox.includes(type)), 'profile 6 must be cumulative over profile 5');
  assert(!p1.toolbox.includes('controls_repeat_ext'));
  assert(p2.toolbox.includes('controls_repeat_ext'));
  assert(!p2.toolbox.includes('webeeblocks_v2_range'));
  assert(p3.toolbox.includes('webeeblocks_v2_range'));
  assert(p3.toolbox.includes('controls_if'));
  assert(!p3.toolbox.includes('logic_operation'));
  assert(p4.toolbox.includes('logic_operation'));
  assert(p5.toolbox.includes('variables_set') && p5.toolbox.includes('variables_get'));
  assert(p6.toolbox.includes('webeeblocks_v2_vertical'));
  assert(p6.toolbox.includes('webeeblocks_v2_turn'));
  assert(p6.toolbox.includes('webeeblocks_v2_wait'));
  assert(p6.toolbox.includes('webeeblocks_v2_light'));
  assert(!p6.toolbox.includes('webeeblocks_v2_speed'), 'compact progression does not need speed selection in its open-strategy profile');
  assert(!p1.hardware.includes('multi-ranger-deck'));
  assert(!p2.hardware.includes('multi-ranger-deck'));
  assert(p3.hardware.includes('multi-ranger-deck'));
  assert.deepStrictEqual(p1.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward']);
  assert.deepStrictEqual(pPrecision.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
  assert.deepStrictEqual(pPrecision.runtime.moveDirections, ['forward','left']);
  assert.deepStrictEqual(p2.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
  assert.deepStrictEqual(pDecision.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
  assert.deepStrictEqual(pDecision.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front']);
  assert.deepStrictEqual(pDecision.runtime.rangeDirections, ['front']);
  assert(!pDecision.runtime.allowedStatementKinds.includes('repeat'));
  assert.deepStrictEqual(pDecision.parameterBounds.math_number.NUM, {min:1,max:2,step:1});
  assert(pDecision.parameterBounds.math_number.NUM.min >= p3.parameterBounds.math_number.NUM.min &&
    pDecision.parameterBounds.math_number.NUM.max <= p3.parameterBounds.math_number.NUM.max &&
    pDecision.parameterBounds.math_number.NUM.step === p3.parameterBounds.math_number.NUM.step,
    'reactive profile must preserve the simple-decision numeric domain');
  assert.deepStrictEqual(p3.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
  assert.deepStrictEqual(p3.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front']);
  assert.deepStrictEqual(p4.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
  assert.deepStrictEqual(p4.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front','left','right']);
  assert.deepStrictEqual(p4.runtime.rangeDirections, ['front','left','right']);
  assert.deepStrictEqual(p6.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front','back','left','right']);
  assert.deepStrictEqual(p6.runtime.rangeDirections, ['front','back','left','right']);
  assert.deepStrictEqual(p6.runtime.moveDirections, ['forward','back','left','right']);
  assert.deepStrictEqual(p6.runtime.verticalDirections, ['up','down']);
  assert(p6.runtime.allowedStatementKinds.includes('set_variable'));
  assert(p6.runtime.allowedStatementKinds.includes('set_light'));
  assert(!p6.runtime.allowedStatementKinds.includes('set_speed'));
  assert.deepStrictEqual(p2.parameterBounds.math_number.NUM, {min:1,max:10,step:1});
  assert.deepStrictEqual(p3.parameterBounds.math_number.NUM, p2.parameterBounds.math_number.NUM,
    'profile 3 must preserve the repeat-count numeric bound introduced by profile 2');
  assert.deepStrictEqual(p4.parameterBounds.math_number.NUM, p3.parameterBounds.math_number.NUM,
    'profile 4 must preserve the cumulative repeat-count numeric bound');
  assert.deepStrictEqual(SemanticAst.LIMITS.speed_m_s, {min:0.1,max:0.6}, 'backend-neutral AST keeps the generic speed vocabulary');
  const currentWebotsCapabilities = new WwiBackend({send() {}}, {timeoutMs:50}).capabilities;
  assert(currentWebotsCapabilities.actions.includes('set_speed'), 'Webots backend must advertise proven set_speed support');
  const genericProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
  assert.deepStrictEqual(genericProfile.parameterBounds.webeeblocks_v2_speed.SPEED, {min:0.1,max:0.35,step:0.05});
  assert.deepStrictEqual(genericProfile.runtime.astBounds['set_speed.speed_m_s'], {min:0.1,max:0.35});
  const backendActionKinds = ['takeoff','move','vertical','turn','wait','set_speed','set_light','land'];
  const requiredBackendActions = p4.runtime.allowedStatementKinds.filter(kind => backendActionKinds.includes(kind));
  assert(requiredBackendActions.every(kind => currentWebotsCapabilities.actions.includes(kind)),
    'profile 4 must not expose an unproven Webots backend action');
  assert(p4.runtime.rangeDirections.every(direction => currentWebotsCapabilities.rangeDirections.includes(direction)),
    'profile 4 must not expose an unproven Webots range direction');
  assert(p4.runtime.moveDirections.every(direction => currentWebotsCapabilities.moveDirections.includes(direction)),
    'profile 4 must not expose an unproven Webots move direction');
  assert(p4.runtime.verticalDirections.every(direction => currentWebotsCapabilities.verticalDirections.includes(direction)),
    'profile 4 must not expose an unproven Webots vertical direction');
  const requiredP6Actions = p6.runtime.allowedStatementKinds.filter(kind => backendActionKinds.includes(kind));
  assert(requiredP6Actions.every(kind => currentWebotsCapabilities.actions.includes(kind)),
    'profile 6 must not expose an unproven Webots backend action');
  assert(p6.runtime.rangeDirections.every(direction => currentWebotsCapabilities.rangeDirections.includes(direction)),
    'profile 6 must not expose an unproven Webots range direction');
  assert(p6.runtime.moveDirections.every(direction => currentWebotsCapabilities.moveDirections.includes(direction)),
    'profile 6 must not expose an unproven Webots move direction');
  assert(p6.runtime.verticalDirections.every(direction => currentWebotsCapabilities.verticalDirections.includes(direction)),
    'profile 6 must not expose an unproven Webots vertical direction');

  const duplicate = JSON.parse(JSON.stringify(p1));
  duplicate.fieldOptions.webeeblocks_v2_move.DIRECTION = ['forward','forward'];
  assert.throws(() => Profiles.validateProfile(duplicate, Activities.BLOCK_CATALOG), /duplicate field option/);
  const hidden = JSON.parse(JSON.stringify(p1));
  hidden.fieldOptions.webeeblocks_v2_range = {DIRECTION:['front']};
  assert.throws(() => Profiles.validateProfile(hidden, Activities.BLOCK_CATALOG), /hidden block/);

  function dropdown(options) {
    return {
      options: options.map(option => option.slice()),
      value: options[0][1],
      setOptionsCalls: 0,
      getOptions() { return this.options.map(option => option.slice()); },
      setOptions(next) {
        this.setOptionsCalls += 1;
        this.options = next.map(option => option.slice());
        this.value = this.options[0][1];
      },
      getValue() { return this.value; },
      setValue(value) { this.value = value; }
    };
  }

  const definitions = {
    webeeblocks_v2_move: {init() { this.fields = {DIRECTION:dropdown([['avancer','forward'],['reculer','back'],['aller à gauche','left'],['aller à droite','right']])}; }},
    webeeblocks_v2_range: {init() { this.fields = {DIRECTION:dropdown([['devant','front'],['derrière','back'],['à gauche','left'],['à droite','right'],['au-dessus','up']])}; }}
  };
  class FakeWorkspace {
    constructor(isFlyout) { this.blocks = []; this.isFlyout = !!isFlyout; }
    newBlock(type) {
      const block = {type, fields:{}, isInFlyout:this.isFlyout, getField(name) { return this.fields[name] || null; }, dispose() {}};
      definitions[type].init.call(block);
      this.blocks.push(block);
      return block;
    }
    getAllBlocks() { return this.blocks.slice(); }
    getToolbox() { return null; }
    dispose() {}
  }
  const FakeBlockly = {Blocks:definitions, Workspace:FakeWorkspace};
  const controller = Profiles.createFieldOptionController(Activities.DOCUMENT, Activities.BLOCK_CATALOG, FakeBlockly);

  controller.setProfile(p1, null);
  const flyoutWorkspace = new FakeWorkspace(true);
  const flyoutMove = flyoutWorkspace.newBlock('webeeblocks_v2_move');
  assert.deepStrictEqual(flyoutMove.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward']);
  const callsBeforeNoop = flyoutMove.getField('DIRECTION').setOptionsCalls;
  controller.applyWorkspace(flyoutWorkspace);
  assert.strictEqual(flyoutMove.getField('DIRECTION').setOptionsCalls, callsBeforeNoop,
    'reapplying an already-correct profile menu must be a Blockly no-op');

  controller.setProfile(p3, flyoutWorkspace);
  assert.deepStrictEqual(flyoutMove.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward','left']);
  const flyoutRange = flyoutWorkspace.newBlock('webeeblocks_v2_range');
  assert.deepStrictEqual(flyoutRange.getField('DIRECTION').getOptions(false).map(option => option[1]), ['front']);

  const genericFlyoutProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
  controller.setProfile(genericFlyoutProfile, flyoutWorkspace);
  assert.deepStrictEqual(flyoutMove.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward','back','left','right']);
  assert.deepStrictEqual(flyoutRange.getField('DIRECTION').getOptions(false).map(option => option[1]), ['front','back','left','right','up']);

  controller.setProfile(genericProfile, null);
  const workspace = new FakeWorkspace(false);
  const move = workspace.newBlock('webeeblocks_v2_move');
  move.getField('DIRECTION').setValue('left');
  controller.setProfile(p1, workspace);
  assert.strictEqual(move.getField('DIRECTION').getValue(), 'left',
    'profile filtering must not silently rewrite an existing student program');
  assert.deepStrictEqual(move.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward','back','left','right'],
    'an incompatible existing block must keep its generic menu until the student corrects it');

  const preservedWorkspace = {
    getAllBlocks() {
      return [{type:'webeeblocks_v2_move', getField(name) { return name === 'DIRECTION' ? {getValue:() => 'left'} : null; }}];
    }
  };
  assert.throws(() => ActivityContract.preflightWorkspace(p1, preservedWorkspace), /field option forbidden by profile/,
    'the authority boundary must reject the preserved incompatible value');

  const forbiddenWorkspace = {
    getAllBlocks() {
      return [{type:'webeeblocks_v2_move', getField(name) { return name === 'DIRECTION' ? {getValue:() => 'right'} : null; }}];
    }
  };
  mustRejectStudentValidation(
    () => ActivityContract.preflightWorkspace(p1, forbiddenWorkspace),
    /option de ce programme/
  );
  assert.throws(
    () => ActivityContract.preflightAst(p1, {program:[{kind:'move',direction:'right',distance_m:0.5}]}),
    /move direction unavailable/
  );
}

(async function() {
  proveProgressionStarterFiles();
  proveProgressionProfilesAndFieldOptions();
  await mustReject({
    version: 1,
    semantics: 'webeeblocks-ast-v1',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {kind: 'repeat', count: 1, body: [{kind: 'land'}]},
      {kind: 'land'}
    ]
  }, /top-level boundaries/);

  await mustReject({
    version: 1,
    semantics: 'webeeblocks-ast-v1',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {kind: 'if', condition: {kind: 'unknown_expression'}, then: [], else: []},
      {kind: 'land'}
    ]
  }, /unsupported expression kind/);

  await mustReject({
    version: 1,
    semantics: 'webeeblocks-ast-v1',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {kind: 'move', direction: 'forward', distance_m: NaN},
      {kind: 'land'}
    ]
  }, /must be finite/);

  mustRejectStudentValidation(
    () => SemanticAst.compileWorkspace({getTopBlocks: () => [{type: 'webeeblocks_v2_takeoff'}, {type: 'webeeblocks_v2_land'}]}),
    /détachés du programme principal/
  );
  mustRejectStudentValidation(
    () => SemanticAst.compileWorkspace({getTopBlocks: () => []}),
    /programme relié/
  );
  mustRejectStudentValidation(
    () => SemanticAst.compileWorkspace({getTopBlocks: () => [{
      type: 'webeeblocks_v2_takeoff',
      getFieldValue: name => name === 'HEIGHT' ? 0.5 : null,
      getNextBlock: () => null
    }]}),
    /se terminer par « atterrir »/
  );

  let compilerCalled = false;
  let interpreterCalled = false;
  let validationError = null;
  try {
    await ActivityContract.execute(
      {toolbox: ['webeeblocks_v2_takeoff'], parameterBounds: {}, runtime: {}},
      {getAllBlocks: () => [{type: 'logic_negate'}]},
      {compileWorkspace: () => { compilerCalled = true; return {}; }},
      {run: async () => { interpreterCalled = true; }},
      {}
    );
  } catch (error) { validationError = error; }
  assert(validationError, 'forbidden Blockly block was not rejected');
  assert.strictEqual(validationError.code, 'PROGRAM_INVALID');
  assert(/pas disponible dans cette activité/.test(validationError.studentDetail));
  assert.strictEqual(compilerCalled, false, 'forbidden block reached AST compiler');
  assert.strictEqual(interpreterCalled, false, 'forbidden block reached interpreter/backend path');
  assert.deepStrictEqual(Outcome.classify(validationError), {
    state: 'À CORRIGER',
    detail: 'Un bloc de ce programme n’est pas disponible dans cette activité. Supprimez-le avant de lancer.',
    machineCode: 'PROGRAM_INVALID'
  });

  await proveUnavailableBackendCapabilityIsStudentCorrectable();

  console.log('PASS Runtime v2 preflight + compact #66 pedagogical granularity/current-Webots capability/fail-closed checks');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
