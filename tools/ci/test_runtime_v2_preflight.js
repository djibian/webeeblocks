'use strict';
const assert = require('assert');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const ActivityContract = require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract.js');
const SemanticAst = require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast.js');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');

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

(async function() {
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

  console.log('PASS Runtime v2 preflight rejects malformed AST and gives fail-closed student guidance for forbidden or disconnected Blockly programs');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
