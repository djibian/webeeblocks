(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksActivityContract = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  var BACKEND_ACTION_KINDS = ['takeoff', 'move', 'vertical', 'turn', 'wait', 'set_speed', 'land'];
  function fail(message) { throw new Error('activity contract: ' + message); }
  function workspaceTypes(workspace) { if (!workspace || typeof workspace.getAllBlocks !== 'function') fail('invalid Blockly workspace'); return workspace.getAllBlocks(false).map(function(block) { return block.type; }); }
  function preflightWorkspace(profile, workspace) { var allowed = new Set(profile.toolbox); var types = workspaceTypes(workspace); types.forEach(function(type) { if (!allowed.has(type)) fail('block forbidden by profile: ' + type); }); return types; }
  function applyFieldBounds(profile, workspace) { var definitions = profile.parameterBounds || {}; workspace.getAllBlocks(false).forEach(function(block) { var fields = definitions[block.type] || {}; Object.keys(fields).forEach(function(fieldName) { var field = block.getField(fieldName); if (!field || typeof field.setConstraints !== 'function') fail('field bound target unavailable: ' + block.type + '.' + fieldName); var bounds = fields[fieldName]; field.setConstraints(bounds.min, bounds.max, bounds.step); }); }); }
  function collectAst(ast) {
    var statements = new Set(), ranges = new Set(), moves = new Set(), verticals = new Set();
    function expression(node) { if (!node) return; if (node.kind === 'range') ranges.add(node.direction); if (node.left) expression(node.left); if (node.right) expression(node.right); }
    function sequence(items) { (items || []).forEach(function(statement) { statements.add(statement.kind); if (statement.kind === 'move') moves.add(statement.direction); if (statement.kind === 'vertical') verticals.add(statement.direction); if (statement.kind === 'if') { expression(statement.condition); sequence(statement.then); sequence(statement.else); } else if (statement.kind === 'repeat') sequence(statement.body); }); }
    sequence(ast && ast.program);
    return {statements: statements, ranges: ranges, moveDirections: moves, verticalDirections: verticals};
  }
  function checkBound(bounds, name, value) { if (!Object.prototype.hasOwnProperty.call(bounds, name)) return; var constraint = bounds[name]; if (value < constraint.min || value > constraint.max) fail(name + ' outside profile bounds: ' + value); }
  function checkAstBounds(profile, ast) { var bounds = profile.runtime.astBounds || {}; function sequence(items) { (items || []).forEach(function(statement) { if (statement.kind === 'takeoff') checkBound(bounds, 'takeoff.height_m', statement.height_m); else if (statement.kind === 'move') checkBound(bounds, 'move.distance_m', statement.distance_m); else if (statement.kind === 'vertical') checkBound(bounds, 'vertical.distance_m', statement.distance_m); else if (statement.kind === 'turn') checkBound(bounds, 'turn.angle_deg_abs', Math.abs(statement.angle_deg)); else if (statement.kind === 'wait') checkBound(bounds, 'wait.seconds', statement.seconds); else if (statement.kind === 'set_speed') checkBound(bounds, 'set_speed.speed_m_s', statement.speed_m_s); else if (statement.kind === 'repeat') { checkBound(bounds, 'repeat.count', statement.count); sequence(statement.body); } else if (statement.kind === 'if') { sequence(statement.then); sequence(statement.else); } }); } sequence(ast.program); }
  function requireDirections(facts, key, allowedValues, messagePrefix) { var allowed = new Set(allowedValues || []); facts[key].forEach(function(direction) { if (!allowed.has(direction)) fail(messagePrefix + direction); }); }
  function preflightAst(profile, ast) {
    var facts = collectAst(ast);
    var kinds = new Set(profile.runtime.allowedStatementKinds || []);
    facts.statements.forEach(function(kind) { if (!kinds.has(kind)) fail('AST statement forbidden by profile: ' + kind); });
    requireDirections(facts, 'ranges', profile.runtime.rangeDirections, 'range capability unavailable in profile: ');
    requireDirections(facts, 'moveDirections', profile.runtime.moveDirections, 'move direction unavailable in profile: ');
    requireDirections(facts, 'verticalDirections', profile.runtime.verticalDirections, 'vertical direction unavailable in profile: ');
    checkAstBounds(profile, ast);
    return facts;
  }
  function preflightBackend(profile, facts, backend) {
    var capabilities = backend && backend.capabilities;
    if (!capabilities) fail('backend capabilities unavailable');
    var actions = new Set(capabilities.actions || []);
    facts.statements.forEach(function(kind) { if (BACKEND_ACTION_KINDS.indexOf(kind) >= 0 && !actions.has(kind)) fail('backend action capability unavailable: ' + kind); });
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
    var onAst = interpreterOptions.onAst;
    delete interpreterOptions.onAst;
    if (typeof onAst === 'function') onAst(ast);
    await interpreter.run(ast, backend, interpreterOptions);
    return ast;
  }
  return {preflightWorkspace: preflightWorkspace, applyFieldBounds: applyFieldBounds, collectAst: collectAst, preflightAst: preflightAst, preflightBackend: preflightBackend, execute: execute};
});
