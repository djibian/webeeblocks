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

    async function read(path) {
      var response = await fetchImpl(baseUrl + path, {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer ' + token,
          'Cache-Control': 'no-store'
        },
        cache: 'no-store'
      });
      var payload;
      try {
        payload = await response.json();
      } catch (_error) {
        fail('bridge returned malformed JSON');
      }
      if (!response.ok)
        fail('bridge read failed (' + response.status + '): ' + String(payload && payload.error || 'unknown error'));
      return payload;
    }

    var adapter = {
      async readCapabilities() {
        return read('/v1/capabilities');
      },
      async readConnectionEpoch() {
        var payload = await read('/v1/connection-epoch');
        return requireText(payload && payload.connectionEpoch, 'connectionEpoch');
      }
    };
    return Object.freeze(adapter);
  }

  return {create: create};
});
