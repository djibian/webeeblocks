'use strict';

const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const PhysicalCapabilities = require('../../plugins/robot_windows/blockly/webeeblocks/physical_capability_contract.js');

const MIN_NOMINAL_ALTITUDE_M = 0.2;
const MAX_NOMINAL_ALTITUDE_M = 1.5;
const MIN_MOVE_DISTANCE_M = 0.1;
const MAX_MOVE_DISTANCE_M = 2.0;
const MIN_VERTICAL_DISTANCE_M = 0.1;
const MAX_VERTICAL_DISTANCE_M = 0.8;
const MIN_TURN_DEG = 1.0;
const MAX_TURN_DEG = 179.0;
const MIN_WAIT_SECONDS = 0.1;
const MAX_WAIT_SECONDS = 5.0;
const MIN_HORIZONTAL_SPEED_M_S = 0.10;
const MAX_HORIZONTAL_SPEED_M_S = 0.35;
const MOVE_DIRECTIONS = new Set(['forward', 'back', 'left', 'right']);
const VERTICAL_DIRECTIONS = new Set(['up', 'down']);
const LIGHT_COLORS = new Set(['off', 'red', 'green', 'blue', 'yellow', 'white']);

function fail(message) {
  throw new Error('physical dynamic safety: ' + message);
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function exactKeys(value, expected, path) {
  if (!isObject(value))
    fail(path + ' must be an object');
  const actual = Object.keys(value).sort();
  const wanted = expected.slice().sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index]))
    fail(path + ' contains unsupported fields');
}

function finiteNumber(value, path) {
  if (typeof value !== 'number' || !Number.isFinite(value))
    fail(path + ' must be a finite number');
  return value;
}

function boundedNumber(value, path, minimum, maximum) {
  const number = finiteNumber(value, path);
  if (number < minimum || number > maximum)
    fail(path + ' violates established physical bounds');
  return number;
}

function requireAltitude(interval, path) {
  if (!interval || !Number.isFinite(interval.min) || !Number.isFinite(interval.max) || interval.min > interval.max)
    fail(path + ' produced an invalid nominal-altitude interval');
  if (interval.min < MIN_NOMINAL_ALTITUDE_M || interval.max > MAX_NOMINAL_ALTITUDE_M)
    fail(path + ' can leave the established 0.2-1.5 m nominal-altitude envelope');
  return interval;
}

function shifted(interval, delta, path) {
  return requireAltitude({min: interval.min + delta, max: interval.max + delta}, path);
}

function union(left, right, path) {
  return requireAltitude({min: Math.min(left.min, right.min), max: Math.max(left.max, right.max)}, path);
}

function validateAction(statement, interval, path) {
  switch (statement.kind) {
    case 'move': {
      exactKeys(statement, ['kind', 'direction', 'distance_m'], path);
      if (!MOVE_DIRECTIONS.has(statement.direction))
        fail(path + '.direction is unsupported');
      boundedNumber(statement.distance_m, path + '.distance_m', MIN_MOVE_DISTANCE_M, MAX_MOVE_DISTANCE_M);
      return interval;
    }
    case 'vertical': {
      exactKeys(statement, ['kind', 'direction', 'distance_m'], path);
      if (!VERTICAL_DIRECTIONS.has(statement.direction))
        fail(path + '.direction is unsupported');
      const distance = boundedNumber(statement.distance_m, path + '.distance_m', MIN_VERTICAL_DISTANCE_M, MAX_VERTICAL_DISTANCE_M);
      return shifted(interval, statement.direction === 'up' ? distance : -distance, path);
    }
    case 'turn': {
      exactKeys(statement, ['kind', 'angle_deg'], path);
      const angle = finiteNumber(statement.angle_deg, path + '.angle_deg');
      if (Math.abs(angle) < MIN_TURN_DEG || Math.abs(angle) > MAX_TURN_DEG)
        fail(path + '.angle_deg violates established physical bounds');
      return interval;
    }
    case 'wait':
      exactKeys(statement, ['kind', 'seconds'], path);
      boundedNumber(statement.seconds, path + '.seconds', MIN_WAIT_SECONDS, MAX_WAIT_SECONDS);
      return interval;
    case 'set_speed':
      exactKeys(statement, ['kind', 'speed_m_s'], path);
      boundedNumber(statement.speed_m_s, path + '.speed_m_s', MIN_HORIZONTAL_SPEED_M_S, MAX_HORIZONTAL_SPEED_M_S);
      return interval;
    case 'set_light':
      exactKeys(statement, ['kind', 'color'], path);
      if (!LIGHT_COLORS.has(statement.color))
        fail(path + '.color violates the established Runtime v2 palette');
      return interval;
    default:
      return null;
  }
}

function proveSequence(sequence, interval, path, depth) {
  if (!Array.isArray(sequence))
    fail(path + ' must be an array');
  if (depth > 20)
    fail(path + ' nesting is too deep');

  let current = requireAltitude({min: interval.min, max: interval.max}, path);
  for (let index = 0; index < sequence.length; index += 1) {
    const statement = sequence[index];
    const statementPath = path + '[' + index + ']';
    if (!isObject(statement) || typeof statement.kind !== 'string')
      fail(statementPath + ' is malformed');

    const actionResult = validateAction(statement, current, statementPath);
    if (actionResult) {
      current = actionResult;
      continue;
    }

    if (statement.kind === 'set_variable') {
      exactKeys(statement, ['kind', 'variable', 'value'], statementPath);
      continue;
    }

    if (statement.kind === 'if') {
      const keys = Object.keys(statement).sort();
      const noElse = ['condition', 'kind', 'then'];
      const withElse = ['condition', 'else', 'kind', 'then'];
      const accepted = [noElse, withElse].some(expected =>
        keys.length === expected.length && keys.every((key, position) => key === expected[position]));
      if (!accepted)
        fail(statementPath + ' contains unsupported fields');
      const thenInterval = proveSequence(statement.then, current, statementPath + '.then', depth + 1);
      const elseInterval = statement.else === undefined
        ? current
        : proveSequence(statement.else, current, statementPath + '.else', depth + 1);
      current = union(thenInterval, elseInterval, statementPath);
      continue;
    }

    if (statement.kind === 'repeat') {
      exactKeys(statement, ['kind', 'count', 'body'], statementPath);
      // Interpreter.validateProgram() is authoritative for the exact integer 1..20 bound.
      for (let iteration = 0; iteration < statement.count; iteration += 1)
        current = proveSequence(statement.body, current, statementPath + '.body', depth + 1);
      continue;
    }

    if (statement.kind === 'takeoff' || statement.kind === 'land')
      fail(statementPath + ' contains a nested flight boundary');
    fail(statementPath + ' uses an unsupported physical statement kind');
  }
  return current;
}

function parseExactBinding(astBinding) {
  if (typeof astBinding !== 'string' || astBinding.length === 0 || astBinding !== astBinding.trim())
    fail('exact canonical AST binding must be a non-empty trimmed string');
  let ast;
  try {
    ast = JSON.parse(astBinding);
  } catch (error) {
    fail('exact canonical AST binding is malformed JSON');
  }
  exactKeys(ast, ['version', 'semantics', 'program'], 'AST envelope');
  let rebound;
  try {
    rebound = PhysicalCapabilities.bindAst(ast);
  } catch (error) {
    fail('AST binding is not a supported canonical backend-neutral AST');
  }
  if (rebound !== astBinding)
    fail('AST binding is not the exact canonical JSON serialization');
  try {
    Interpreter.validateProgram(ast);
  } catch (error) {
    fail('shared interpreter rejected AST: ' + error.message);
  }
  return ast;
}

function proveBoundPhysicalProgram(astBinding) {
  const ast = parseExactBinding(astBinding);
  const program = ast.program;
  const first = program[0];
  const last = program[program.length - 1];
  exactKeys(first, ['kind', 'height_m'], 'program[0]');
  if (first.kind !== 'takeoff')
    fail('physical program must begin with exact takeoff');
  const initialAltitude = boundedNumber(
    first.height_m,
    'program[0].height_m',
    MIN_NOMINAL_ALTITUDE_M,
    MAX_NOMINAL_ALTITUDE_M
  );
  exactKeys(last, ['kind'], 'program[' + (program.length - 1) + ']');
  if (last.kind !== 'land')
    fail('physical program must end with exact land');

  const terminal = proveSequence(
    program.slice(1, -1),
    {min: initialAltitude, max: initialAltitude},
    'program.inflight',
    0
  );
  return Object.freeze({
    compatible: true,
    executionAuthority: false,
    astBinding: astBinding,
    initialNominalAltitudeM: initialAltitude,
    terminalNominalAltitudeMinM: terminal.min,
    terminalNominalAltitudeMaxM: terminal.max
  });
}

module.exports = Object.freeze({
  proveBoundPhysicalProgram,
  MIN_NOMINAL_ALTITUDE_M,
  MAX_NOMINAL_ALTITUDE_M
});
