'use strict';
const assert = require('assert');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const ActivityContract = require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract.js');
const SemanticAst = require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast.js');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js');
const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities.js');

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

function proveProgressionProfilesAndFieldOptions() {
  const p1 = Profiles.resolveById(Activities.DOCUMENT, 'progression-sequence-v1', Activities.BLOCK_CATALOG);
  const p2 = Profiles.resolveById(Activities.DOCUMENT, 'progression-repeat-v1', Activities.BLOCK_CATALOG);
  const p3 = Profiles.resolveById(Activities.DOCUMENT, 'progression-reactive-v1', Activities.BLOCK_CATALOG);

  assert.strictEqual(p1.world, p2.world);
  assert.strictEqual(p2.world, p3.world);
  assert(p1.toolbox.every(type => p2.toolbox.includes(type)), 'profile 2 must be cumulative over profile 1');
  assert(p2.toolbox.every(type => p3.toolbox.includes(type)), 'profile 3 must be cumulative over profile 2');
  assert(!p1.toolbox.includes('controls_repeat_ext'));
  assert(p2.toolbox.includes('controls_repeat_ext'));
  assert(!p2.toolbox.includes('webeeblocks_v2_range'));
  assert(p3.toolbox.includes('webeeblocks_v2_range'));
  assert(p3.toolbox.includes('controls_if'));
  assert(!p1.hardware.includes('multi-ranger-deck'));
  assert(!p2.hardware.includes('multi-ranger-deck'));
  assert(p3.hardware.includes('multi-ranger-deck'));
  assert.deepStrictEqual(p1.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward']);
  assert.deepStrictEqual(p3.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
  assert.deepStrictEqual(p3.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front']);

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
      getOptions() { return this.options.map(option => option.slice()); },
      setOptions(next) { this.options = next.map(option => option.slice()); },
      getValue() { return this.value; },
      setValue(value) { this.value = value; }
    };
  }

  const definitions = {
    webeeblocks_v2_move: {init() { this.fields = {DIRECTION:dropdown([['avancer','forward'],['reculer','back'],['aller à gauche','left'],['aller à droite','right']])}; }},
    webeeblocks_v2_range: {init() { this.fields = {DIRECTION:dropdown([['devant','front'],['derrière','back'],['à gauche','left'],['à droite','right'],['au-dessus','up']])}; }}
  };
  class FakeWorkspace {
    constructor() { this.blocks = []; }
    newBlock(type) {
      const block = {type, fields:{}, getField(name) { return this.fields[name] || null; }, dispose() {}};
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
  const workspace = new FakeWorkspace();
  const move = workspace.newBlock('webeeblocks_v2_move');
  assert.deepStrictEqual(move.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward']);

  controller.setProfile(p3, workspace);
  assert.deepStrictEqual(move.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward','left']);
  const range = workspace.newBlock('webeeblocks_v2_range');
  assert.deepStrictEqual(range.getField('DIRECTION').getOptions(false).map(option => option[1]), ['front']);

  const genericProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
  controller.setProfile(genericProfile, workspace);
  assert.deepStrictEqual(move.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward','back','left','right']);
  assert.deepStrictEqual(range.getField('DIRECTION').getOptions(false).map(option => option[1]), ['front','back','left','right','up']);

  move.getField('DIRECTION').setValue('left');
  controller.setProfile(p1, workspace);
  assert.strictEqual(move.getField('DIRECTION').getValue(), 'left',
    'profile filtering must not silently rewrite an existing student program');
  assert.deepStrictEqual(move.getField('DIRECTION').getOptions(false).map(option => option[1]), ['forward','back','left','right'],
    'an incompatible existing block must keep its generic menu until the student corrects it');
  assert.throws(() => ActivityContract.preflightWorkspace(p1, workspace), /field option forbidden by profile/,
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

  console.log('PASS Runtime v2 preflight + 66-A cumulative profiles/field options/fail-closed hidden capability checks');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
