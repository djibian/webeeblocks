const assert = require('assert');
const Extended = require('./extended_blocks.js');

function block(type, fields, inputs) {
  return {
    type,
    _fields: fields || {},
    _inputs: inputs || {},
    _next: null,
    getFieldValue(name) { return this._fields[name]; },
    getInputTargetBlock(name) { return this._inputs[name] || null; },
    getNextBlock() { return this._next; },
    next(other) { this._next = other; return other; }
  };
}

function workspace(top) {
  return { getTopBlocks() { return [top]; } };
}

function number(n) { return block('math_number', {NUM: n}); }
function range(direction) { return block('webeeblocks_exp_range', {DIRECTION: direction}); }
function compare(op, a, b) { return block('logic_compare', {OP: op}, {A: a, B: b}); }

(function simpleMotionProgram() {
  const takeoff = block('webeeblocks_exp_takeoff', {HEIGHT: 0.5});
  const speed = takeoff.next(block('webeeblocks_exp_speed', {SPEED: 0.3}));
  const forward = speed.next(block('webeeblocks_exp_move', {DIRECTION: 'forward', DISTANCE: 0.5}));
  const left = forward.next(block('webeeblocks_exp_move', {DIRECTION: 'left', DISTANCE: 0.3}));
  const up = left.next(block('webeeblocks_exp_vertical', {DIRECTION: 'up', DISTANCE: 0.2}));
  const turn = up.next(block('webeeblocks_exp_turn', {DIRECTION: 'right', ANGLE: 90}));
  const wait = turn.next(block('webeeblocks_exp_wait', {SECONDS: 0.5}));
  wait.next(block('webeeblocks_exp_land'));

  const ast = Extended.compileWorkspace(workspace(takeoff));
  assert.deepStrictEqual(ast.program.map(x => x.kind), ['takeoff','set_speed','move','move','vertical','turn','wait','land']);
  assert.strictEqual(ast.program[0].height_m, 0.5);
  assert.strictEqual(ast.program[2].direction, 'forward');
  assert.strictEqual(ast.program[3].direction, 'left');
  assert.strictEqual(ast.program[5].angle_deg, -90);
})();

(function reactiveAvoidanceStructure() {
  const takeoff = block('webeeblocks_exp_takeoff', {HEIGHT: 0.5});
  const repeat = takeoff.next(block('controls_repeat_ext', {TIMES: 3}));
  const condition = compare('LT', range('front'), number(0.5));
  const ifBlock = block('controls_if', {}, {IF0: condition});
  const sidestep = block('webeeblocks_exp_move', {DIRECTION: 'left', DISTANCE: 0.3});
  const forward = block('webeeblocks_exp_move', {DIRECTION: 'forward', DISTANCE: 0.3});
  ifBlock._inputs.DO0 = sidestep;
  ifBlock._inputs.ELSE = forward;
  repeat._inputs.DO = ifBlock;
  repeat.next(block('webeeblocks_exp_land'));

  const ast = Extended.compileWorkspace(workspace(takeoff));
  assert.strictEqual(ast.program[1].kind, 'repeat');
  assert.strictEqual(ast.program[1].count, 3);
  const decision = ast.program[1].body[0];
  assert.strictEqual(decision.kind, 'if');
  assert.deepStrictEqual(decision.condition, {
    kind: 'compare', op: 'LT',
    left: {kind: 'range', direction: 'front', unit: 'm'},
    right: {kind: 'number', value: 0.5}
  });
  assert.strictEqual(decision.then[0].direction, 'left');
  assert.strictEqual(decision.else[0].direction, 'forward');
})();

(function failClosed() {
  assert.throws(() => Extended.compileExpression(range('down')), /unsupported range direction/);
  assert.throws(() => Extended.compileStatement(block('webeeblocks_exp_move', {DIRECTION: 'forward', DISTANCE: 2.1})), /out of experimental range/);
  assert.throws(() => Extended.compileStatement(block('webeeblocks_exp_speed', {SPEED: 0.9})), /out of experimental range/);
  assert.throws(() => Extended.compileStatement(block('controls_repeat_ext', {TIMES: 0}, {DO: block('webeeblocks_exp_land')})), /out of experimental range/);
  assert.throws(() => Extended.compileWorkspace({getTopBlocks() { return []; }}), /exactly one top-level sequence/);
  assert.throws(() => Extended.compileWorkspace(workspace(block('webeeblocks_exp_move', {DIRECTION: 'forward', DISTANCE: 0.5}))), /start with takeoff/);
})();

console.log('PASS extended block semantic AST');
