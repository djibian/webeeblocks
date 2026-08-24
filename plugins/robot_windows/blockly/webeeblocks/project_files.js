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
  var EXTENSION = '.webeeblocks.json';
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
    return base.toLowerCase().endsWith(EXTENSION) ? base : base + EXTENSION;
  }

  function createProject(profile, workspace, options) {
    requireDependencies(options);
    if (!profile || typeof profile.id !== 'string') fail('current activity unavailable');
    options.activityContract.preflightWorkspace(profile, workspace);
    var ast = options.semanticAst.compileWorkspace(workspace);
    options.activityContract.preflightAst(profile, ast);
    if (ast.semantics !== SEMANTICS) fail('unsupported AST semantics: ' + String(ast.semantics));
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
      var ast = options.semanticAst.compileWorkspace(temporary);
      options.activityContract.preflightAst(profile, ast);
      if (ast.semantics !== project.activity.semantics) fail('workspace semantics mismatch');
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
    var nativeAccess = typeof browserWindow.showOpenFilePicker === 'function' && typeof browserWindow.showSaveFilePicker === 'function';

    function pickerOptions() {
      return {
        types: [{description: 'Projet WebeeBlocks', accept: {'application/json': [EXTENSION]}}],
        excludeAcceptAllOption: false,
        multiple: false
      };
    }
    function download(name, text) {
      var blob = new browserWindow.Blob([text], {type: 'application/json'});
      var url = browserWindow.URL.createObjectURL(blob);
      var anchor = documentObject.createElement('a');
      anchor.href = url;
      anchor.download = normalizeName(name);
      anchor.style.display = 'none';
      documentObject.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      browserWindow.setTimeout(function() { browserWindow.URL.revokeObjectURL(url); }, 0);
      return Promise.resolve({handle: null, name: anchor.download, mode: 'download'});
    }
    function upload() {
      return new Promise(function(resolve, reject) {
        var input = documentObject.createElement('input');
        input.type = 'file';
        input.accept = EXTENSION + ',application/json';
        input.style.display = 'none';
        documentObject.body.appendChild(input);
        input.addEventListener('change', function() {
          var file = input.files && input.files[0];
          input.remove();
          if (!file) { reject(new Error('project file: open cancelled')); return; }
          file.text().then(function(text) { resolve({handle: null, name: file.name, text: text, mode: 'upload'}); }, reject);
        }, {once: true});
        input.click();
      });
    }
    async function writeHandle(handle, text) {
      var writable = await handle.createWritable();
      try { await writable.write(text); }
      finally { await writable.close(); }
    }
    return {
      nativeFileSystemAccess: nativeAccess,
      async open() {
        if (!nativeAccess) return upload();
        var handles = await browserWindow.showOpenFilePicker(pickerOptions());
        if (!handles || handles.length !== 1) fail('open cancelled');
        var file = await handles[0].getFile();
        return {handle: handles[0], name: file.name, text: await file.text(), mode: 'native'};
      },
      async saveAs(name, text) {
        if (!nativeAccess) return download(name, text);
        var handle = await browserWindow.showSaveFilePicker(Object.assign({suggestedName: normalizeName(name)}, pickerOptions()));
        await writeHandle(handle, text);
        return {handle: handle, name: handle.name || normalizeName(name), mode: 'native'};
      },
      async save(target, name, text) {
        if (target && typeof target.createWritable === 'function') {
          await writeHandle(target, text);
          return {handle: target, name: target.name || normalizeName(name), mode: 'native'};
        }
        return download(name, text);
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
        var loadedAst = options.semanticAst.compileWorkspace(options.workspace);
        options.activityContract.preflightAst(validated.profile, loadedAst);
        if (!sameJson(loadedAst, validated.ast)) fail('loaded workspace differs from validated project');
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
        targetName = normalizeName(opened.name || validated.profile.id);
        return {name: targetName, ast: validated.ast, mode: opened.mode || null};
      },
      async saveAs(name) {
        var result = await options.transport.saveAs(normalizeName(name || targetName || options.getProfile().id), currentBytes());
        targetHandle = result.handle || null;
        targetName = normalizeName(result.name || name || options.getProfile().id);
        return {name: targetName, mode: result.mode || null};
      },
      async save() {
        if (!targetName) return this.saveAs(options.getProfile().id);
        var result = await options.transport.save(targetHandle, targetName, currentBytes());
        targetHandle = result.handle || targetHandle;
        targetName = normalizeName(result.name || targetName);
        return {name: targetName, mode: result.mode || null};
      },
      currentName: function() { return targetName; },
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
    normalizeName: normalizeName,
    createProject: createProject,
    encodeProject: encodeProject,
    parseProject: parseProject,
    validateProjectText: validateProjectText,
    createBrowserTransport: createBrowserTransport,
    createManager: createManager
  };
});
