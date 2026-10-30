// Only the disposable Webots Robot Window uses this durable, single-use recovery
// checkpoint. No project .wbb is written and no physical backend sees this path.
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebeeBlocksSimulationRecovery = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  var KEY = 'webeeblocks-world-recovery-v1';

  function validate(value) {
    if (!value || value.version !== 2 || typeof value.token !== 'string' || !/^[0-9a-f]{64}$/.test(value.token) || !Number.isSafeInteger(value.nextRequestId) ||
        value.nextRequestId < 1 || value.nextRequestId > 2147483647 ||
        typeof value.profileId !== 'string' ||
        !/^[A-Za-z0-9_-]{1,100}$/.test(value.profileId) ||
        typeof value.workspace !== 'string' || value.workspace.length > 5000000)
      throw new Error('Invalid WebeeBlocks recovery checkpoint');
    var parsed = JSON.parse(value.workspace);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
      throw new Error('Invalid WebeeBlocks Blockly checkpoint');
    return value;
  }

  function peek() {
    var raw = localStorage.getItem(KEY);
    return raw === null ? null : validate(JSON.parse(raw));
  }

  function save(profileId, workspace, nextRequestId) {
    // Correlates the browser checkpoint with the independent native witness.
    if (!globalThis.crypto || typeof globalThis.crypto.getRandomValues !== 'function')
      throw new Error('Recovery correlation randomness unavailable');
    var random = new Uint8Array(32);
    globalThis.crypto.getRandomValues(random);
    var token = Array.from(random, function(b) { return b.toString(16).padStart(2, '0'); }).join('');
    var checkpoint = validate({version: 2, token: token, profileId: profileId, workspace: workspace, nextRequestId: nextRequestId});
    var encoded = JSON.stringify(checkpoint);
    localStorage.setItem(KEY, encoded);
    if (localStorage.getItem(KEY) !== encoded)
      throw new Error('Recovery checkpoint was not durably stored');
    return checkpoint;
  }

  function clear(checkpoint) {
    if (JSON.stringify(peek()) !== JSON.stringify(checkpoint))
      throw new Error('Recovery checkpoint changed while validating');
    localStorage.removeItem(KEY);
    if (localStorage.getItem(KEY) !== null)
      throw new Error('Recovery checkpoint could not be cleared');
  }

  return Object.freeze({peek: peek, save: save, clear: clear});
});
