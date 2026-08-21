(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksInterpreter = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var SENSOR_DIRECTIONS = ['front', 'back', 'left', 'right', 'up'];
  var MOVE_DIRECTIONS = ['forward', 'back', 'left', 'right'];
  var VERTICAL_DIRECTIONS = ['up', 'down'];
  var COMPARE_OPS = ['LT', 'LTE', 'GT', 'GTE', 'EQ', 'NEQ'];

  function fail(message) { throw new Error('runtime v2: ' + message); }
  function finite(value, name) { var n = Number(value); if (!Number.isFinite(n)) fail(name + ' must be finite'); return n; }
  function requireMethod(backend, name) { if (!backend || typeof backend[name] !== 'function') fail('backend is missing ' + name + '()'); return backend[name].bind(backend); }

  function validateProgram(ast) {
    if (!ast || ast.version !== 1 || ast.semantics !== 'webeeblocks-ast-v1') fail('unsupported AST envelope');
    if (!Array.isArray(ast.program) || ast.program.length < 2) fail('program must contain at least takeoff and land');
    if (ast.program[0].kind !== 'takeoff' || ast.program[ast.program.length - 1].kind !== 'land') fail('program must start with takeoff and end with land');
  }

  async function evaluate(expression, backend, budget, depth) {
    if (!expression || typeof expression.kind !== 'string') fail('invalid expression');
    if (depth > 20) fail('expression nesting too deep');
    budget.remaining -= 1;
    if (budget.remaining < 0) fail('execution budget exceeded');

    switch (expression.kind) {
      case 'number': return finite(expression.value, 'number');
      case 'range': {
        var direction = String(expression.direction);
        if (SENSOR_DIRECTIONS.indexOf(direction) < 0 || expression.unit !== 'm') fail('unsupported range expression');
        return finite(await requireMethod(backend, 'readRange')(direction), 'range(' + direction + ')');
      }
      case 'compare': {
        var op = String(expression.op);
        if (COMPARE_OPS.indexOf(op) < 0) fail('unsupported comparison ' + op);
        var left = await evaluate(expression.left, backend, budget, depth + 1);
        var right = await evaluate(expression.right, backend, budget, depth + 1);
        if (op === 'LT') return left < right;
        if (op === 'LTE') return left <= right;
        if (op === 'GT') return left > right;
        if (op === 'GTE') return left >= right;
        if (op === 'EQ') return left === right;
        return left !== right;
      }
      case 'logic': {
        var logic = String(expression.op);
        if (logic !== 'AND' && logic !== 'OR') fail('unsupported logic operation ' + logic);
        var first = Boolean(await evaluate(expression.left, backend, budget, depth + 1));
        if (logic === 'AND') return first && Boolean(await evaluate(expression.right, backend, budget, depth + 1));
        return first || Boolean(await evaluate(expression.right, backend, budget, depth + 1));
      }
      default: fail('unsupported expression kind ' + expression.kind);
    }
  }

  async function executeSequence(sequence, backend, budget, depth) {
    if (!Array.isArray(sequence)) fail('statement sequence must be an array');
    if (depth > 20) fail('statement nesting too deep');

    for (var i = 0; i < sequence.length; ++i) {
      budget.remaining -= 1;
      if (budget.remaining < 0) fail('execution budget exceeded');
      var statement = sequence[i];
      if (!statement || typeof statement.kind !== 'string') fail('invalid statement');

      switch (statement.kind) {
        case 'takeoff': await requireMethod(backend, 'takeoff')(finite(statement.height_m, 'height_m')); break;
        case 'land': await requireMethod(backend, 'land')(); break;
        case 'move': {
          var direction = String(statement.direction);
          if (MOVE_DIRECTIONS.indexOf(direction) < 0) fail('unsupported move direction ' + direction);
          await requireMethod(backend, 'move')(direction, finite(statement.distance_m, 'distance_m'));
          break;
        }
        case 'vertical': {
          var verticalDirection = String(statement.direction);
          if (VERTICAL_DIRECTIONS.indexOf(verticalDirection) < 0) fail('unsupported vertical direction ' + verticalDirection);
          await requireMethod(backend, 'vertical')(verticalDirection, finite(statement.distance_m, 'distance_m'));
          break;
        }
        case 'turn': await requireMethod(backend, 'turn')(finite(statement.angle_deg, 'angle_deg')); break;
        case 'wait': await requireMethod(backend, 'wait')(finite(statement.seconds, 'seconds')); break;
        case 'set_speed': await requireMethod(backend, 'setSpeed')(finite(statement.speed_m_s, 'speed_m_s')); break;
        case 'if': {
          var condition = Boolean(await evaluate(statement.condition, backend, budget, depth + 1));
          await executeSequence(condition ? statement.then : (statement.else || []), backend, budget, depth + 1);
          break;
        }
        case 'repeat': {
          var count = Number(statement.count);
          if (!Number.isInteger(count) || count < 1 || count > 20) fail('repeat count out of bounds');
          for (var repeat = 0; repeat < count; ++repeat) await executeSequence(statement.body, backend, budget, depth + 1);
          break;
        }
        default: fail('unsupported statement kind ' + statement.kind);
      }
    }
  }

  async function run(ast, backend, options) {
    validateProgram(ast);
    var maxSteps = options && Number.isInteger(options.maxSteps) ? options.maxSteps : 1000;
    if (maxSteps < 1 || maxSteps > 100000) fail('invalid execution budget');
    var budget = {remaining: maxSteps};
    await executeSequence(ast.program, backend, budget, 0);
    return {remainingBudget: budget.remaining};
  }

  return {run: run, evaluate: evaluate, validateProgram: validateProgram};
});
