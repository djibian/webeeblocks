'use strict';

const assert = require('assert');
const {run, ScriptedBackend} = require('./interpreter.js');

function reactiveFixture() {
  return {
    version: 1,
    semantics: 'webeeblocks-experimental-ast',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {
        kind: 'repeat',
        count: 3,
        body: [
          {
            kind: 'if',
            condition: {
              kind: 'compare',
              op: 'LT',
              left: {kind: 'range', direction: 'front', unit: 'm'},
              right: {kind: 'number', value: 0.5}
            },
            then: [{kind: 'move', direction: 'left', distance_m: 0.3}],
            else: [{kind: 'move', direction: 'forward', distance_m: 0.3}]
          }
        ]
      },
      {kind: 'land'}
    ]
  };
}

(function provesReevaluationEveryIteration() {
  const backend = new ScriptedBackend({front: [0.4, 0.8, 0.3]});
  run(reactiveFixture(), backend);
  assert.deepStrictEqual(backend.trace, [
    {op: 'takeoff', height_m: 0.5},
    {op: 'range', direction: 'front', value_m: 0.4, read: 1},
    {op: 'move', direction: 'left', distance_m: 0.3},
    {op: 'range', direction: 'front', value_m: 0.8, read: 2},
    {op: 'move', direction: 'forward', distance_m: 0.3},
    {op: 'range', direction: 'front', value_m: 0.3, read: 3},
    {op: 'move', direction: 'left', distance_m: 0.3},
    {op: 'land'}
  ]);
})();

(function provesRangeIsNotCachedAcrossBranches() {
  const ast = reactiveFixture();
  ast.program[1].count = 2;
  const backend = new ScriptedBackend({front: [0.49, 0.51]});
  run(ast, backend);
  assert.strictEqual(backend.rangeOffsets.front, 2);
  assert.strictEqual(backend.trace[2].direction, 'left');
  assert.strictEqual(backend.trace[4].direction, 'forward');
})();

(function failsClosedWhenSensorDataRunsOut() {
  const backend = new ScriptedBackend({front: [0.4]});
  assert.throws(() => run(reactiveFixture(), backend), /no scripted range sample/);
})();

(function failsClosedOnUnknownStatement() {
  const ast = reactiveFixture();
  ast.program.splice(1, 0, {kind: 'avoid_obstacle'});
  assert.throws(() => run(ast, new ScriptedBackend({front: [1, 1, 1]})), /unsupported statement kind/);
})();

(function failsClosedOnInvalidRepeatCount() {
  const ast = reactiveFixture();
  ast.program[1].count = 21;
  assert.throws(() => run(ast, new ScriptedBackend({front: [1, 1, 1]})), /repeat count out of bounds/);
})();

(function failsClosedOnInvalidEnvelope() {
  const ast = reactiveFixture();
  ast.semantics = 'python';
  assert.throws(() => run(ast, new ScriptedBackend({front: [1, 1, 1]})), /unsupported AST envelope/);
})();

(function shortCircuitsLogicWithoutPhantomSensorRead() {
  const ast = {
    version: 1,
    semantics: 'webeeblocks-experimental-ast',
    program: [
      {kind: 'takeoff', height_m: 0.5},
      {
        kind: 'if',
        condition: {
          kind: 'logic', op: 'AND',
          left: {kind: 'compare', op: 'LT', left: {kind: 'number', value: 2}, right: {kind: 'number', value: 1}},
          right: {kind: 'compare', op: 'LT', left: {kind: 'range', direction: 'front', unit: 'm'}, right: {kind: 'number', value: 0.5}}
        },
        then: [{kind: 'move', direction: 'left', distance_m: 0.3}],
        else: [{kind: 'move', direction: 'forward', distance_m: 0.3}]
      },
      {kind: 'land'}
    ]
  };
  const backend = new ScriptedBackend({front: []});
  run(ast, backend);
  assert.strictEqual(backend.trace.some(e => e.op === 'range'), false);
  assert.strictEqual(backend.trace[1].direction, 'forward');
})();

console.log('PASS reactive AST interpreter: re-evaluation, branching, trace and fail-closed behavior');
