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

  function isCancellation(error) {
    var message = String(error && error.message || error || '');
    return !!(error && error.name === 'AbortError') || message.indexOf('open cancelled') >= 0;
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
      if (isCancellation(error)) {
        fileState(name === 'open' ? 'Ouverture annulée' : 'Enregistrement annulé', false);
        return null;
      }
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
    var projectFileMode = manager.nativeFileSystemAccess ? 'native' : 'fallback';
    document.body.dataset.projectFileMode = projectFileMode;
    window.dispatchEvent(new CustomEvent('webeeblocks-project-files-ready', {
      detail: {nativeFileSystemAccess: manager.nativeFileSystemAccess, mode: projectFileMode}
    }));

    if (!manager.nativeFileSystemAccess)
      fileState('Mode compatible : Enregistrer crée une nouvelle copie', false);

    document.getElementById('projectOpen').addEventListener('click', function() {
      operation('open', async function() {
        var result = await manager.open();
        runtimeTerminal = false;
        fileState('Projet : ' + result.name, false);
        if (runtimeBackend && runtimeBackend.ready) setRuntimeStatus('PRÊT', 'Projet ouvert');
      });
    });

    document.getElementById('projectSaveAs').addEventListener('click', function() {
      operation('save-as', async function() {
        var result = await manager.saveAs(suggestedName());
        fileState(result.mode === 'download-copy'
          ? 'Nouvelle copie proposée au téléchargement : ' + result.name
          : 'Projet : ' + result.name, false);
      });
    });

    document.getElementById('projectSave').addEventListener('click', function() {
      operation('save', async function() {
        var result = await manager.save();
        if (result) fileState(result.mode === 'download-copy'
          ? 'Nouvelle copie proposée au téléchargement : ' + result.name
          : 'Projet : ' + result.name, false);
      });
    });
  });
})();
