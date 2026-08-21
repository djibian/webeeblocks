'use strict';
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');

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

  console.log('PASS Runtime v2 whole-AST validation rejects before backend actions');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
