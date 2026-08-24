(function() {
  'use strict';

  var manager = null;
  var busy = false;

  function fileState(text, error) {
    var target = document.getElementById('projectFileState');
    if (target) {
      target.textContent = text;
      target.dataset.error = error ? 'true' : 'false';
    }
  }

  function diagnostic(operation, error) {
    console.error('WebeeBlocks project ' + operation + ' failed', error);
    window.dispatchEvent(new CustomEvent('webeeblocks-project-file-diagnostic', {
      detail: {
        operation: operation,
        technicalMessage: error && error.message ? error.message : String(error)
      }
    }));
  }

  function setButtonsDisabled(disabled) {
    ['projectOpen', 'projectSave', 'projectSaveAs'].forEach(function(id) {
      var button = document.getElementById(id);
      if (button) button.disabled = disabled;
    });
  }

  async function operation(name, action) {
    if (busy) return;
    busy = true;
    setButtonsDisabled(true);
    try { return await action(); }
    catch (error) {
      diagnostic(name, error);
      fileState(name === 'open' ? 'Impossible d’ouvrir ce projet' : 'Impossible d’enregistrer ce projet', true);
      return null;
    } finally {
      busy = false;
      setButtonsDisabled(false);
    }
  }

  function applyProfile(profile) {
    runtimeProfile = profile;
    document.getElementById('activityTitle').textContent = profile.brief.visible ? profile.brief.title : 'WebeeBlocks';
    document.getElementById('activityGoal').textContent = profile.brief.visible ? profile.brief.goal : '';
    if (workspace && typeof workspace.updateToolbox === 'function') workspace.updateToolbox(buildToolbox(profile));
    WebeeBlocksActivityContract.applyFieldBounds(profile, workspace);
  }

  function suggestedName() {
    return manager && manager.currentName() ? manager.currentName() : runtimeProfile.id + WebeeBlocksProjectFiles.EXTENSION;
  }

  function promptName() {
    var existing = suggestedName();
    var base = existing.endsWith(WebeeBlocksProjectFiles.EXTENSION) ? existing.slice(0, -WebeeBlocksProjectFiles.EXTENSION.length) : existing;
    var chosen = window.prompt('Nom du projet', base);
    return chosen === null ? null : WebeeBlocksProjectFiles.normalizeName(chosen);
  }

  window.addEventListener('load', function() {
    if (!workspace || !runtimeProfile) {
      fileState('Fichiers projet indisponibles', true);
      return;
    }

    var transport = WebeeBlocksProjectFiles.createBrowserTransport(window, document);
    manager = WebeeBlocksProjectFiles.createManager({
      Blockly: Blockly,
      profiles: WebeeBlocksActivityProfiles,
      activitiesDocument: WebeeBlocksActivities.DOCUMENT,
      blockCatalog: WebeeBlocksActivities.BLOCK_CATALOG,
      semanticAst: WebeeBlocksSemanticAst,
      activityContract: WebeeBlocksActivityContract,
      workspace: workspace,
      getProfile: function() { return runtimeProfile; },
      setProfile: applyProfile,
      transport: transport
    });
    window.WebeeBlocksProjectManager = manager;
    document.body.dataset.projectFileMode = manager.nativeFileSystemAccess ? 'native' : 'upload-download';
    window.dispatchEvent(new CustomEvent('webeeblocks-project-files-ready', {
      detail: {nativeFileSystemAccess: manager.nativeFileSystemAccess}
    }));

    document.getElementById('projectOpen').addEventListener('click', function() {
      operation('open', async function() {
        var result = await manager.open();
        runtimeTerminal = false;
        fileState('Projet : ' + result.name, false);
        if (runtimeBackend && runtimeBackend.ready) setRuntimeStatus('PRÊT', 'Projet ouvert');
      });
    });

    document.getElementById('projectSaveAs').addEventListener('click', function() {
      var name = manager.nativeFileSystemAccess ? suggestedName() : promptName();
      if (name === null) return;
      operation('save-as', async function() {
        var result = await manager.saveAs(name);
        fileState('Projet : ' + result.name, false);
      });
    });

    document.getElementById('projectSave').addEventListener('click', function() {
      operation('save', async function() {
        var result;
        if (!manager.currentName() && !manager.nativeFileSystemAccess) {
          var name = promptName();
          if (name === null) return;
          result = await manager.saveAs(name);
        } else {
          result = await manager.save();
        }
        if (result) fileState('Projet : ' + result.name, false);
      });
    });
  });
})();
