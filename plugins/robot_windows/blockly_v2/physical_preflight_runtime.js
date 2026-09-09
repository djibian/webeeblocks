(function(root) {
  'use strict';

  function fail(message) {
    throw new Error('physical preflight runtime: ' + message);
  }

  function requireText(value, name) {
    if (typeof value !== 'string' || value.trim() === '')
      fail(name + ' must be a non-empty string');
    return value.trim();
  }

  var adapter = null;
  var bridge = null;
  var boundProfile = null;
  var responder = null;
  var responderGeneration = 0;

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

  function createResponder(options) {
    options = options || {};
    var baseUrl = requireText(options.baseUrl, 'baseUrl').replace(/\/$/, '');
    var token = requireText(
      options.preflightResponderToken,
      'preflightResponderToken'
    );
    var fetchImpl = options.fetchImpl ||
      (typeof fetch === 'function' ? fetch.bind(globalThis) : null);
    if (typeof fetchImpl !== 'function')
      fail('fetch implementation is required');

    async function request(path, method, body) {
      var headers = {
        'Authorization': 'Bearer ' + token,
        'Cache-Control': 'no-store'
      };
      var requestOptions = {
        method: method,
        headers: headers,
        cache: 'no-store'
      };
      if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        requestOptions.body = JSON.stringify(body);
      }
      var response = await fetchImpl(baseUrl + path, requestOptions);
      var payload;
      try {
        payload = await response.json();
      } catch (_error) {
        fail('preflight responder returned malformed JSON');
      }
      if (!response.ok)
        fail(
          'preflight responder request failed (' +
          response.status +
          '): ' +
          String(payload && payload.error || 'unknown error')
        );
      return payload;
    }

    return Object.freeze({
      async readChallenge() {
        var payload = await request('/v1/preflight-challenge', 'GET');
        if (!payload || payload.executionAuthority !== false)
          fail('preflight challenge must remain non-authority');
        if (payload.challengeId === null)
          return null;
        return requireText(payload.challengeId, 'challengeId');
      },
      async submitAssertion(assertion) {
        return request('/v1/preflight-assertion', 'POST', assertion);
      }
    });
  }

  function delay(ms) {
    return new Promise(function(resolve) {
      setTimeout(resolve, ms);
    });
  }

  async function answerCurrentProgramChallenges(
    generation,
    activeAdapter,
    activeResponder
  ) {
    while (
      adapter === activeAdapter &&
      responder === activeResponder &&
      responderGeneration === generation
    ) {
      var challengeId;
      try {
        challengeId = await activeResponder.readChallenge();
      } catch (_error) {
        if (
          adapter !== activeAdapter ||
          responder !== activeResponder ||
          responderGeneration !== generation
        )
          return;
        await delay(100);
        continue;
      }
      if (
        adapter !== activeAdapter ||
        responder !== activeResponder ||
        responderGeneration !== generation
      )
        return;
      if (challengeId === null)
        continue;

      var assertion = {
        challengeId: challengeId,
        ok: false,
        executionAuthority: false
      };
      try {
        var result = await assertCurrentProgram();
        if (
          adapter !== activeAdapter ||
          responder !== activeResponder ||
          responderGeneration !== generation
        )
          return;
        assertion.ok = true;
        assertion.profileId = root.runtimeProfile.id;
        assertion.astBinding = result.preflight.astBinding;
        assertion.connectionEpoch = result.preflight.connectionEpoch;
      } catch (_error) {
        assertion.ok = false;
      }

      try {
        await activeResponder.submitAssertion(assertion);
      } catch (_error) {
        // Host timeout/reconnect/replay rejection creates no authority.
        // Never retry a settled assertion response.
      }
    }
  }

  function configure(options) {
    responderGeneration += 1;
    if (bridge && typeof bridge.clear === 'function')
      bridge.clear();
    bridge = null;
    boundProfile = null;
    responder = null;
    adapter = root.WebeeBlocksPhysicalCapabilityHttpAdapter.create(options || {});
    responder = createResponder(options || {});
    var generation = responderGeneration;
    var activeAdapter = adapter;
    var activeResponder = responder;
    answerCurrentProgramChallenges(
      generation,
      activeAdapter,
      activeResponder
    );
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
    if (
      bridge !== activeBridge ||
      profileBinding(root.runtimeProfile) !== expectedProfileBinding
    ) {
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
      if (
        bridge === activeBridge &&
        profileBinding(root.runtimeProfile) !== expectedProfileBinding
      ) {
        activeBridge.clear();
        bridge = null;
        boundProfile = null;
      }
      throw error;
    }
    if (
      bridge !== activeBridge ||
      boundProfile !== expectedProfileBinding ||
      profileBinding(root.runtimeProfile) !== expectedProfileBinding
    ) {
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
    responderGeneration += 1;
    if (bridge && typeof bridge.clear === 'function')
      bridge.clear();
    bridge = null;
    boundProfile = null;
    responder = null;
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
