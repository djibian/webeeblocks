'use strict';

/**
 * Conservative no-effect safety proof for dynamic physical Runtime v2 programs.
 *
 * This module deliberately does not execute the student program and exposes no
 * backend, sensor, command or authority surface. It first delegates language
 * validity to the existing shared interpreter, then proves the physical safety
 * envelope for every syntactically reachable control-flow path. Conditions are
 * treated as nondeterministic: both branches are analysed, and repeat bodies are
 * analysed for every statically bounded iteration. The resulting altitude
 * interval is therefore an over-approximation; uncertainty rejects rather than
 * defers an unsafe path until after takeoff.
 */

const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Interpreter = require(path.join(
  ROOT,
  'plugins/robot_windows/blockly/webeeblocks/interpreter.js'
));

const MIN_ALTITUDE_M = 0.2;
const MAX_ALTITUDE_M = 1.5;
const MIN_MOVE_DISTANCE_M = 0.10;
const MAX_MOVE_DISTANCE_M = 2.00;
const MIN_VERTICAL_DISTANCE_M = 0.10;
const MAX_VERTICAL_DISTANCE_M = 0.80;
const MIN_TURN_DEG = 1.0;
const MAX_TURN_DEG = 179.0;
const MIN_WAIT_SECONDS = 0.1;
const MAX_WAIT_SECONDS = 5.0;
const MIN_HORIZONTAL_SPEED_M_S = 0.10;
const MAX_HORIZONTAL_SPEED_M_S = 0.35;
const LIGHT_COLORS = new Set(['off', 'red', 'green', 'blue', 'yellow', 'white']);

function fail(message) {
  throw new Error('physical dynamic preflight: ' + message);
}

function exactKeys(value, keys, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    fail(label + ' must be an object');
  const actual = Object.keys(value).sort();
  const expected = keys.slice().sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index]))
    fail(label + ' contains unsupported fields');
}

function exactOneOfKeySets(value, keySets, label) {
  for (const keys of keySets) {
    const actual = Object.keys(value).sort();
    const expected = keys.slice().sort();
    if (actual.length === expected.length && actual.every((key, index) => key === expected[index]))
      return;
  }
  fail(label + ' contains unsupported fields');
}

function finiteNumber(value, label) {
  if (typeof value !== 'number' || !Number.isFinite(value))
    fail(label + ' must be a finite number');
  return value;
}

function bounded(value, label, minimum, maximum) {
  const number = finiteNumber(value, label);
  if (number < minimum || number > maximum)
    fail(label + ' violates established physical bounds');
  return number;
}

function exactVariable(variable) {
  exactKeys(variable, ['id', 'name'], 'variable reference');
  if (typeof variable.id !== 'string' || !variable.id)
    fail('variable reference id is invalid');
  if (typeof variable.name !== 'string' || !variable.name.trim())
    fail('variable reference name is invalid');
}

function exactExpression(expression, depth) {
  if (depth > 20)
    fail('expression nesting is too deep');
  if (!expression || typeof expression !== 'object' || Array.isArray(expression))
    fail('expression must be an object');
  switch (expression.kind) {
    case 'number':
      exactKeys(expression, ['kind', 'value'], 'number expression');
      finiteNumber(expression.value, 'number expression value');
      return;
    case 'range':
      exactKeys(expression, ['kind', 'direction', 'unit'], 'range expression');
      return;
    case 'variable_get':
      exactKeys(expression, ['kind', 'variable'], 'variable expression');
      exactVariable(expression.variable);
      return;
    case 'arithmetic':
    case 'compare':
    case 'logic':
      exactKeys(expression, ['kind', 'op', 'left', 'right'], expression.kind + ' expression');
      exactExpression(expression.left, depth + 1);
      exactExpression(expression.right, depth + 1);
      return;
    default:
      fail('unsupported expression kind ' + String(expression.kind));
  }
}

function requireAltitude(interval, context) {
  if (!interval || typeof interval.min !== 'number' || typeof interval.max !== 'number')
    fail('internal altitude interval is invalid');
  if (
    !Number.isFinite(interval.min) ||
    !Number.isFinite(interval.max) ||
    interval.min < MIN_ALTITUDE_M ||
    interval.max > MAX_ALTITUDE_M
  )
    fail(context + ' can leave the established 0.2-1.5 m nominal-altitude envelope');
  return interval;
}

function exactStatementShape(statement, nested) {
  if (!statement || typeof statement !== 'object' || Array.isArray(statement))
    fail('statement must be an object');
  const kind = statement.kind;
  if (nested && (kind === 'takeoff' || kind === 'land'))
    fail('takeoff and land are only allowed at top-level boundaries');
  switch (kind) {
    case 'takeoff':
      exactKeys(statement, ['kind', 'height_m'], 'takeoff statement');
      bounded(statement.height_m, 'takeoff height_m', MIN_ALTITUDE_M, MAX_ALTITUDE_M);
      return;
    case 'land':
      exactKeys(statement, ['kind'], 'land statement');
      return;
    case 'move':
      exactKeys(statement, ['kind', 'direction', 'distance_m'], 'move statement');
      bounded(statement.distance_m, 'move distance_m', MIN_MOVE_DISTANCE_M, MAX_MOVE_DISTANCE_M);
      return;
    case 'vertical':
      exactKeys(statement, ['kind', 'direction', 'distance_m'], 'vertical statement');
      bounded(statement.distance_m, 'vertical distance_m', MIN_VERTICAL_DISTANCE_M, MAX_VERTICAL_DISTANCE_M);
      return;
    case 'turn': {
      exactKeys(statement, ['kind', 'angle_deg'], 'turn statement');
      const angle = finiteNumber(statement.angle_deg, 'turn angle_deg');
      const magnitude = Math.abs(angle);
      if (magnitude < MIN_TURN_DEG || magnitude > MAX_TURN_DEG)
        fail('turn angle_deg violates established physical bounds');
      return;
    }
    case 'wait':
      exactKeys(statement, ['kind', 'seconds'], 'wait statement');
      bounded(statement.seconds, 'wait seconds', MIN_WAIT_SECONDS, MAX_WAIT_SECONDS);
      return;
    case 'set_speed':
      exactKeys(statement, ['kind', 'speed_m_s'], 'set_speed statement');
      bounded(
        statement.speed_m_s,
        'set_speed speed_m_s',
        MIN_HORIZONTAL_SPEED_M_S,
        MAX_HORIZONTAL_SPEED_M_S
      );
      return;
    case 'set_light':
      exactKeys(statement, ['kind', 'color'], 'set_light statement');
      if (typeof statement.color !== 'string' || !LIGHT_COLORS.has(statement.color))
        fail('set_light color violates established physical palette');
      return;
    case 'set_variable':
      exactKeys(statement, ['kind', 'variable', 'value'], 'set_variable statement');
      exactVariable(statement.variable);
      exactExpression(statement.value, 0);
      return;
    case 'if':
      exactOneOfKeySets(
        statement,
        [
          ['kind', 'condition', 'then'],
          ['kind', 'condition', 'then', 'else']
        ],
        'if statement'
      );
      exactExpression(statement.condition, 0);
      if (!Array.isArray(statement.then) || (statement.else !== undefined && !Array.isArray(statement.else)))
        fail('if branches must be statement arrays');
      return;
    case 'repeat':
      exactKeys(statement, ['kind', 'count', 'body'], 'repeat statement');
      if (!Number.isInteger(statement.count) || statement.count < 1 || statement.count > 20)
        fail('repeat count violates shared interpreter bounds');
      if (!Array.isArray(statement.body))
        fail('repeat body must be a statement array');
      return;
    default:
      fail('unsupported physical statement kind ' + String(kind));
  }
}

function analyseSequence(sequence, interval, depth) {
  if (!Array.isArray(sequence))
    fail('statement sequence must be an array');
  if (depth > 20)
    fail('statement nesting is too deep');
  let current = {min: interval.min, max: interval.max};
  for (const statement of sequence) {
    exactStatementShape(statement, true);
    switch (statement.kind) {
      case 'vertical': {
        const distance = statement.distance_m;
        const delta = statement.direction === 'up' ? distance : -distance;
        current = requireAltitude(
          {min: current.min + delta, max: current.max + delta},
          'vertical path'
        );
        break;
      }
      case 'if': {
        const thenResult = analyseSequence(statement.then, current, depth + 1);
        const elseResult = analyseSequence(statement.else || [], current, depth + 1);
        current = requireAltitude(
          {
            min: Math.min(thenResult.min, elseResult.min),
            max: Math.max(thenResult.max, elseResult.max)
          },
          'conditional path'
        );
        break;
      }
      case 'repeat':
        for (let iteration = 0; iteration < statement.count; iteration += 1)
          current = analyseSequence(statement.body, current, depth + 1);
        break;
      case 'takeoff':
      case 'land':
        fail('takeoff and land cannot occur inside the in-flight dynamic body');
        break;
      default:
        // Non-vertical effects, observations, variables and host-local state are
        // nominal-altitude neutral. Their exact physical bounds were checked above.
        break;
    }
  }
  return current;
}

function validatePhysicalProgram(ast) {
  // Language/control-flow validity remains owned by the shared interpreter.
  Interpreter.validateProgram(ast);

  exactKeys(ast, ['version', 'semantics', 'program'], 'physical AST envelope');
  if (!Array.isArray(ast.program) || ast.program.length < 2)
    fail('physical program must contain flight boundaries');

  const first = ast.program[0];
  const last = ast.program[ast.program.length - 1];
  exactStatementShape(first, false);
  exactStatementShape(last, false);
  if (first.kind !== 'takeoff')
    fail('physical program must begin with exact takeoff');
  if (last.kind !== 'land')
    fail('physical program must end with exact land');

  const initialAltitude = bounded(
    first.height_m,
    'takeoff height_m',
    MIN_ALTITUDE_M,
    MAX_ALTITUDE_M
  );
  const terminal = analyseSequence(
    ast.program.slice(1, -1),
    {min: initialAltitude, max: initialAltitude},
    0
  );

  return Object.freeze({
    initialAltitudeM: initialAltitude,
    terminalAltitudeMinM: terminal.min,
    terminalAltitudeMaxM: terminal.max,
    executionAuthority: false
  });
}

module.exports = Object.freeze({
  validatePhysicalProgram,
  MIN_ALTITUDE_M,
  MAX_ALTITUDE_M
});
