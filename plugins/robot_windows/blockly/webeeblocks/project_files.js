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
    if (typeof value !== 'string' || !value.trim()) fail(path + ' must be a non-empty string');
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

  function createStarterText(activityId) {
    requireString(activityId, 'activity.id');
    return JSON.stringify({
      format: FORMAT,
      version: VERSION,
      activity: {id: activityId.trim(), semantics: SEMANTICS},
      workspace: {blocks: {languageVersion: 0, blocks: []}}
    }, null, 2) + '\n';
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

  function validateSerializedFieldOptions(profile, workspaceState) {
    var definitions = profile.fieldOptions || {};
    function visit(value) {
      if (Array.isArray(value)) { value.forEach(visit); return; }
      if (!isObject(value)) return;
      if (typeof value.type === 'string' && isObject(value.fields) && definitions[value.type]) {
        var fields = definitions[value.type];
        Object.keys(fields).forEach(function(fieldName) {
          if (!Object.prototype.hasOwnProperty.call(value.fields, fieldName)) return;
          var fieldValue = value.fields[fieldName];
          if (fields[fieldName].indexOf(fieldValue) < 0)
            fail('workspace field forbidden by profile: ' + value.type + '.' + fieldName + '=' + String(fieldValue));
        });
      }
      Object.keys(value).forEach(function(key) { visit(value[key]); });
    }
    visit(workspaceState);
    return true;
  }


  // Blockly's generic SPEED field has 0.1 precision and can round saved
  // classroom A2/A3 values before profile-specific 0.01 bounds are installed.
  // Restore only exact, authorized school values; the Grand Prix is unchanged.
  function loadWorkspaceWithProfile(profile, state, workspace, options) {
    requireDependencies(options);
    options.Blockly.serialization.workspaces.load(state, workspace);
    if (profile.id !== 'progression-altitude-v1' &&
        profile.id !== 'progression-orientation-3d-v1') return workspace;
    var lesson = profile.id === 'progression-altitude-v1' ? 'Activity 2' : 'Activity 3';
    options.activityContract.applyFieldBounds(profile, workspace);
    var limits = profile.parameterBounds && profile.parameterBounds.webeeblocks_v2_speed &&
      profile.parameterBounds.webeeblocks_v2_speed.SPEED;
    if (!limits || limits.step !== 0.01)
      fail(lesson + ' speed constraints unavailable');
    var seen = Object.create(null);
    function visit(value) {
      if (Array.isArray(value)) { value.forEach(visit); return; }
      if (!isObject(value)) return;
      if (value.type === 'webeeblocks_v2_speed' && isObject(value.fields) &&
          Object.prototype.hasOwnProperty.call(value.fields, 'SPEED')) {
        if (typeof value.id !== 'string' || !value.id || seen[value.id])
          fail(lesson + ' invalid speed block identity');
        seen[value.id] = true;
        var requested = value.fields.SPEED;
        if (typeof requested !== 'number' || !Number.isFinite(requested) ||
            requested < limits.min || requested > limits.max ||
            Math.abs((requested - limits.min) / limits.step -
              Math.round((requested - limits.min) / limits.step)) > 1e-7)
          fail(lesson + ' serialized speed outside profile bounds or step');
        var block = typeof workspace.getBlockById === 'function' && workspace.getBlockById(value.id);
        var field = block && block.type === 'webeeblocks_v2_speed' && block.getField('SPEED');
        if (!field || typeof field.setValue !== 'function' || typeof field.getValue !== 'function')
          fail(lesson + ' speed block missing after load');
        field.setValue(requested);
        if (Number(field.getValue()) !== requested)
          fail(lesson + ' speed precision changed during Open');
      }
      Object.keys(value).forEach(function(key) { visit(value[key]); });
    }
    visit(state);
    return workspace;
  }

  function validateProjectText(text, currentProfile, options, portableImport) {
    requireDependencies(options);
    var project = parseProject(text);
    var profile = options.profiles.resolveById(options.activitiesDocument, project.activity.id, options.blockCatalog);
    if (!currentProfile || (!portableImport && profile.world !== currentProfile.world))
      fail('activity is incompatible with the current Webots world');
    validateSerializedFieldOptions(profile, project.workspace);

    var temporary = new options.Blockly.Workspace();
    try {
      loadWorkspaceWithProfile(profile, project.workspace, temporary, options);
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
      // File System Access commits the temporary file on close(). A failed
      // write must abort instead: closing here could replace a valid .wbb
      // with incomplete student work.
      if (!writable || typeof writable.write !== 'function' ||
          typeof writable.close !== 'function' || typeof writable.abort !== 'function')
        fail('transactional file stream unavailable');
      try {
        await writable.write(text);
        await writable.close();
      } catch (error) {
        try { await writable.abort(); }
        catch (abortError) {
          if (error && typeof error === 'object') {
            // Diagnostic annotation is best-effort: DOM/host errors may be frozen.
            try { error.abortError = abortError; }
            catch (_) { /* Never replace the original write error. */ }
          }
        }
        throw error;
      }
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
      },
      async release() {}
    };
  }

  function createManager(options) {
    requireDependencies(options);
    if (!options.workspace || typeof options.getProfile !== 'function' || typeof options.setProfile !== 'function' || !options.transport)
      fail('manager dependencies incomplete');
    var targetHandle = null;
    var targetName = null;
    var applying = false;
    // In foreign contexts preserve the source profile as a safe Save fallback.
    // It never selects or authorizes a native scene.
    var importedSourceProfile = null;

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
    function currentBytes() {
      try { return encodeProject(options.getProfile(), options.workspace, dependencies()); }
      catch (error) {
        // If the current activity cannot express all imported blocks, keep
        // their original (validated) source activity contract on disk.
        if (!importedSourceProfile) throw error;
        return encodeProject(importedSourceProfile, options.workspace, dependencies());
      }
    }
    function snapshot() {
      return {profile: options.getProfile(), workspace: options.Blockly.serialization.workspaces.save(options.workspace)};
    }
    function restore(saved) {
      options.setProfile(saved.profile);
      options.workspace.clear();
      loadWorkspaceWithProfile(saved.profile, saved.workspace, options.workspace, dependencies());
      options.activityContract.applyFieldBounds(saved.profile, options.workspace);
    }
    async function releaseTarget(handle) {
      if (!handle || typeof options.transport.release !== 'function') return;
      try { await options.transport.release(handle); }
      catch (error) { console.warn('WebeeBlocks project target release failed', error); }
    }
    function applyValidated(validated) {
      var before = snapshot();
      applying = true;
      try {
        options.setProfile(validated.profile);
        options.workspace.clear();
        loadWorkspaceWithProfile(validated.profile, validated.project.workspace, options.workspace, dependencies());
        options.activityContract.applyFieldBounds(validated.profile, options.workspace);
        options.activityContract.preflightWorkspace(validated.profile, options.workspace);
        validateWorkspaceFields(validated.profile, options.workspace);
        if (validated.ast) {
          var loadedAst = options.semanticAst.compileWorkspace(options.workspace);
          options.activityContract.preflightAst(validated.profile, loadedAst);
          if (!sameJson(loadedAst, validated.ast)) fail('loaded workspace differs from validated project');
        }
        importedSourceProfile = null;
      } catch (error) {
        try { restore(before); } catch (rollbackError) { console.error('WebeeBlocks project rollback failed', rollbackError); }
        throw error;
      } finally { applying = false; }
    }
    function applyPortableImport(validated) {
      // Deliberately retain the current activity and native scene. Open may
      // accept valid foreign blocks; the flight preflight still validates
      // against options.getProfile() and rejects incompatible blocks.
      var previous = snapshot();
      var previousSource = importedSourceProfile;
      applying = true;
      try {
        options.workspace.clear();
        loadWorkspaceWithProfile(validated.profile, validated.project.workspace,
                                 options.workspace, dependencies());
        options.activityContract.preflightWorkspace(validated.profile, options.workspace);
        validateWorkspaceFields(validated.profile, options.workspace);
        if (validated.ast) {
          var loaded = options.semanticAst.compileWorkspace(options.workspace);
          options.activityContract.preflightAst(validated.profile, loaded);
          if (!sameJson(loaded, validated.ast)) fail('portable project changed AST');
        }
        if (options.getProfile() !== previous.profile)
          fail('portable Open changed the active activity');
        importedSourceProfile = validated.profile;
      } catch (error) {
        importedSourceProfile = previousSource;
        try {
          // Portable Open did not select a profile. Restore the foreign
          // workspace under its own source contract, not the active toolbox.
          if (options.getProfile() !== previous.profile) options.setProfile(previous.profile);
          options.workspace.clear();
          loadWorkspaceWithProfile(previousSource || previous.profile, previous.workspace,
                                   options.workspace, dependencies());
          if (!previousSource)
            options.activityContract.applyFieldBounds(previous.profile, options.workspace);
        }
        catch (rollbackError) { error.rollbackError = rollbackError; }
        throw error;
      } finally { applying = false; }
    }

    async function prepareAndApply(validated) {
      var previousProfile = options.getProfile();
      if (typeof options.prepareProfile === 'function') await options.prepareProfile(validated.profile);
      try { applyValidated(validated); }
      catch (error) {
        // Preparation was acknowledged, but the live workspace failed to load.
        // Restore its scene as well as the profile/workspace restored above.
        if (typeof options.prepareProfile === 'function') {
          try { await options.prepareProfile(previousProfile); }
          catch (restorationError) { error.sceneRestorationError = restorationError; }
        }
        throw error;
      }
    }
    async function applyTemplateText(name, text, mode) {
      var validated = validateProjectText(text, options.getProfile(), dependencies());
      var templateName = preserveSelectedName(name || validated.profile.id + EXTENSION);
      await prepareAndApply(validated);
      var previousHandle = targetHandle;
      targetHandle = null;
      targetName = null;
      if (previousHandle) await releaseTarget(previousHandle);
      return {name: templateName, ast: validated.ast, mode: mode || null};
    }
    return {
      async openIntoCurrentActivity() {
        var opened = await options.transport.open();
        var handle = opened.handle || null;
        var validated, selectedName;
        try {
          // The file's source activity authenticates its blocks and fields;
          // the *current* activity remains the only authority for execution.
          validated = validateProjectText(opened.text, options.getProfile(),
                                          dependencies(), true);
          selectedName = preserveSelectedName(opened.name || validated.profile.id + EXTENSION);
          applyPortableImport(validated);
        } catch (error) {
          if (handle && handle !== targetHandle) await releaseTarget(handle);
          throw error;
        }
        var old = targetHandle;
        targetHandle = handle;
        targetName = selectedName;
        if (old && old !== handle) await releaseTarget(old);
        return {name: selectedName, ast: validated.ast,
                sourceActivity: validated.profile.id,
                activity: options.getProfile().id, mode: opened.mode || null};
      },
      async open() {
        var opened = await options.transport.open();
        var nextHandle = opened.handle || null;
        var validated;
        var nextName;
        try {
          validated = validateProjectText(opened.text, options.getProfile(), dependencies());
          await prepareAndApply(validated);
          nextName = preserveSelectedName(opened.name || validated.profile.id + EXTENSION);
        } catch (error) {
          if (nextHandle && nextHandle !== targetHandle) await releaseTarget(nextHandle);
          throw error;
        }
        var previousHandle = targetHandle;
        targetHandle = nextHandle;
        targetName = nextName;
        if (previousHandle && previousHandle !== targetHandle) await releaseTarget(previousHandle);
        return {name: targetName, ast: validated.ast, mode: opened.mode || null};
      },
      async openTemplate() {
        var opened = await options.transport.open();
        var templateHandle = opened.handle || null;
        var previousHandle = targetHandle;
        try {
          var result = await applyTemplateText(opened.name, opened.text, opened.mode || null);
          if (templateHandle && templateHandle !== previousHandle) await releaseTarget(templateHandle);
          return result;
        } catch (error) {
          if (templateHandle && templateHandle !== targetHandle) await releaseTarget(templateHandle);
          throw error;
        }
      },
      async openTemplateText(name, text) {
        return applyTemplateText(name, text, 'embedded');
      },
      async saveAs(name) {
        var proposal = normalizeName(name || targetName || options.getProfile().id);
        var result = await options.transport.saveAs(proposal, currentBytes());
        var nextHandle = result.handle || null;
        var nextName;
        try { nextName = preserveSelectedName(result.name || proposal); }
        catch (error) {
          if (nextHandle && nextHandle !== targetHandle) await releaseTarget(nextHandle);
          throw error;
        }
        var previousHandle = targetHandle;
        targetHandle = nextHandle;
        targetName = nextName;
        if (previousHandle && previousHandle !== targetHandle) await releaseTarget(previousHandle);
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
    createStarterText: createStarterText,
    parseProject: parseProject,
    validateProjectText: validateProjectText,
    loadWorkspaceWithProfile: loadWorkspaceWithProfile,
    createBrowserTransport: createBrowserTransport,
    createManager: createManager
  };
});
