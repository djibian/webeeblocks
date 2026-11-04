(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksActivityContract = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  var BACKEND_ACTION_KINDS = ['takeoff', 'move', 'vertical', 'turn', 'wait', 'set_speed', 'set_light', 'land'];
  function fail(message) { throw new Error('activity contract: ' + message); }
  function studentFail(message, detail) {
    var error = new Error('activity contract: ' + message);
    error.code = 'PROGRAM_INVALID';
    error.studentDetail = detail;
    throw error;
  }
  function workspaceTypes(workspace) {
    if (!workspace || typeof workspace.getAllBlocks !== 'function') fail('invalid Blockly workspace');
    return workspace.getAllBlocks(false).map(function(block) {
      return block.type;
    });
  }
  function preflightFieldOptions(profile, workspace) {
    var definitions = profile.fieldOptions || {};
    workspace.getAllBlocks(false).forEach(function(block) {
      var fields = definitions[block.type] || {};
      Object.keys(fields).forEach(function(fieldName) {
        var field = block.getField(fieldName);
        if (!field || typeof field.getValue !== 'function')
          fail('field-option target unavailable: ' + block.type + '.' + fieldName);
        var value = field.getValue();
        if (fields[fieldName].indexOf(value) < 0)
          studentFail('field option forbidden by profile: ' + block.type + '.' + fieldName + '=' + value,
            'Une option de ce programme n’est pas disponible dans cette activité. Modifiez-la avant de lancer.');
      });
    });
    return true;
  }
  function preflightWorkspace(profile, workspace) {
    var allowed = new Set(profile.toolbox);
    var types = workspaceTypes(workspace);
    workspace.getAllBlocks(false).forEach(function(block) {
      if (allowed.has(block.type)) return;
      // A numeric shadow is part of a movement command, not a separate
      // operator taught to pupils in the earliest activities.
      var parent = typeof block.getParent === 'function' ? block.getParent() : null;
      var motion = parent && (
        parent.type === 'webeeblocks_v2_takeoff' || parent.type === 'webeeblocks_v2_move' ||
        parent.type === 'webeeblocks_v2_vertical');
      var input = parent && (parent.type === 'webeeblocks_v2_takeoff' ? 'HEIGHT' : 'DISTANCE');
      if (block.type === 'math_number' && motion && typeof block.isShadow === 'function' &&
          block.isShadow() && parent.getInputTargetBlock(input) === block) return;
      studentFail('block forbidden by profile: ' + block.type,
        'Un bloc de ce programme n’est pas disponible dans cette activité. Supprimez-le avant de lancer.');
    });
    preflightFieldOptions(profile, workspace);
    return types;
  }
  function applyFieldBounds(profile, workspace) {
    var definitions = profile.parameterBounds || {};
    workspace.getAllBlocks(false).forEach(function(block) {
      // Numeric values directly plugged into movements obey movement bounds,
      // independently of Number-operator limits used for repeat counts.
      var parent = typeof block.getParent === 'function' ? block.getParent() : null;
      var socket = parent && parent.type === 'webeeblocks_v2_takeoff' ? 'HEIGHT' : 'DISTANCE';
      var motion = parent && ['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_vertical'].indexOf(parent.type) >= 0;
      if (block.type === 'math_number' && motion &&
          parent.getInputTargetBlock(socket) === block) {
        var limits = profile.runtime.astBounds || {};
        var key = parent.type === 'webeeblocks_v2_takeoff' ? 'takeoff.height_m' :
          parent.type === 'webeeblocks_v2_vertical' ? 'vertical.distance_m' : 'move.distance_m';
        var generic = limits[key] || {};
        var min = Number.isFinite(generic.min) ? generic.min : 0.01;
        var max = Number.isFinite(generic.max) ? generic.max : 2;
        if (parent.type === 'webeeblocks_v2_move') {
          var dir = parent.getFieldValue('DIRECTION');
          var directional = limits[dir==='left'||dir==='right'?'move.lateral.distance_m':'move.forward.distance_m'] || {};
          if (Number.isFinite(directional.min)) min = Math.max(min,directional.min);
          if (Number.isFinite(directional.max)) max = Math.min(max,directional.max);
        }
        if (min > max) fail('invalid movement literal bounds in profile');
        block.getField('NUM').setConstraints(min,max,0.01);
        return;
      }
      var fields = definitions[block.type] || {};
      Object.keys(fields).forEach(function(fieldName) {
        var field = block.getField(fieldName);
        if (!field || typeof field.setConstraints !== 'function')
          fail('field bound target unavailable: ' + block.type + '.' + fieldName);
        var bounds = fields[fieldName];
        field.setConstraints(bounds.min, bounds.max, bounds.step);
      });
    });
  }
  function collectAst(ast) {
    var elapsedTime = false, statements = new Set(), ranges = new Set(), moves = new Set(), verticals = new Set();
    function expression(node) {
      if (!node) return;
      if (node.kind === 'elapsed_time') elapsedTime = true;
      if (node.kind === 'range') ranges.add(node.direction);
      if (node.left) expression(node.left);
      if (node.right) expression(node.right);
    }
    function sequence(items) {
      (items || []).forEach(function(statement) {
        statements.add(statement.kind);
        if (statement.kind === 'move') moves.add(statement.direction);
        if (statement.kind === 'vertical') verticals.add(statement.direction);
        if (statement.kind === 'set_variable') expression(statement.value);
        if (statement.kind === 'takeoff' && typeof statement.height_m === 'object') expression(statement.height_m);
        if ((statement.kind === 'move' || statement.kind === 'vertical') && typeof statement.distance_m === 'object') expression(statement.distance_m);
        if (statement.kind === 'if') {
          expression(statement.condition);
          sequence(statement.then);
          sequence(statement.else);
        } else if (statement.kind === 'repeat' || statement.kind === 'while' || statement.kind === 'call') {
          if (statement.kind === 'while') expression(statement.condition);
          sequence(statement.body);
        };
      });
    }
    sequence(ast && ast.program);
    return {
      elapsedTime: elapsedTime, statements: statements, ranges: ranges,
      moveDirections: moves, verticalDirections: verticals
    };
  }
  function checkBound(bounds, name, value) {
    if (!Object.prototype.hasOwnProperty.call(bounds, name)) return;
    if (typeof value !== 'number' || !Number.isFinite(value)) fail(name + ' must be finite');
    var constraint = bounds[name];
    if (value < constraint.min || value > constraint.max) fail(name + ' outside profile bounds: ' + value);
  }
  function checkMotion(profile,bounds,name,value,direction) {
    if (typeof value === 'object' && value && typeof value.kind === 'string')
      return; // Interpreter checks the evaluated number before dispatch.
    checkBound(bounds,name,value);
    if(name==='move.distance_m')
      checkBound(bounds,direction==='left'||direction==='right'?'move.lateral.distance_m':'move.forward.distance_m',value);
  }
  function checkAstBounds(profile, ast) {
    var bounds = profile.runtime.astBounds || {};
    function sequence(items) {
      (items || []).forEach(function(statement) {
        if (statement.kind === 'takeoff') checkMotion(profile,bounds,'takeoff.height_m',statement.height_m);
        else if (statement.kind === 'move') checkMotion(profile,bounds,'move.distance_m',statement.distance_m,statement.direction);
        else if (statement.kind === 'vertical') checkMotion(profile,bounds,'vertical.distance_m',statement.distance_m);
        else if (statement.kind === 'turn') checkBound(bounds, 'turn.angle_deg_abs', Math.abs(statement.angle_deg));
        else if (statement.kind === 'wait') checkBound(bounds, 'wait.seconds', statement.seconds);
        else if (statement.kind === 'set_speed') checkBound(bounds, 'set_speed.speed_m_s', statement.speed_m_s);
        else if (statement.kind === 'repeat') {
          checkBound(bounds, 'repeat.count', statement.count);
          sequence(statement.body);
        } else if (statement.kind === 'while') {
          checkBound(bounds, 'while.max_iterations', statement.max_iterations);
          sequence(statement.body);
        } else if (statement.kind === 'call') {
          sequence(statement.body);
        } else if (statement.kind === 'if') {
          sequence(statement.then);
          sequence(statement.else);
        }
      });
    }
    sequence(ast.program);
  }
  function requireDirections(facts, key, allowedValues, messagePrefix) {
    var allowed = new Set(allowedValues || []);
    facts[key].forEach(function(direction) {
      if (!allowed.has(direction)) fail(messagePrefix + direction);
    });
  }
  function preflightAst(profile, ast) {
    var facts = collectAst(ast);
    if (facts.elapsedTime && profile.runtime.elapsedSimulationTime !== true)
      fail('elapsed simulation time unavailable in profile');
    var kinds = new Set(profile.runtime.allowedStatementKinds || []);
    facts.statements.forEach(function(kind) { if (!kinds.has(kind)) fail('AST statement forbidden by profile: ' + kind); });
    requireDirections(facts, 'ranges', profile.runtime.rangeDirections, 'range capability unavailable in profile: ');
    requireDirections(facts, 'moveDirections', profile.runtime.moveDirections, 'move direction unavailable in profile: ');
    requireDirections(facts, 'verticalDirections', profile.runtime.verticalDirections,
      'vertical direction unavailable in profile: ');
    checkAstBounds(profile, ast);
    return facts;
  }
  function preflightBackend(profile, facts, backend) {
    var capabilities = backend && backend.capabilities;
    if (!capabilities) fail('backend capabilities unavailable');
    if (facts.elapsedTime && capabilities.elapsedSimulationTime !== true) fail('elapsed simulation time unavailable on backend');
    if (facts.statements.has('call') && capabilities.procedures !== true) fail('procedures unavailable on backend');
    var actions = new Set(capabilities.actions || []);
    facts.statements.forEach(function(kind) {
      if (BACKEND_ACTION_KINDS.indexOf(kind) >= 0 && !actions.has(kind))
        studentFail('backend action capability unavailable: ' + kind,
          'Ce bloc n’est pas pris en charge dans cette simulation. Modifiez le programme avant de relancer.');
    });
    requireDirections(facts, 'ranges', capabilities.rangeDirections, 'backend range capability unavailable: ');
    requireDirections(facts, 'moveDirections', capabilities.moveDirections, 'backend move direction unavailable: ');
    requireDirections(facts, 'verticalDirections', capabilities.verticalDirections, 'backend vertical direction unavailable: ');
    return true;
  }
  async function execute(profile, workspace, compiler, interpreter, backend, options) {
    preflightWorkspace(profile, workspace);
    applyFieldBounds(profile, workspace);
    var ast = compiler.compileWorkspace(workspace);
    var facts = preflightAst(profile, ast);
    preflightBackend(profile, facts, backend);
    var interpreterOptions = Object.assign({}, options || {});
    interpreterOptions.motionBounds = profile.runtime.astBounds || {};
    var onAst = interpreterOptions.onAst;
    delete interpreterOptions.onAst;
    if (typeof onAst === 'function') onAst(ast);
    if (backend.capabilities && backend.capabilities.simulationScenes === true) {
      if (typeof backend.prepareActivity !== 'function') fail('simulation scene preparation unavailable');
      await backend.prepareActivity(profile);
    }
    await interpreter.run(ast, backend, interpreterOptions);
    return ast;
  }
  return {
    preflightWorkspace: preflightWorkspace, preflightFieldOptions: preflightFieldOptions,
    applyFieldBounds: applyFieldBounds, collectAst: collectAst, preflightAst: preflightAst,
    preflightBackend: preflightBackend, execute: execute
  };
});
