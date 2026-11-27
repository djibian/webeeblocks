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
  function projectFail(message, detail) {
    var error = new Error('project file: ' + message);
    error.code = 'PROJECT_INVALID';
    error.studentDetail = detail;
    throw error;
  }
  function classifyFailure(operation, error) {
    var opening = operation === 'open' || operation === 'activity';
    var saving = operation === 'save' || operation === 'saveAs';
    var prefix = operation === 'variant' ? 'Impossible de changer de parcours' :
      opening ? 'Impossible d’ouvrir ce projet' : 'Impossible d’enregistrer ce projet';
    var detail;
    // Uncertain rollback or write cleanup is never presented as a safe retry.
    if (error && (error.rollbackError || error.abortError))
      detail = 'Prévenez votre enseignant avant de poursuivre : l’état du projet doit être vérifié.';
    else if (error && (error.code === 'PROJECT_INVALID' || error.code === 'PROGRAM_INVALID') &&
             typeof error.studentDetail === 'string' && error.studentDetail)
      detail = error.studentDetail;
    else if (error && error.name === 'ProjectFileBrokerError' && error.code === 'BUSY')
      detail = 'Attendez la fin de l’opération en cours.';
    else if (saving && error && error.name === 'ProjectFileBrokerError' && error.code === 'TARGET_UNAVAILABLE')
      detail = 'Utilisez « Enregistrer sous » pour choisir un nouveau fichier.';
    else if (error && error.name === 'NotAllowedError')
      detail = 'Vérifiez que vous avez autorisé l’accès au fichier ou au dossier.';
    else if (error && error.name === 'NotFoundError')
      detail = 'Vérifiez que le fichier ou le dossier est toujours accessible.';
    else if (saving && error && error.name === 'QuotaExceededError')
      detail = 'L’espace de stockage est insuffisant. Choisissez un autre dossier.';
    else if (saving)
      detail = 'Vérifiez l’accès au dossier et l’espace disponible. Si le problème persiste, prévenez votre enseignant.';
    else
      detail = 'Vérifiez le fichier ou la connexion à la simulation. Si le problème persiste, prévenez votre enseignant.';
    return prefix + ' — ' + detail;
  }
  function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function sameJson(left, right) { return JSON.stringify(left) === JSON.stringify(right); }
  function sortedKeys(value) { return Object.keys(value).sort(); }
  function requireExactKeys(value, expected, path) {
    var actual = sortedKeys(value);
    var wanted = expected.slice().sort();
    if (!sameJson(actual, wanted)) projectFail(path + ' has unsupported fields: ' + actual.join(', '), 'Ce fichier ne possède pas la structure attendue d’un projet WebeeBlocks. Choisissez un fichier .wbb valide.');
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
          projectFail('workspace field outside profile bounds: ' + block.type + '.' + fieldName, 'Une valeur du programme dépasse les limites de son activité. Corrigez-la avant d’enregistrer ou choisissez un projet compatible.');
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
    catch (error) { projectFail('invalid JSON', 'Le fichier est illisible ou incomplet. Choisissez un fichier .wbb enregistré avec WebeeBlocks.'); }
    if (!isObject(value)) projectFail('root must be an object', 'Ce fichier n’est pas un projet WebeeBlocks. Choisissez un fichier .wbb.');
    requireExactKeys(value, ROOT_KEYS, 'root');
    if (value.format !== FORMAT) projectFail('unsupported format', 'Ce fichier n’est pas un projet WebeeBlocks reconnu. Choisissez un fichier .wbb.');
    if (value.version !== VERSION) projectFail('unsupported version: ' + String(value.version), 'Ce projet utilise une version non prise en charge. Demandez à votre enseignant la version de WebeeBlocks adaptée.');
    if (!isObject(value.activity)) projectFail('activity must be an object', 'L’activité du projet est manquante ou invalide. Choisissez un fichier .wbb valide.');
    requireExactKeys(value.activity, ACTIVITY_KEYS, 'activity');
    if (typeof value.activity.id !== 'string' || !value.activity.id.trim())
      projectFail('activity.id must be a non-empty string', 'L’activité du projet est manquante. Choisissez un fichier .wbb valide.');
    if (value.activity.semantics !== SEMANTICS) projectFail('unsupported AST semantics: ' + String(value.activity.semantics), 'Ce programme utilise une version de blocs non prise en charge. Demandez à votre enseignant une version compatible.');
    if (!isObject(value.workspace)) projectFail('workspace must be an object', 'Les blocs du projet sont manquants ou invalides. Choisissez un autre fichier .wbb.');
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
            projectFail('workspace field forbidden by profile: ' + value.type + '.' + fieldName + '=' + String(fieldValue), 'Le projet contient une option de bloc incompatible avec son activité. Choisissez un projet compatible.');
        });
      }
      Object.keys(value).forEach(function(key) { visit(value[key]); });
    }
    visit(workspaceState);
    return true;
  }


  // Blockly's generic SPEED field has 0.1 precision and can round saved
  // values before the source activity's finer constraints are installed.
  // Restore only exact, authorized values; never clamp a foreign project.
  function loadWorkspaceWithProfile(profile, state, workspace, options) {
    requireDependencies(options);
    options.Blockly.serialization.workspaces.load(state, workspace);
    var grandPrix = /^progression-grand-prix-(?:a[1-7]-v1|route-v2)$/.test(profile.id);
    if (!grandPrix && profile.id !== 'progression-altitude-v1' &&
        profile.id !== 'progression-orientation-3d-v1') return workspace;
    var lesson = grandPrix ? 'Grand Prix' :
      (profile.id === 'progression-altitude-v1' ? 'Activity 2' : 'Activity 3');
    if (!grandPrix) options.activityContract.applyFieldBounds(profile, workspace);
    var limits = profile.parameterBounds && profile.parameterBounds.webeeblocks_v2_speed &&
      profile.parameterBounds.webeeblocks_v2_speed.SPEED;
    if (!limits || limits.step !== (grandPrix ? 0.05 : 0.01))
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
        if (grandPrix) {
          if (typeof field.setConstraints !== 'function')
            fail(lesson + ' speed field constraints unavailable');
          field.setConstraints(limits.min, limits.max, limits.step);
        }
        field.setValue(requested);
        if (Number(field.getValue()) !== requested)
          fail(lesson + ' speed precision changed during Open');
      }
      Object.keys(value).forEach(function(key) { visit(value[key]); });
    }
    visit(state);
    return workspace;
  }

  // Blockly FieldNumber may clamp or round serialized values while loading.
  // Validate the original value, not only its normalized live representation.
  // The portable path may restore finer source constraints, never silently
  // repair a malformed value or change the meaning of an imported program.
  function preservePortableFields(profile, state, workspace, Blockly) {
    var definitions = profile.parameterBounds || {};
    var roots = state.blocks && state.blocks.blocks;
    function visit(blockState) {
      if (!isObject(blockState)) return;
      var block = workspace.getBlockById(blockState.id);
      var declared = definitions[blockState.type] || {};
      Object.keys(blockState.fields || {}).forEach(function(name) {
        var requested = blockState.fields[name];
        var field = block && block.type === blockState.type && block.getField(name);
        // Dropdown deserialization can silently retain its default when the
        // serialized option is unknown. Variables use identity objects, not
        // ordinary dropdown options, and have their own serialization contract.
        if (field && typeof Blockly.FieldDropdown === 'function' &&
            field instanceof Blockly.FieldDropdown &&
            !(typeof Blockly.FieldVariable === 'function' && field instanceof Blockly.FieldVariable)) {
          if (typeof requested !== 'string' || field.getValue() !== requested)
            fail('serialized dropdown field changed during Open: ' + blockState.type + '.' + name);
          return;
        }
        var bounds = declared[name];
        var actual = field && typeof field.getValue === 'function' ? field.getValue() : undefined;
        if (!bounds && typeof actual !== 'number' && typeof requested !== 'number') return;
        if (!field || typeof requested !== 'number' || !Number.isFinite(requested) ||
            typeof actual !== 'number')
          fail('invalid serialized numeric field: ' + blockState.type + '.' + name);
        if (bounds && (requested < bounds.min || requested > bounds.max))
          fail('serialized numeric field outside profile bounds: ' + blockState.type + '.' + name);
        if (actual !== requested && bounds && typeof field.setConstraints === 'function' &&
            typeof field.setValue === 'function' &&
            Math.abs(requested / bounds.step - Math.round(requested / bounds.step)) <= 1e-7) {
          field.setConstraints(bounds.min, bounds.max, bounds.step);
          field.setValue(requested);
        }
        if (field.getValue() !== requested)
          fail('serialized numeric field changed during Open: ' + blockState.type + '.' + name);
      });
      // Only active blocks exist in the loaded workspace. A dormant shadow
      // alongside an explicit input block is not a second live block.
      Object.keys(blockState.inputs || {}).forEach(function(name) {
        var input = blockState.inputs[name];
        if (isObject(input)) visit(input.block || input.shadow);
      });
      if (isObject(blockState.next)) visit(blockState.next.block || blockState.next.shadow);
    }
    if (Array.isArray(roots)) roots.forEach(visit);
  }

  function validateProjectText(text, currentProfile, options, portableImport) {
    requireDependencies(options);
    var project = parseProject(text);
    var sourceDocument = portableImport && options.portableActivitiesDocument || options.activitiesDocument;
    var profile = options.profiles.resolveById(sourceDocument, project.activity.id, options.blockCatalog);
    if (!currentProfile || (!portableImport && profile.world !== currentProfile.world))
      projectFail('activity is incompatible with the current Webots world', 'Ce projet appartient à une autre activité ou simulation. Ouvrez-le dans la simulation correspondante.');
    validateSerializedFieldOptions(profile, project.workspace);

    var temporary = new options.Blockly.Workspace();
    try {
      loadWorkspaceWithProfile(profile, project.workspace, temporary, options);
      if (portableImport) preservePortableFields(profile, project.workspace, temporary, options.Blockly);
      options.activityContract.preflightWorkspace(profile, temporary);
      validateWorkspaceFields(profile, temporary);
      var ast = optionalAst(profile, temporary, options);
      return {project: project, profile: profile, ast: ast};
    } catch (error) {
      if (String(error && error.message || error).indexOf('project file: ') === 0) throw error;
      if (error && error.code === 'PROGRAM_INVALID' && typeof error.studentDetail === 'string' && error.studentDetail)
        projectFail('invalid workspace: ' + String(error.message), error.studentDetail);
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
        portableActivitiesDocument: options.portableActivitiesDocument,
        blockCatalog: options.blockCatalog,
        semanticAst: options.semanticAst,
        activityContract: options.activityContract
      };
    }
    function currentBytes() {
      var current = options.getProfile();
      var deps = dependencies();
      if (!importedSourceProfile) return encodeProject(current, options.workspace, deps);

      function portableBytes(profile) {
        var text = encodeProject(profile, options.workspace, deps);
        // Block vocabulary alone is insufficient: numeric AST limits and
        // serialized precision can differ even when all block types match.
        // Reopen in a scratch workspace before committing the file, and
        // never retag an import whose executable program would change.
        var liveAst = optionalAst(profile, options.workspace, deps);
        var reopened = validateProjectText(text, current, deps, true);
        if (reopened.profile.id !== profile.id || !sameJson(liveAst, reopened.ast))
          fail('portable Save would change the program');
        return text;
      }

      try { return portableBytes(current); }
      catch (error) {
        // Preserve the source only if the edited project is still valid there.
        // Do not silently relabel a program invalid under both profiles.
        if (importedSourceProfile.id === current.id) throw error;
        return portableBytes(importedSourceProfile);
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
        preservePortableFields(validated.profile, validated.project.workspace, options.workspace, options.Blockly);
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
          if (previousSource) preservePortableFields(previousSource, previous.workspace, options.workspace, options.Blockly);
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
        if (!targetHandle || !targetName) projectFail('no current file; use Save As', 'Utilisez « Enregistrer sous » pour choisir un fichier.');
        var result = await options.transport.save(targetHandle, targetName, currentBytes());
        targetHandle = result.handle || targetHandle;
        targetName = preserveSelectedName(result.name || targetName);
        return {name: targetName, mode: result.mode || null};
      },
      currentName: function() { return targetName; },
      hasCurrentTarget: function() { return !!targetHandle && !!targetName; },
      isApplying: function() { return applying; },
      hasPortableImport: function() { return importedSourceProfile !== null; },
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
    classifyFailure: classifyFailure,
    validateProjectText: validateProjectText,
    loadWorkspaceWithProfile: loadWorkspaceWithProfile,
    createBrowserTransport: createBrowserTransport,
    createManager: createManager
  };
});
