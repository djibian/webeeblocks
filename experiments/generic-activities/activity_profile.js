/*
 * Experimental WebeeBlocks activity-profile resolver.
 *
 * This module is intentionally independent of Webots, Blockly DOM and the
 * current release-candidate UI. It proves that an activity can declare its
 * world, brief, toolbox subset, parameter bounds, hardware and evaluation
 * contract without hard-coding those choices in blockly.html.
 */
(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksActivityProfiles = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function requireString(value, path) {
    if (typeof value !== 'string' || value.trim() === '')
      throw new Error(path + ' must be a non-empty string');
    return value;
  }

  function requireBoolean(value, path) {
    if (typeof value !== 'boolean')
      throw new Error(path + ' must be a boolean');
    return value;
  }

  function validateBounds(bounds, path) {
    if (!isObject(bounds))
      throw new Error(path + ' must be an object');
    ['min', 'max', 'step'].forEach(function(key) {
      if (!Number.isFinite(bounds[key]))
        throw new Error(path + '.' + key + ' must be finite');
    });
    if (bounds.min > bounds.max)
      throw new Error(path + '.min must be <= max');
    if (bounds.step <= 0)
      throw new Error(path + '.step must be > 0');
  }

  function validateProfile(profile, blockCatalog) {
    if (!isObject(profile))
      throw new Error('profile must be an object');

    requireString(profile.id, 'id');
    requireString(profile.world, 'world');

    if (!isObject(profile.brief))
      throw new Error('brief must be an object');
    requireBoolean(profile.brief.visible, 'brief.visible');
    if (profile.brief.visible) {
      requireString(profile.brief.title, 'brief.title');
      requireString(profile.brief.goal, 'brief.goal');
    }

    if (!Array.isArray(profile.toolbox) || profile.toolbox.length === 0)
      throw new Error('toolbox must be a non-empty array');

    var seen = Object.create(null);
    profile.toolbox.forEach(function(type, index) {
      requireString(type, 'toolbox[' + index + ']');
      if (!Object.prototype.hasOwnProperty.call(blockCatalog, type))
        throw new Error('unknown block type: ' + type);
      if (seen[type])
        throw new Error('duplicate block type: ' + type);
      seen[type] = true;
    });

    if (profile.parameterBounds !== undefined) {
      if (!isObject(profile.parameterBounds))
        throw new Error('parameterBounds must be an object');
      Object.keys(profile.parameterBounds).forEach(function(blockType) {
        if (!seen[blockType])
          throw new Error('parameter bounds declared for hidden block: ' + blockType);
        var fields = profile.parameterBounds[blockType];
        if (!isObject(fields))
          throw new Error('parameterBounds.' + blockType + ' must be an object');
        Object.keys(fields).forEach(function(field) {
          validateBounds(fields[field], 'parameterBounds.' + blockType + '.' + field);
        });
      });
    }

    if (!Array.isArray(profile.hardware))
      throw new Error('hardware must be an array');

    if (!isObject(profile.timer) || typeof profile.timer.enabled !== 'boolean')
      throw new Error('timer.enabled must be a boolean');

    if (!isObject(profile.evaluation))
      throw new Error('evaluation must be an object');
    requireString(profile.evaluation.type, 'evaluation.type');

    return true;
  }

  function resolveProfile(profile, blockCatalog) {
    validateProfile(profile, blockCatalog);
    var resolved = clone(profile);
    resolved.toolbox = resolved.toolbox.map(function(type) {
      var definition = clone(blockCatalog[type]);
      definition.type = type;
      if (resolved.parameterBounds && resolved.parameterBounds[type])
        definition.parameterBounds = clone(resolved.parameterBounds[type]);
      return definition;
    });
    if (!resolved.brief.visible)
      resolved.brief = {visible: false};
    return resolved;
  }

  function resolveById(document, profileId, blockCatalog) {
    if (!isObject(document) || !Array.isArray(document.activities))
      throw new Error('activity document must contain an activities array');
    var matches = document.activities.filter(function(profile) {
      return profile.id === profileId;
    });
    if (matches.length !== 1)
      throw new Error('activity id must resolve exactly once: ' + profileId);
    return resolveProfile(matches[0], blockCatalog);
  }

  return {
    validateProfile: validateProfile,
    resolveProfile: resolveProfile,
    resolveById: resolveById
  };
});
