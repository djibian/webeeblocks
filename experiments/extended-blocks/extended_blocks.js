/* Experimental only: richer Crazyflie block semantics without touching the frozen product. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksExtended = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  const LIMITS = Object.freeze({
    height_m: {min: 0.2, max: 1.5},
    distance_m: {min: 0.1, max: 2.0},
    vertical_m: {min: 0.1, max: 0.8},
    wait_s: {min: 0.1, max: 5.0},
    speed_m_s: {min: 0.1, max: 0.6},
    range_m: {min: 0.05, max: 4.0},
    repeat: {min: 1, max: 20}
  });

  const SENSOR_DIRECTIONS = Object.freeze(['front', 'back', 'left', 'right', 'up']);

  function finite(value, name) {
    const n = Number(value);
    if (!Number.isFinite(n))
      throw new Error(name + ' must be finite');
    return n;
  }

  function bounded(value, name, limits) {
    const n = finite(value, name);
    if (n < limits.min || n > limits.max)
      throw new Error(name + ' out of experimental range: ' + n);
    return n;
  }

  function field(block, name) {
    if (!block || typeof block.getFieldValue !== 'function')
      throw new Error('invalid Blockly block');
    return block.getFieldValue(name);
  }

  function statementChildren(block, inputName) {
    if (!block || typeof block.getInputTargetBlock !== 'function')
      throw new Error('block does not expose statement input ' + inputName);
    const first = block.getInputTargetBlock(inputName);
    return compileSequence(first);
  }

  function valueChild(block, inputName) {
    if (!block || typeof block.getInputTargetBlock !== 'function')
      throw new Error('block does not expose value input ' + inputName);
    const child = block.getInputTargetBlock(inputName);
    if (!child)
      throw new Error('missing value input ' + inputName);
    return compileExpression(child);
  }

  function compileExpression(block) {
    switch (block.type) {
      case 'webeeblocks_exp_range': {
        const direction = String(field(block, 'DIRECTION'));
        if (SENSOR_DIRECTIONS.indexOf(direction) < 0)
          throw new Error('unsupported range direction: ' + direction);
        return {kind: 'range', direction: direction, unit: 'm'};
      }
      case 'math_number':
        return {kind: 'number', value: finite(field(block, 'NUM'), 'number')};
      case 'logic_compare': {
        const op = String(field(block, 'OP'));
        if (['LT', 'LTE', 'GT', 'GTE', 'EQ', 'NEQ'].indexOf(op) < 0)
          throw new Error('unsupported comparison: ' + op);
        return {kind: 'compare', op: op, left: valueChild(block, 'A'), right: valueChild(block, 'B')};
      }
      case 'logic_operation': {
        const op = String(field(block, 'OP'));
        if (op !== 'AND' && op !== 'OR')
          throw new Error('unsupported logic operation: ' + op);
        return {kind: 'logic', op: op, left: valueChild(block, 'A'), right: valueChild(block, 'B')};
      }
      default:
        throw new Error('unsupported experimental expression block: ' + block.type);
    }
  }

  function compileStatement(block) {
    switch (block.type) {
      case 'webeeblocks_exp_takeoff':
        return {kind: 'takeoff', height_m: bounded(field(block, 'HEIGHT'), 'height_m', LIMITS.height_m)};
      case 'webeeblocks_exp_land':
        return {kind: 'land'};
      case 'webeeblocks_exp_move': {
        const direction = String(field(block, 'DIRECTION'));
        if (['forward', 'back', 'left', 'right'].indexOf(direction) < 0)
          throw new Error('unsupported move direction: ' + direction);
        return {kind: 'move', direction: direction, distance_m: bounded(field(block, 'DISTANCE'), 'distance_m', LIMITS.distance_m)};
      }
      case 'webeeblocks_exp_vertical': {
        const direction = String(field(block, 'DIRECTION'));
        if (direction !== 'up' && direction !== 'down')
          throw new Error('unsupported vertical direction: ' + direction);
        return {kind: 'vertical', direction: direction, distance_m: bounded(field(block, 'DISTANCE'), 'vertical_m', LIMITS.vertical_m)};
      }
      case 'webeeblocks_exp_turn': {
        const direction = String(field(block, 'DIRECTION'));
        const degrees = bounded(field(block, 'ANGLE'), 'angle_deg', {min: 1, max: 179});
        if (direction !== 'left' && direction !== 'right')
          throw new Error('unsupported turn direction: ' + direction);
        return {kind: 'turn', angle_deg: direction === 'left' ? degrees : -degrees};
      }
      case 'webeeblocks_exp_wait':
        return {kind: 'wait', seconds: bounded(field(block, 'SECONDS'), 'wait_s', LIMITS.wait_s)};
      case 'webeeblocks_exp_speed':
        return {kind: 'set_speed', speed_m_s: bounded(field(block, 'SPEED'), 'speed_m_s', LIMITS.speed_m_s)};
      case 'controls_repeat_ext':
        return {kind: 'repeat', count: bounded(field(block, 'TIMES'), 'repeat', LIMITS.repeat), body: statementChildren(block, 'DO')};
      case 'controls_if': {
        const result = {kind: 'if', condition: valueChild(block, 'IF0'), then: statementChildren(block, 'DO0')};
        const otherwise = block.getInputTargetBlock('ELSE');
        if (otherwise)
          result.else = compileSequence(otherwise);
        return result;
      }
      default:
        throw new Error('unsupported experimental statement block: ' + block.type);
    }
  }

  function compileSequence(first) {
    const result = [];
    let block = first;
    let guard = 0;
    while (block) {
      if (++guard > 200)
        throw new Error('experimental program too large');
      result.push(compileStatement(block));
      block = typeof block.getNextBlock === 'function' ? block.getNextBlock() : null;
    }
    return result;
  }

  function compileWorkspace(workspace) {
    const tops = workspace.getTopBlocks(true);
    if (tops.length !== 1)
      throw new Error('experimental Crazyflie program must have exactly one top-level sequence');
    const program = compileSequence(tops[0]);
    if (program.length < 2 || program[0].kind !== 'takeoff' || program[program.length - 1].kind !== 'land')
      throw new Error('experimental program must start with takeoff and end with land');
    return {version: 1, semantics: 'webeeblocks-experimental-ast', program: program};
  }

  return {
    LIMITS: LIMITS,
    SENSOR_DIRECTIONS: SENSOR_DIRECTIONS,
    compileExpression: compileExpression,
    compileStatement: compileStatement,
    compileSequence: compileSequence,
    compileWorkspace: compileWorkspace
  };
});
