/* Experimental only: deterministic execution of WebeeBlocks semantic AST.
 * This file is isolated from the frozen product/runtime.
 */
(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksReactiveInterpreter = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  const SENSOR_DIRECTIONS = Object.freeze(['front', 'back', 'left', 'right', 'up']);
  const MOVE_DIRECTIONS = Object.freeze(['forward', 'back', 'left', 'right']);
  const VERTICAL_DIRECTIONS = Object.freeze(['up', 'down']);
  const COMPARE_OPS = Object.freeze(['LT', 'LTE', 'GT', 'GTE', 'EQ', 'NEQ']);
  const LOGIC_OPS = Object.freeze(['AND', 'OR']);

  function fail(message) {
    throw new Error('reactive AST: ' + message);
  }

  function finite(value, name) {
    const n = Number(value);
    if (!Number.isFinite(n))
      fail(name + ' must be finite');
    return n;
  }

  function requireMethod(backend, name) {
    if (!backend || typeof backend[name] !== 'function')
      fail('backend is missing ' + name + '()');
    return backend[name].bind(backend);
  }

  function validateProgram(ast) {
    if (!ast || ast.version !== 1 || ast.semantics !== 'webeeblocks-experimental-ast')
      fail('unsupported AST envelope');
    if (!Array.isArray(ast.program) || ast.program.length < 2)
      fail('program must contain at least takeoff and land');
    if (ast.program[0].kind !== 'takeoff' || ast.program[ast.program.length - 1].kind !== 'land')
      fail('program must start with takeoff and end with land');
  }

  function evaluate(expression, backend, budget, depth) {
    if (!expression || typeof expression.kind !== 'string')
      fail('invalid expression');
    if (depth > 20)
      fail('expression nesting too deep');
    if (--budget.remaining < 0)
      fail('execution budget exceeded');

    switch (expression.kind) {
      case 'number':
        return finite(expression.value, 'number');
      case 'range': {
        const direction = String(expression.direction);
        if (SENSOR_DIRECTIONS.indexOf(direction) < 0 || expression.unit !== 'm')
          fail('unsupported range expression');
        const readRange = requireMethod(backend, 'readRange');
        return finite(readRange(direction), 'range(' + direction + ')');
      }
      case 'compare': {
        const op = String(expression.op);
        if (COMPARE_OPS.indexOf(op) < 0)
          fail('unsupported comparison ' + op);
        const left = evaluate(expression.left, backend, budget, depth + 1);
        const right = evaluate(expression.right, backend, budget, depth + 1);
        if (op === 'LT') return left < right;
        if (op === 'LTE') return left <= right;
        if (op === 'GT') return left > right;
        if (op === 'GTE') return left >= right;
        if (op === 'EQ') return left === right;
        return left !== right;
      }
      case 'logic': {
        const op = String(expression.op);
        if (LOGIC_OPS.indexOf(op) < 0)
          fail('unsupported logic operation ' + op);
        const left = Boolean(evaluate(expression.left, backend, budget, depth + 1));
        if (op === 'AND')
          return left && Boolean(evaluate(expression.right, backend, budget, depth + 1));
        return left || Boolean(evaluate(expression.right, backend, budget, depth + 1));
      }
      default:
        fail('unsupported expression kind ' + expression.kind);
    }
  }

  function executeSequence(sequence, backend, budget, depth) {
    if (!Array.isArray(sequence))
      fail('statement sequence must be an array');
    if (depth > 20)
      fail('statement nesting too deep');

    for (const statement of sequence) {
      if (--budget.remaining < 0)
        fail('execution budget exceeded');
      if (!statement || typeof statement.kind !== 'string')
        fail('invalid statement');

      switch (statement.kind) {
        case 'takeoff':
          requireMethod(backend, 'takeoff')(finite(statement.height_m, 'height_m'));
          break;
        case 'land':
          requireMethod(backend, 'land')();
          break;
        case 'move': {
          const direction = String(statement.direction);
          if (MOVE_DIRECTIONS.indexOf(direction) < 0)
            fail('unsupported move direction ' + direction);
          requireMethod(backend, 'move')(direction, finite(statement.distance_m, 'distance_m'));
          break;
        }
        case 'vertical': {
          const direction = String(statement.direction);
          if (VERTICAL_DIRECTIONS.indexOf(direction) < 0)
            fail('unsupported vertical direction ' + direction);
          requireMethod(backend, 'vertical')(direction, finite(statement.distance_m, 'distance_m'));
          break;
        }
        case 'turn':
          requireMethod(backend, 'turn')(finite(statement.angle_deg, 'angle_deg'));
          break;
        case 'wait':
          requireMethod(backend, 'wait')(finite(statement.seconds, 'seconds'));
          break;
        case 'set_speed':
          requireMethod(backend, 'setSpeed')(finite(statement.speed_m_s, 'speed_m_s'));
          break;
        case 'if': {
          const condition = Boolean(evaluate(statement.condition, backend, budget, depth + 1));
          executeSequence(condition ? statement.then : (statement.else || []), backend, budget, depth + 1);
          break;
        }
        case 'repeat': {
          const count = Number(statement.count);
          if (!Number.isInteger(count) || count < 1 || count > 20)
            fail('repeat count out of bounds');
          for (let i = 0; i < count; ++i)
            executeSequence(statement.body, backend, budget, depth + 1);
          break;
        }
        default:
          fail('unsupported statement kind ' + statement.kind);
      }
    }
  }

  function run(ast, backend, options) {
    validateProgram(ast);
    const budget = {remaining: options && Number.isInteger(options.maxSteps) ? options.maxSteps : 1000};
    if (budget.remaining < 1 || budget.remaining > 100000)
      fail('invalid execution budget');
    executeSequence(ast.program, backend, budget, 0);
    return {remainingBudget: budget.remaining};
  }

  function ScriptedBackend(rangeScripts) {
    this.rangeScripts = {};
    this.rangeOffsets = {};
    this.trace = [];
    const scripts = rangeScripts || {};
    for (const direction of Object.keys(scripts)) {
      if (SENSOR_DIRECTIONS.indexOf(direction) < 0 || !Array.isArray(scripts[direction]))
        fail('invalid range script for ' + direction);
      this.rangeScripts[direction] = scripts[direction].slice();
      this.rangeOffsets[direction] = 0;
    }
  }

  ScriptedBackend.prototype.readRange = function(direction) {
    const script = this.rangeScripts[direction];
    const index = this.rangeOffsets[direction] || 0;
    if (!script || index >= script.length)
      fail('no scripted range sample for ' + direction + ' at read ' + index);
    const value = finite(script[index], 'scripted range');
    this.rangeOffsets[direction] = index + 1;
    this.trace.push({op: 'range', direction: direction, value_m: value, read: index + 1});
    return value;
  };
  ScriptedBackend.prototype.takeoff = function(height_m) { this.trace.push({op: 'takeoff', height_m: height_m}); };
  ScriptedBackend.prototype.land = function() { this.trace.push({op: 'land'}); };
  ScriptedBackend.prototype.move = function(direction, distance_m) { this.trace.push({op: 'move', direction: direction, distance_m: distance_m}); };
  ScriptedBackend.prototype.vertical = function(direction, distance_m) { this.trace.push({op: 'vertical', direction: direction, distance_m: distance_m}); };
  ScriptedBackend.prototype.turn = function(angle_deg) { this.trace.push({op: 'turn', angle_deg: angle_deg}); };
  ScriptedBackend.prototype.wait = function(seconds) { this.trace.push({op: 'wait', seconds: seconds}); };
  ScriptedBackend.prototype.setSpeed = function(speed_m_s) { this.trace.push({op: 'set_speed', speed_m_s: speed_m_s}); };

  return {
    run: run,
    evaluate: evaluate,
    ScriptedBackend: ScriptedBackend
  };
});
