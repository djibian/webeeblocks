// Only the disposable Webots Robot Window uses this durable, single-use recovery
// checkpoint. No project .wbb is written and no physical backend sees this path.
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebeeBlocksSimulationRecovery = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  var KEY = 'webeeblocks-world-recovery-v1';

  function validate(value) {
    if (!value || value.version !== 1 || typeof value.profileId !== 'string' ||
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

  function save(profileId, workspace) {
    var checkpoint = validate({version: 1, profileId: profileId, workspace: workspace});
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
