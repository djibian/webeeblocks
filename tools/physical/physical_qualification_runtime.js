(function(root) {
  'use strict';

  function fail(message) {
    throw new Error('physical qualification runtime: ' + message);
  }

  function requireText(value, name) {
    if (typeof value !== 'string' || value.trim() === '' || value !== value.trim())
      fail(name + ' must be a non-empty trimmed string');
    return value;
  }

  var config = root.WebeeBlocksPhysicalQualificationConfig;
  if (!config)
    return;
  if (config.executionAuthority !== false)
    fail('launcher configuration must remain non-authority');
  if (!root.WebeeBlocksPhysicalPreflight ||
      root.WebeeBlocksPhysicalPreflight.executionAuthority !== false)
    fail('physical preflight runtime is unavailable or authoritative');

  var launcherBaseUrl = requireText(config.launcherBaseUrl, 'launcherBaseUrl').replace(/\/$/, '');
  var launcherToken = requireText(config.launcherToken, 'launcherToken');
  var hostBootstrap = config.hostBootstrap;
  if (!hostBootstrap || hostBootstrap.executionAuthority !== false)
    fail('host bootstrap must remain non-authority');
  for (var key of ['baseUrl', 'token', 'preflightResponderToken'])
    requireText(hostBootstrap[key], 'hostBootstrap.' + key);

  root.WebeeBlocksPhysicalPreflight.configure(hostBootstrap);

  async function request(path, method, body) {
    var headers = {
      'Authorization': 'Bearer ' + launcherToken,
      'Cache-Control': 'no-store'
    };
    var options = {method: method, headers: headers, cache: 'no-store'};
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    var response = await fetch(launcherBaseUrl + path, options);
    var payload = await response.json();
    if (!response.ok)
      fail('launcher request failed (' + response.status + ')');
    return payload;
  }

  async function publishFailure(requestId, error) {
    try {
      await request('/v1/prepared', 'POST', {
        requestId: requestId,
        ok: false,
        error: error && error.message ? String(error.message) : 'physical preflight failed',
        executionAuthority: false
      });
    } catch (_ignored) {
      // The launcher owns the transaction. A lost failure report creates no authority.
    }
  }

  async function prepareExactCurrentProgram(requestId) {
    try {
      var result = await root.WebeeBlocksPhysicalPreflight.preflightCurrentProgram();
      if (!result || !result.preflight)
        fail('preflight result is unavailable');
      var profile = root.runtimeProfile;
      if (!profile || typeof profile.id !== 'string')
        fail('current activity profile is unavailable');
      await request('/v1/prepared', 'POST', {
        requestId: requestId,
        ok: true,
        profileId: requireText(profile.id, 'profileId'),
        astBinding: requireText(result.preflight.astBinding, 'astBinding'),
        connectionEpoch: requireText(result.preflight.connectionEpoch, 'connectionEpoch'),
        executionAuthority: false
      });
    } catch (error) {
      await publishFailure(requestId, error);
    }
  }

  var activeRequestId = null;
  async function poll() {
    while (true) {
      try {
        var payload = await request('/v1/prepare-request', 'GET');
        if (!payload || payload.executionAuthority !== false)
          fail('prepare request crossed authority boundary');
        if (payload.requestId !== null) {
          var requestId = requireText(payload.requestId, 'requestId');
          if (activeRequestId === null) {
            activeRequestId = requestId;
            await prepareExactCurrentProgram(requestId);
          } else if (activeRequestId !== requestId) {
            fail('launcher changed the one-shot preparation request');
          }
        }
      } catch (_error) {
        // A launcher/browser transport failure creates no physical authority.
      }
      await new Promise(function(resolve) { setTimeout(resolve, 200); });
    }
  }

  poll();
})(typeof window !== 'undefined' ? window : globalThis);
