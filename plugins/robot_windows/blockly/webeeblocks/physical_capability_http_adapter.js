(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksPhysicalCapabilityHttpAdapter = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function fail(message) {
    throw new Error('physical capability HTTP adapter: ' + message);
  }

  function requireText(value, name) {
    if (typeof value !== 'string' || value.trim() === '')
      fail(name + ' must be a non-empty string');
    return value.trim();
  }

  function create(options) {
    options = options || {};
    var baseUrl = requireText(options.baseUrl, 'baseUrl').replace(/\/$/, '');
    var token = requireText(options.token, 'token');
    var fetchImpl = options.fetchImpl || (typeof fetch === 'function' ? fetch.bind(globalThis) : null);
    if (typeof fetchImpl !== 'function')
      fail('fetch implementation is required');

    async function request(path, method, body) {
      var headers = {
        'Authorization': 'Bearer ' + token,
        'Cache-Control': 'no-store'
      };
      var options = {
        method: method,
        headers: headers,
        cache: 'no-store'
      };
      if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
      }
      var response = await fetchImpl(baseUrl + path, options);
      var payload;
      try {
        payload = await response.json();
      } catch (_error) {
        fail('bridge returned malformed JSON');
      }
      if (!response.ok)
        fail('bridge request failed (' + response.status + '): ' + String(payload && payload.error || 'unknown error'));
      return payload;
    }

    async function read(path) {
      return request(path, 'GET');
    }

    var adapter = {
      async readCapabilities() {
        return read('/v1/capabilities');
      },
      async readConnectionEpoch() {
        var payload = await read('/v1/connection-epoch');
        return requireText(payload && payload.connectionEpoch, 'connectionEpoch');
      },
      async readCurrentProgramChallenge() {
        var payload = await read('/v1/preflight-challenge');
        if (!payload || payload.executionAuthority !== false)
          fail('preflight challenge must remain non-authority');
        if (payload.challengeId === null)
          return null;
        return requireText(payload.challengeId, 'challengeId');
      },
      async submitCurrentProgramAssertion(assertion) {
        if (!assertion || typeof assertion !== 'object')
          fail('current-program assertion is required');
        requireText(assertion.challengeId, 'challengeId');
        if (assertion.executionAuthority !== false)
          fail('current-program assertion must remain non-authority');
        if (assertion.ok !== true && assertion.ok !== false)
          fail('current-program assertion status must be boolean');
        if (assertion.ok === true) {
          requireText(assertion.profileId, 'profileId');
          requireText(assertion.astBinding, 'astBinding');
          requireText(assertion.connectionEpoch, 'connectionEpoch');
        }
        return request('/v1/preflight-assertion', 'POST', assertion);
      }
    };
    return Object.freeze(adapter);
  }

  return {create: create};
});
