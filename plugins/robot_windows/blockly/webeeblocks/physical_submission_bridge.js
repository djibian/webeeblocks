(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory(
      require('./physical_capability_contract.js'),
      require('./semantic_ast.js')
    );
  else
    root.WebeeBlocksPhysicalSubmissionBridge = factory(
      root.WebeeBlocksPhysicalCapabilityContract,
      root.WebeeBlocksSemanticAst
    );
})(typeof self !== 'undefined' ? self : this, function(PhysicalCapabilities, SemanticAst) {
  'use strict';

  function fail(message) {
    throw new Error('physical submission bridge: ' + message);
  }

  function create(profile, adapter, compileWorkspace) {
    if (!profile || !Array.isArray(profile.hardware))
      fail('activity profile is required');
    if (!PhysicalCapabilities || typeof PhysicalCapabilities.preflightConnected !== 'function' ||
        typeof PhysicalCapabilities.assertPreflightConnected !== 'function')
      fail('physical capability contract is unavailable');
    compileWorkspace = compileWorkspace || (SemanticAst && SemanticAst.compileWorkspace);
    if (typeof compileWorkspace !== 'function')
      fail('semantic AST compiler is unavailable');

    var bound = null;

    async function preflightWorkspace(workspace) {
      var ast = compileWorkspace(workspace);
      var result = await PhysicalCapabilities.preflightConnected(profile, ast, adapter);
      bound = {astBinding: result.astBinding, result: result};
      return result;
    }

    async function assertCurrentWorkspace(workspace) {
      if (!bound)
        fail('physical preflight is required before re-assertion');
      var ast = compileWorkspace(workspace);
      if (PhysicalCapabilities.bindAst(ast) !== bound.astBinding)
        fail('workspace changed since physical preflight');
      await PhysicalCapabilities.assertPreflightConnected(bound.result, ast, adapter);
      return {
        compatible: true,
        executionAuthority: false,
        ast: ast,
        preflight: bound.result
      };
    }

    function clear() {
      bound = null;
    }

    return Object.freeze({
      executionAuthority: false,
      preflightWorkspace: preflightWorkspace,
      assertCurrentWorkspace: assertCurrentWorkspace,
      clear: clear
    });
  }

  return {create: create};
});
