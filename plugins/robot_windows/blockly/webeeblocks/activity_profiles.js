(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksActivityProfiles = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function fail(message) { throw new Error('activity profile: ' + message); }
  function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function requireString(value, path) { if (typeof value !== 'string' || value.trim() === '') fail(path + ' must be a non-empty string'); }
  function requireStringArray(value, path) { if (!Array.isArray(value)) fail(path + ' must be an array'); value.forEach(function(item, index) { requireString(item, path + '[' + index + ']'); }); }
  function validateBounds(bounds, path) { if (!isObject(bounds)) fail(path + ' must be an object'); ['min', 'max', 'step'].forEach(function(key) { if (!Number.isFinite(bounds[key])) fail(path + '.' + key + ' must be finite'); }); if (bounds.min > bounds.max) fail(path + '.min must be <= max'); if (bounds.step <= 0) fail(path + '.step must be > 0'); }

  function validateProfile(profile, blockCatalog) {
    if (!isObject(profile)) fail('profile must be an object');
    requireString(profile.id, 'id');
    requireString(profile.world, 'world');
    if (!isObject(profile.brief) || typeof profile.brief.visible !== 'boolean') fail('brief.visible must be a boolean');
    if (profile.brief.visible) { requireString(profile.brief.title, 'brief.title'); requireString(profile.brief.goal, 'brief.goal'); }
    if (!Array.isArray(profile.toolbox) || profile.toolbox.length === 0) fail('toolbox must be a non-empty array');

    var seen = Object.create(null);
    profile.toolbox.forEach(function(type) { requireString(type, 'toolbox entry'); if (!Object.prototype.hasOwnProperty.call(blockCatalog, type)) fail('unknown block type: ' + type); if (seen[type]) fail('duplicate block type: ' + type); seen[type] = true; });

    var parameterBounds = profile.parameterBounds || {};
    if (!isObject(parameterBounds)) fail('parameterBounds must be an object');
    Object.keys(parameterBounds).forEach(function(blockType) { if (!seen[blockType]) fail('parameter bounds declared for hidden block: ' + blockType); var fields = parameterBounds[blockType]; if (!isObject(fields)) fail('parameterBounds.' + blockType + ' must be an object'); Object.keys(fields).forEach(function(fieldName) { validateBounds(fields[fieldName], 'parameterBounds.' + blockType + '.' + fieldName); }); });

    requireStringArray(profile.hardware, 'hardware');
    if (!isObject(profile.timer) || typeof profile.timer.enabled !== 'boolean') fail('timer.enabled must be a boolean');
    if (!isObject(profile.evaluation)) fail('evaluation must be an object');
    requireString(profile.evaluation.type, 'evaluation.type');
    if (!isObject(profile.runtime)) fail('runtime must be an object');
    requireStringArray(profile.runtime.allowedStatementKinds, 'runtime.allowedStatementKinds');
    requireStringArray(profile.runtime.rangeDirections, 'runtime.rangeDirections');
    requireStringArray(profile.runtime.moveDirections, 'runtime.moveDirections');
    requireStringArray(profile.runtime.verticalDirections, 'runtime.verticalDirections');
    return true;
  }

  function resolveProfile(profile, blockCatalog) {
    validateProfile(profile, blockCatalog);
    // `toolbox` has one product contract everywhere: an ordered array of Blockly
    // block type strings. Consumers that need block metadata must resolve those
    // types against the shared block catalog instead of changing this shape.
    return clone(profile);
  }

  function resolveById(document, profileId, blockCatalog) {
    if (!isObject(document) || !Array.isArray(document.activities)) fail('activity document must contain an activities array');
    var matches = document.activities.filter(function(profile) { return profile.id === profileId; });
    if (matches.length !== 1) fail('activity id must resolve exactly once: ' + profileId);
    return resolveProfile(matches[0], blockCatalog);
  }

  return {validateProfile: validateProfile, resolveProfile: resolveProfile, resolveById: resolveById};
});
