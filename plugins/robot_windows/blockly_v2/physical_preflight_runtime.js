(function(root) {
  'use strict';

  function fail(message) {
    throw new Error('physical preflight runtime: ' + message);
  }

  var adapter = null;
  var bridge = null;
  var boundProfile = null;

  function profileBinding(profile) {
    if (!profile || typeof profile.id !== 'string' || profile.id.trim() === '' ||
        !Array.isArray(profile.hardware))
      fail('current activity profile is unavailable');
    if (profile.physicalHardwareRequired !== undefined &&
        !Array.isArray(profile.physicalHardwareRequired))
      fail('current activity physical hardware requirements are malformed');
    return JSON.stringify({
      id: profile.id,
      hardware: profile.hardware.slice(),
      physicalHardwareRequired: profile.physicalHardwareRequired === undefined
        ? null
        : profile.physicalHardwareRequired.slice()
    });
  }

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
    boundProfile = null;
    adapter = root.WebeeBlocksPhysicalCapabilityHttpAdapter.create(options || {});
    return true;
  }

  async function preflightCurrentProgram() {
    requireProductState();
    if (!adapter)
      fail('live capability session is not configured');
    var profile = root.runtimeProfile;
    var expectedProfileBinding = profileBinding(profile);
    var activeBridge = root.WebeeBlocksPhysicalSubmissionBridge.create(
      profile,
      adapter,
      root.WebeeBlocksSemanticAst.compileWorkspace
    );
    bridge = activeBridge;
    boundProfile = null;
    var result = await activeBridge.preflightWorkspace(root.workspace);
    if (bridge !== activeBridge || profileBinding(root.runtimeProfile) !== expectedProfileBinding) {
      activeBridge.clear();
      if (bridge === activeBridge)
        bridge = null;
      fail('activity profile changed during physical preflight');
    }
    boundProfile = expectedProfileBinding;
    return result;
  }

  async function assertCurrentProgram() {
    requireProductState();
    if (!bridge || boundProfile === null)
      fail('physical preflight is required before re-assertion');
    var activeBridge = bridge;
    var expectedProfileBinding = boundProfile;
    if (profileBinding(root.runtimeProfile) !== expectedProfileBinding) {
      activeBridge.clear();
      bridge = null;
      boundProfile = null;
      fail('activity profile changed since physical preflight');
    }
    var result;
    try {
      result = await activeBridge.assertCurrentWorkspace(root.workspace);
    } catch (error) {
      if (bridge === activeBridge &&
          profileBinding(root.runtimeProfile) !== expectedProfileBinding) {
        activeBridge.clear();
        bridge = null;
        boundProfile = null;
      }
      throw error;
    }
    if (bridge !== activeBridge || boundProfile !== expectedProfileBinding ||
        profileBinding(root.runtimeProfile) !== expectedProfileBinding) {
      activeBridge.clear();
      if (bridge === activeBridge) {
        bridge = null;
        boundProfile = null;
      }
      fail('activity profile changed during physical re-assertion');
    }
    return result;
  }

  function clear() {
    if (bridge && typeof bridge.clear === 'function')
      bridge.clear();
    bridge = null;
    boundProfile = null;
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
