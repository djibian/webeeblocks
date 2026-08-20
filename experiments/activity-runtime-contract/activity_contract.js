/* Experimental A2 only. Bridges one declarative activity profile to Blockly and AST runtime preflight.
 * No product/runtime code is modified. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebeeBlocksActivityRuntimeContract = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function fail(msg) { throw new Error('activity contract: ' + msg); }
  function own(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  function collectAst(ast) {
    const blocks = new Set();
    const ranges = new Set();
    function expr(e) {
      if (!e) return;
      if (e.kind === 'range') ranges.add(e.direction);
      if (e.left) expr(e.left);
      if (e.right) expr(e.right);
    }
    function seq(items) {
      for (const s of items || []) {
        blocks.add(s.kind);
        if (s.kind === 'if') { expr(s.condition); seq(s.then); seq(s.else); }
        if (s.kind === 'repeat') seq(s.body);
      }
    }
    seq(ast && ast.program);
    return {blocks, ranges};
  }

  function workspaceTypes(workspace) {
    return workspace.getAllBlocks(false).map(b => b.type);
  }

  function preflightWorkspace(profile, workspace) {
    const allowed = new Set(profile.toolbox);
    const types = workspaceTypes(workspace);
    for (const type of types) {
      if (!allowed.has(type)) fail('block forbidden by profile: ' + type);
    }
    return types;
  }

  function checkBounds(profile, ast) {
    const bounds = profile.astBounds || {};
    function bounded(name, value) {
      if (!own(bounds, name)) return;
      const b = bounds[name];
      if (value < b.min || value > b.max) fail(name + ' outside profile bounds: ' + value);
    }
    function seq(items) {
      for (const s of items || []) {
        if (s.kind === 'takeoff') bounded('takeoff.height_m', s.height_m);
        if (s.kind === 'move') bounded('move.distance_m', s.distance_m);
        if (s.kind === 'repeat') { bounded('repeat.count', s.count); seq(s.body); }
        if (s.kind === 'if') { seq(s.then); seq(s.else); }
      }
    }
    seq(ast.program);
  }

  function preflightAst(profile, ast) {
    const facts = collectAst(ast);
    const allowedKinds = new Set(profile.runtime.allowedStatementKinds || []);
    for (const kind of facts.blocks) {
      if (!allowedKinds.has(kind)) fail('AST statement forbidden by profile: ' + kind);
    }
    const allowedRanges = new Set(profile.runtime.rangeDirections || []);
    for (const direction of facts.ranges) {
      if (!allowedRanges.has(direction)) fail('range capability unavailable in profile: ' + direction);
    }
    checkBounds(profile, ast);
    return facts;
  }

  function toolboxXml(profile) {
    return '<xml>' + profile.toolbox.map(type => '<block type="' + type + '"></block>').join('') + '</xml>';
  }

  function execute(profile, workspace, compiler, interpreter, backend) {
    preflightWorkspace(profile, workspace);
    const ast = compiler.compileWorkspace(workspace);
    preflightAst(profile, ast);
    interpreter.run(ast, backend);
    return ast;
  }

  return {preflightWorkspace, preflightAst, toolboxXml, execute};
});
