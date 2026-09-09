(function(root) {
  'use strict';

  function fail(message) {
    throw new Error('physical preflight runtime: ' + message);
  }

  var adapter = null;
  var bridge = null;

  function requireProductState() {
    if (!root.WebeeBlocksPhysicalCapabilityHttpAdapter ||
        typeof root.WebeeBlocksPhysicalCapabilityHttpAdapter.create !== 'function')
      fail('live capability adapter is unavailable');
    if (!root.WebeeBlocksPhysicalSubmissionBridge ||
        typeof root.WebeeBlocksPhysicalSubmissionBridge.create !== 'function')
      fail('physical submission bridge is unavailable');
    if (!root.WebeeBlocksSemanticAst || typeof root.WebeeBlocksSemanticAst.compileWorkspace !== 'function')
      fail('semantic AST compiler is unavailable');
    if (!root.runtimeProfile || !Array.isArray(root.runtimeProfile.hardware))
      fail('current activity profile is unavailable');
    if (!root.workspace)
      fail('current Blockly workspace is unavailable');
  }

  function configure(options) {
    if (bridge && typeof bridge.clear === 'function')
      bridge.clear();
    bridge = null;
    adapter = root.WebeeBlocksPhysicalCapabilityHttpAdapter.create(options || {});
    return true;
  }

  async function preflightCurrentProgram() {
    requireProductState();
    if (!adapter)
      fail('live capability session is not configured');
    bridge = root.WebeeBlocksPhysicalSubmissionBridge.create(
      root.runtimeProfile,
      adapter,
      root.WebeeBlocksSemanticAst.compileWorkspace
    );
    return bridge.preflightWorkspace(root.workspace);
  }

  async function assertCurrentProgram() {
    requireProductState();
    if (!bridge)
      fail('physical preflight is required before re-assertion');
    return bridge.assertCurrentWorkspace(root.workspace);
  }

  function clear() {
    if (bridge && typeof bridge.clear === 'function')
      bridge.clear();
    bridge = null;
    adapter = null;
  }

  root.WebeeBlocksPhysicalPreflight = Object.freeze({
    executionAuthority: false,
    configure: configure,
    preflightCurrentProgram: preflightCurrentProgram,
    assertCurrentProgram: assertCurrentProgram,
    clear: clear
  });
})(typeof window !== 'undefined' ? window : globalThis);
