(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksProjectFiles = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var FORMAT = 'webeeblocks-project';
  var VERSION = 1;
  var SEMANTICS = 'webeeblocks-ast-v1';
  var EXTENSION = '.wbb';
  var LEGACY_EXTENSION = '.webeeblocks.json';
  var OPEN_EXTENSIONS = ['.wbb', '.json'];
  var ROOT_KEYS = ['activity', 'format', 'version', 'workspace'];
  var ACTIVITY_KEYS = ['id', 'semantics'];

  function fail(message) { throw new Error('project file: ' + message); }
  function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function sameJson(left, right) { return JSON.stringify(left) === JSON.stringify(right); }
  function sortedKeys(value) { return Object.keys(value).sort(); }
  function requireExactKeys(value, expected, path) {
    var actual = sortedKeys(value);
    var wanted = expected.slice().sort();
    if (!sameJson(actual, wanted)) fail(path + ' has unsupported fields: ' + actual.join(', '));
  }
  function requireString(value, path) {
    if (typeof value !== 'string' || value.trim() === '') fail(path + ' must be a non-empty string');
  }
  function requireDependencies(options) {
    ['Blockly', 'profiles', 'activitiesDocument', 'blockCatalog', 'semanticAst', 'activityContract'].forEach(function(key) {
      if (!options || !options[key]) fail('missing dependency: ' + key);
    });
  }

  function normalizeName(name) {
    var base = typeof name === 'string' && name.trim() ? name.trim() : 'programme';
    var lower = base.toLowerCase();
    if (lower.endsWith(EXTENSION)) return base;
    if (lower.endsWith(LEGACY_EXTENSION))
      base = base.slice(0, -LEGACY_EXTENSION.length);
    else if (lower.endsWith('.json'))
      base = base.slice(0, -'.json'.length);
    return base + EXTENSION;
  }

  function preserveSelectedName(name) {
    if (typeof name !== 'string' || !name.trim()) fail('selected file has no name');
    return name.trim();
  }

  function validateWorkspaceFields(profile, workspace) {
    var definitions = profile.parameterBounds || {};
    workspace.getAllBlocks(false).forEach(function(block) {
      var fields = definitions[block.type] || {};
      Object.keys(fields).forEach(function(fieldName) {
        var field = block.getField(fieldName);
        if (!field || typeof field.getValue !== 'function') fail('workspace field unavailable: ' + block.type + '.' + fieldName);
        var value = Number(field.getValue());
        var bounds = fields[fieldName];
        if (!Number.isFinite(value) || value < bounds.min || value > bounds.max)
          fail('workspace field outside profile bounds: ' + block.type + '.' + fieldName);
      });
    });
  }

  function optionalAst(profile, workspace, options) {
    try {
      var ast = options.semanticAst.compileWorkspace(workspace);
      options.activityContract.preflightAst(profile, ast);
      if (ast.semantics !== SEMANTICS) fail('unsupported AST semantics: ' + String(ast.semantics));
      return ast;
    } catch (error) {
      var message = String(error && error.message || error);
      var incomplete = [
        'Crazyflie program must have exactly one top-level sequence',
        'program must start with takeoff and end with land',
        'missing value input '
      ].some(function(fragment) { return message.indexOf(fragment) >= 0; });
      if (incomplete) return null;
      throw error;
    }
  }

  function createProject(profile, workspace, options) {
    requireDependencies(options);
    if (!profile || typeof profile.id !== 'string') fail('current activity unavailable');
    options.activityContract.preflightWorkspace(profile, workspace);
    validateWorkspaceFields(profile, workspace);
    return {
      format: FORMAT,
      version: VERSION,
      activity: {id: profile.id, semantics: SEMANTICS},
      workspace: options.Blockly.serialization.workspaces.save(workspace)
    };
  }

  function encodeProject(profile, workspace, options) {
    return JSON.stringify(createProject(profile, workspace, options), null, 2) + '\n';
  }

  function parseProject(text) {
    var value;
    try { value = JSON.parse(String(text)); }
    catch (error) { fail('invalid JSON'); }
    if (!isObject(value)) fail('root must be an object');
    requireExactKeys(value, ROOT_KEYS, 'root');
    if (value.format !== FORMAT) fail('unsupported format');
    if (value.version !== VERSION) fail('unsupported version: ' + String(value.version));
    if (!isObject(value.activity)) fail('activity must be an object');
    requireExactKeys(value.activity, ACTIVITY_KEYS, 'activity');
    requireString(value.activity.id, 'activity.id');
    if (value.activity.semantics !== SEMANTICS) fail('unsupported AST semantics: ' + String(value.activity.semantics));
    if (!isObject(value.workspace)) fail('workspace must be an object');
    return value;
  }

  function validateProjectText(text, currentProfile, options) {
    requireDependencies(options);
    var project = parseProject(text);
    var profile = options.profiles.resolveById(options.activitiesDocument, project.activity.id, options.blockCatalog);
    if (!currentProfile || profile.world !== currentProfile.world)
      fail('activity is incompatible with the current Webots world');

    var temporary = new options.Blockly.Workspace();
    try {
      options.Blockly.serialization.workspaces.load(project.workspace, temporary);
      options.activityContract.preflightWorkspace(profile, temporary);
      validateWorkspaceFields(profile, temporary);
      var ast = optionalAst(profile, temporary, options);
      return {project: project, profile: profile, ast: ast};
    } catch (error) {
      if (String(error && error.message || error).indexOf('project file: ') === 0) throw error;
      fail('invalid workspace: ' + String(error && error.message || error));
    } finally {
      if (temporary && typeof temporary.dispose === 'function') temporary.dispose();
    }
  }

  function createBrowserTransport(browserWindow, documentObject) {
    if (!browserWindow || !documentObject) fail('browser transport requires window and document');
    var nativeAccess = typeof browserWindow.showOpenFilePicker === 'function' &&
      typeof browserWindow.showSaveFilePicker === 'function';

    function openPickerOptions() {
      return {
        types: [{description: 'Projet WebeeBlocks', accept: {'application/json': OPEN_EXTENSIONS.slice()}}],
        excludeAcceptAllOption: false,
        multiple: false
      };
    }
    function savePickerOptions(name) {
      return {
        suggestedName: normalizeName(name),
        types: [{description: 'Projet WebeeBlocks', accept: {'application/json': [EXTENSION]}}],
        excludeAcceptAllOption: true
      };
    }
    function requireNative() {
      if (!nativeAccess) fail('File System Access unavailable; use Google Chrome');
    }
    async function writeHandle(handle, text) {
      if (!handle || typeof handle.createWritable !== 'function') fail('current file handle unavailable');
      var writable = await handle.createWritable();
      try { await writable.write(text); }
      finally { await writable.close(); }
    }
    return {
      nativeFileSystemAccess: nativeAccess,
      async open() {
        requireNative();
        var handles = await browserWindow.showOpenFilePicker(openPickerOptions());
        if (!handles || handles.length !== 1) fail('open returned no file');
        var file = await handles[0].getFile();
        return {handle: handles[0], name: preserveSelectedName(file.name), text: await file.text(), mode: 'native'};
      },
      async saveAs(name, text) {
        requireNative();
        var proposal = normalizeName(name);
        var handle = await browserWindow.showSaveFilePicker(savePickerOptions(proposal));
        await writeHandle(handle, text);
        return {handle: handle, name: preserveSelectedName(handle.name || proposal), mode: 'native'};
      },
      async save(target, name, text) {
        requireNative();
        await writeHandle(target, text);
        return {handle: target, name: preserveSelectedName(target.name || name), mode: 'native'};
      }
    };
  }

  function createManager(options) {
    requireDependencies(options);
    if (!options.workspace || typeof options.getProfile !== 'function' || typeof options.setProfile !== 'function' || !options.transport)
      fail('manager dependencies incomplete');
    var targetHandle = null;
    var targetName = null;
    var applying = false;

    function dependencies() {
      return {
        Blockly: options.Blockly,
        profiles: options.profiles,
        activitiesDocument: options.activitiesDocument,
        blockCatalog: options.blockCatalog,
        semanticAst: options.semanticAst,
        activityContract: options.activityContract
      };
    }
    function currentBytes() { return encodeProject(options.getProfile(), options.workspace, dependencies()); }
    function snapshot() {
      return {profile: options.getProfile(), workspace: options.Blockly.serialization.workspaces.save(options.workspace)};
    }
    function restore(saved) {
      options.setProfile(saved.profile);
      options.workspace.clear();
      options.Blockly.serialization.workspaces.load(saved.workspace, options.workspace);
      options.activityContract.applyFieldBounds(saved.profile, options.workspace);
    }
    function applyValidated(validated) {
      var before = snapshot();
      applying = true;
      try {
        options.setProfile(validated.profile);
        options.workspace.clear();
        options.Blockly.serialization.workspaces.load(validated.project.workspace, options.workspace);
        options.activityContract.applyFieldBounds(validated.profile, options.workspace);
        options.activityContract.preflightWorkspace(validated.profile, options.workspace);
        validateWorkspaceFields(validated.profile, options.workspace);
        if (validated.ast) {
          var loadedAst = options.semanticAst.compileWorkspace(options.workspace);
          options.activityContract.preflightAst(validated.profile, loadedAst);
          if (!sameJson(loadedAst, validated.ast)) fail('loaded workspace differs from validated project');
        }
      } catch (error) {
        try { restore(before); } catch (rollbackError) { console.error('WebeeBlocks project rollback failed', rollbackError); }
        throw error;
      } finally { applying = false; }
    }
    return {
      async open() {
        var opened = await options.transport.open();
        var validated = validateProjectText(opened.text, options.getProfile(), dependencies());
        applyValidated(validated);
        targetHandle = opened.handle || null;
        targetName = preserveSelectedName(opened.name || validated.profile.id + EXTENSION);
        return {name: targetName, ast: validated.ast, mode: opened.mode || null};
      },
      async saveAs(name) {
        var proposal = normalizeName(name || targetName || options.getProfile().id);
        var result = await options.transport.saveAs(proposal, currentBytes());
        targetHandle = result.handle || null;
        targetName = preserveSelectedName(result.name || proposal);
        return {name: targetName, mode: result.mode || null};
      },
      async save() {
        if (!targetHandle || !targetName) fail('no current file; use Save As');
        var result = await options.transport.save(targetHandle, targetName, currentBytes());
        targetHandle = result.handle || targetHandle;
        targetName = preserveSelectedName(result.name || targetName);
        return {name: targetName, mode: result.mode || null};
      },
      currentName: function() { return targetName; },
      hasCurrentTarget: function() { return !!targetHandle && !!targetName; },
      isApplying: function() { return applying; },
      nativeFileSystemAccess: !!options.transport.nativeFileSystemAccess,
      encodeCurrent: currentBytes
    };
  }

  return {
    FORMAT: FORMAT,
    VERSION: VERSION,
    SEMANTICS: SEMANTICS,
    EXTENSION: EXTENSION,
    LEGACY_EXTENSION: LEGACY_EXTENSION,
    OPEN_EXTENSIONS: OPEN_EXTENSIONS.slice(),
    normalizeName: normalizeName,
    preserveSelectedName: preserveSelectedName,
    createProject: createProject,
    encodeProject: encodeProject,
    parseProject: parseProject,
    validateProjectText: validateProjectText,
    createBrowserTransport: createBrowserTransport,
    createManager: createManager
  };
});
