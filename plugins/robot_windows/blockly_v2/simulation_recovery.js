// Only the disposable Webots Robot Window uses this durable, single-use recovery
// checkpoint. No project .wbb is written and no physical backend sees this path.
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebeeBlocksSimulationRecovery = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  var KEY = 'webeeblocks-world-recovery-v1';

  function validate(value) {
    if (!value || value.version !== 3 || typeof value.token !== 'string' || !/^[0-9a-f]{64}$/.test(value.token) || !Number.isSafeInteger(value.nextRequestId) ||
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

  // Unambiguous SHA-256 input: ASCII domain + UTF-8 byte lengths (big-endian
  // uint32) + the two length-prefixed UTF-8 strings, in profile/workspace order.
  // No digest from mutable localStorage is ever trusted as the original.
  async function fingerprint(profileId, workspace) {
    if (typeof TextEncoder !== 'function' || !globalThis.crypto ||
        !globalThis.crypto.subtle || typeof globalThis.crypto.subtle.digest !== 'function')
      throw new Error('Recovery SHA-256 unavailable — reconstruction refused');
    var encoder = new TextEncoder();
    var domain = encoder.encode('WEBEEBLOCKS_RECOVERY_V3\u0000');
    var profile = encoder.encode(profileId);
    var blocks = encoder.encode(workspace);
    if (!profile.length || profile.length > 100 || blocks.length > 20000000)
      throw new Error('Recovery fingerprint input out of bounds');
    var bytes = new Uint8Array(domain.length + 8 + profile.length + blocks.length);
    var view = new DataView(bytes.buffer);
    var offset = domain.length;
    view.setUint32(offset, profile.length, false); offset += 4;
    bytes.set(profile, offset); offset += profile.length;
    view.setUint32(offset, blocks.length, false); offset += 4;
    bytes.set(blocks, offset);
    var sha = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
    if (sha.length !== 32) throw new Error('Recovery SHA-256 invalid digest length');
    return Array.from(sha, function(b) { return b.toString(16).padStart(2, '0'); }).join('');
  }

  function save(profileId, workspace, nextRequestId, digest) {
    // MUST be invoked under the shared Web Lock, including the absence check.
    // Do not parse an existing value: malformed/legacy records are still owned.
    if (localStorage.getItem(KEY) !== null)
      throw new Error('An earlier Blockly recovery checkpoint already exists');
    if (typeof digest !== 'string' || !/^[0-9a-f]{64}$/.test(digest))
      throw new Error('Missing independent recovery fingerprint');
    // Correlates the browser checkpoint with the independent native witness.
    if (!globalThis.crypto || typeof globalThis.crypto.getRandomValues !== 'function')
      throw new Error('Recovery correlation randomness unavailable');
    var random = new Uint8Array(32);
    globalThis.crypto.getRandomValues(random);
    var token = Array.from(random, function(b) { return b.toString(16).padStart(2, '0'); }).join('');
    var checkpoint = validate({version: 3, token: token, profileId: profileId, workspace: workspace, nextRequestId: nextRequestId});
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

  return Object.freeze({peek: peek, save: save, clear: clear, fingerprint: fingerprint});
});
