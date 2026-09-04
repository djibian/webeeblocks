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
    profile.toolbox.forEach(function(type) {
      requireString(type, 'toolbox entry');
      if (!Object.prototype.hasOwnProperty.call(blockCatalog, type)) fail('unknown block type: ' + type);
      if (seen[type]) fail('duplicate block type: ' + type);
      seen[type] = true;
    });

    var parameterBounds = profile.parameterBounds || {};
    if (!isObject(parameterBounds)) fail('parameterBounds must be an object');
    Object.keys(parameterBounds).forEach(function(blockType) {
      if (!seen[blockType]) fail('parameter bounds declared for hidden block: ' + blockType);
      var fields = parameterBounds[blockType];
      if (!isObject(fields)) fail('parameterBounds.' + blockType + ' must be an object');
      Object.keys(fields).forEach(function(fieldName) { validateBounds(fields[fieldName], 'parameterBounds.' + blockType + '.' + fieldName); });
    });

    var fieldOptions = profile.fieldOptions || {};
    if (!isObject(fieldOptions)) fail('fieldOptions must be an object');
    Object.keys(fieldOptions).forEach(function(blockType) {
      if (!seen[blockType]) fail('field options declared for hidden block: ' + blockType);
      var fields = fieldOptions[blockType];
      if (!isObject(fields)) fail('fieldOptions.' + blockType + ' must be an object');
      Object.keys(fields).forEach(function(fieldName) {
        var values = fields[fieldName];
        requireStringArray(values, 'fieldOptions.' + blockType + '.' + fieldName);
        if (values.length === 0) fail('fieldOptions.' + blockType + '.' + fieldName + ' must not be empty');
        var valueSeen = Object.create(null);
        values.forEach(function(value) {
          if (valueSeen[value]) fail('duplicate field option: ' + blockType + '.' + fieldName + '=' + value);
          valueSeen[value] = true;
        });
      });
    });

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
    return clone(profile);
  }

  function resolveById(document, profileId, blockCatalog) {
    if (!isObject(document) || !Array.isArray(document.activities)) fail('activity document must contain an activities array');
    var matches = document.activities.filter(function(profile) { return profile.id === profileId; });
    if (matches.length !== 1) fail('activity id must resolve exactly once: ' + profileId);
    return resolveProfile(matches[0], blockCatalog);
  }

  function createFieldOptionController(document, blockCatalog, Blockly) {
    if (!isObject(document) || !Array.isArray(document.activities)) fail('activity document must contain an activities array');
    if (!Blockly || !Blockly.Blocks || typeof Blockly.Workspace !== 'function') fail('Blockly field-option dependencies unavailable');

    var targets = Object.create(null);
    document.activities.forEach(function(profile) {
      validateProfile(profile, blockCatalog);
      Object.keys(profile.fieldOptions || {}).forEach(function(blockType) {
        targets[blockType] = targets[blockType] || Object.create(null);
        Object.keys(profile.fieldOptions[blockType]).forEach(function(fieldName) { targets[blockType][fieldName] = true; });
      });
    });

    var generic = Object.create(null);
    var active = {};
    function key(blockType, fieldName) { return blockType + '\u0000' + fieldName; }
    function copyOptions(options) { return options.map(function(option) { return [option[0], option[1]]; }); }

    Object.keys(targets).forEach(function(blockType) {
      var definition = Blockly.Blocks[blockType];
      if (!definition || typeof definition.init !== 'function') fail('field-option block definition unavailable: ' + blockType);
      var scratch = new Blockly.Workspace();
      var block = scratch.newBlock(blockType);
      try {
        Object.keys(targets[blockType]).forEach(function(fieldName) {
          var field = block.getField(fieldName);
          if (!field || typeof field.getOptions !== 'function' || typeof field.setOptions !== 'function')
            fail('public FieldDropdown API unavailable: ' + blockType + '.' + fieldName);
          var options = copyOptions(field.getOptions(false));
          if (!options.length) fail('generic dropdown is empty: ' + blockType + '.' + fieldName);
          var values = Object.create(null);
          options.forEach(function(option) {
            requireString(option[1], 'generic option value ' + blockType + '.' + fieldName);
            if (values[option[1]]) fail('duplicate generic dropdown value: ' + blockType + '.' + fieldName + '=' + option[1]);
            values[option[1]] = true;
          });
          generic[key(blockType, fieldName)] = options;
        });
      } finally {
        if (block && typeof block.dispose === 'function') block.dispose(false);
        if (scratch && typeof scratch.dispose === 'function') scratch.dispose();
      }
    });

    function applyBlock(block, allowDefaultCoercion) {
      var fields = block && targets[block.type];
      if (!fields) return;
      Object.keys(fields).forEach(function(fieldName) {
        var field = block.getField(fieldName);
        if (!field || typeof field.setOptions !== 'function' || typeof field.getValue !== 'function')
          fail('field-option target unavailable: ' + block.type + '.' + fieldName);
        var source = copyOptions(generic[key(block.type, fieldName)]);
        var allowed = active[block.type] && active[block.type][fieldName];
        var options = allowed ? source.filter(function(option) { return allowed.indexOf(option[1]) >= 0; }) : source;
        if (!options.length) fail('active field restriction produced empty dropdown: ' + block.type + '.' + fieldName);
        var previous = field.getValue();
        var previousAllowed = options.some(function(option) { return option[1] === previous; });
        if (!allowDefaultCoercion && !previousAllowed)
          return;
        field.setOptions(options);
        if (typeof field.setValue === 'function') {
          if (allowDefaultCoercion && !previousAllowed)
            field.setValue(options[0][1]);
          else
            field.setValue(previous);
        }
      });
    }

    Object.keys(targets).forEach(function(blockType) {
      var definition = Blockly.Blocks[blockType];
      var originalInit = definition.init;
      definition.init = function() {
        originalInit.call(this);
        if (this.isInFlyout) applyBlock(this, true);
      };
    });

    function applyWorkspace(workspace) {
      if (!workspace || typeof workspace.getAllBlocks !== 'function') return;
      workspace.getAllBlocks(false).forEach(function(block) { applyBlock(block, false); });
      var toolbox = typeof workspace.getToolbox === 'function' ? workspace.getToolbox() : null;
      var flyout = toolbox && typeof toolbox.getFlyout === 'function' ? toolbox.getFlyout() : null;
      var flyoutWorkspace = flyout && typeof flyout.getWorkspace === 'function' ? flyout.getWorkspace() : null;
      if (flyoutWorkspace && typeof flyoutWorkspace.getAllBlocks === 'function')
        flyoutWorkspace.getAllBlocks(false).forEach(function(block) { applyBlock(block, false); });
    }

    function setProfile(profile, workspace) {
      validateProfile(profile, blockCatalog);
      Object.keys(profile.fieldOptions || {}).forEach(function(blockType) {
        Object.keys(profile.fieldOptions[blockType]).forEach(function(fieldName) {
          var source = generic[key(blockType, fieldName)];
          if (!source) fail('unknown dropdown restriction target: ' + blockType + '.' + fieldName);
          var genericValues = source.map(function(option) { return option[1]; });
          profile.fieldOptions[blockType][fieldName].forEach(function(value) {
            if (genericValues.indexOf(value) < 0) fail('unknown generic dropdown value: ' + blockType + '.' + fieldName + '=' + value);
          });
        });
      });
      if (workspace && typeof workspace.getToolbox === 'function') {
        var toolbox = workspace.getToolbox();
        if (toolbox && typeof toolbox.clearSelection === 'function') toolbox.clearSelection();
        var flyout = toolbox && typeof toolbox.getFlyout === 'function' ? toolbox.getFlyout() : null;
        if (flyout && typeof flyout.hide === 'function') flyout.hide();
      }
      active = clone(profile.fieldOptions || {});
      applyWorkspace(workspace);
    }

    function genericOptions(blockType, fieldName) {
      var options = generic[key(blockType, fieldName)];
      if (!options) fail('unknown dropdown target: ' + blockType + '.' + fieldName);
      return copyOptions(options);
    }

    return {setProfile: setProfile, applyWorkspace: applyWorkspace, genericOptions: genericOptions};
  }

  return {
    validateProfile: validateProfile,
    resolveProfile: resolveProfile,
    resolveById: resolveById,
    createFieldOptionController: createFieldOptionController
  };
});
