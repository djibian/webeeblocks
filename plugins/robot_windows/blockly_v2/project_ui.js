(function() {
  'use strict';

  var manager = null;
  var busy = false;
  var supported = false;
  var runtimeLocked = false;
  var handlersWired = false;
  var brokerFallbackAllowed = false;
  var brokerProbeStarted = false;

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
    return !!error && (error.name === 'AbortError' || error.code === 20);
  }

  function renderButtons() {
    var open = document.getElementById('projectOpen');
    var save = document.getElementById('projectSave');
    var saveAs = document.getElementById('projectSaveAs');
    var locked = busy || !supported || runtimeLocked;
    if (open) open.disabled = locked;
    if (saveAs) saveAs.disabled = locked;
    if (save) save.disabled = locked || !manager || !manager.hasCurrentTarget();
  }

  function setRuntimeLocked(locked) {
    runtimeLocked = locked === true;
    var blocklyDiv = document.getElementById('blocklyDiv');
    if (blocklyDiv) blocklyDiv.inert = runtimeLocked;
    renderButtons();
  }

  async function operation(name, action) {
    if (busy || !supported || runtimeLocked) return null;
    busy = true;
    renderButtons();
    try { return await action(); }
    catch (error) {
      if (!isCancellation(error)) {
        diagnostic(name, error);
        fileState(name === 'open' ? 'Impossible d’ouvrir ce projet' : 'Impossible d’enregistrer ce projet', true);
      }
      return null;
    } finally {
      busy = false;
      renderButtons();
    }
  }

  function applyProfile(profile) {
    runtimeProfile = profile;
    document.getElementById('activityTitle').textContent = profile.brief.visible ? profile.brief.title : 'WebeeBlocks';
    document.getElementById('activityGoal').textContent = profile.brief.visible ? profile.brief.goal : '';
    if (!profileFieldOptions) throw new Error('activity field-option controller unavailable');
    profileFieldOptions.setProfile(profile, workspace);
    if (workspace && typeof workspace.updateToolbox === 'function') workspace.updateToolbox(buildToolbox(profile));
    profileFieldOptions.applyWorkspace(workspace);
    WebeeBlocksActivityContract.applyFieldBounds(profile, workspace);
  }

  function suggestedName() {
    var base = manager && manager.currentName() ? manager.currentName() : runtimeProfile.id;
    return WebeeBlocksProjectFiles.normalizeName(base);
  }

  function createManager(transport) {
    return WebeeBlocksProjectFiles.createManager({
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
  }

  function publishMode(mode, nativeFileSystemAccess) {
    document.body.dataset.projectFileMode = mode;
    window.dispatchEvent(new CustomEvent('webeeblocks-project-files-ready', {
      detail: {nativeFileSystemAccess: nativeFileSystemAccess === true, mode: mode}
    }));
  }

  function wireHandlers() {
    if (handlersWired) return;
    handlersWired = true;
    document.getElementById('projectOpen').addEventListener('click', function() {
      operation('open', async function() {
        var result = await manager.open();
        fileState('Projet : ' + result.name, false);
        if (runtimeBackend && runtimeBackend.ready) {
          if (runtimeTerminal) {
            document.getElementById('runtimeDetail').textContent = 'Projet ouvert — réinitialisez la simulation avant de relancer';
            updateRuntimeActions();
          } else {
            setRuntimeStatus('PRÊT', 'Projet ouvert');
          }
        }
      });
    });

    document.getElementById('projectSaveAs').addEventListener('click', function() {
      operation('save-as', async function() {
        var result = await manager.saveAs(suggestedName());
        fileState('Projet : ' + result.name, false);
      });
    });

    document.getElementById('projectSave').addEventListener('click', function() {
      operation('save', async function() {
        var result = await manager.save();
        fileState('Projet : ' + result.name, false);
      });
    });
  }

  function activateTransport(transport, mode, nativeFileSystemAccess) {
    manager = createManager(transport);
    window.WebeeBlocksProjectManager = manager;
    supported = true;
    publishMode(mode, nativeFileSystemAccess);
    fileState('Aucun fichier projet sélectionné', false);
    wireHandlers();
    renderButtons();
  }

  async function tryWwiBroker() {
    if (!brokerFallbackAllowed || brokerProbeStarted || supported || !robotWindow || typeof robotWindow.send !== 'function') return;
    brokerProbeStarted = true;
    try {
      var transport = WebeeBlocksFileBrokerTransport.create(robotWindow, {probeTimeoutMs: 2000});
      await transport.probe();
      activateTransport(transport, 'wwi-native-broker', false);
    } catch (error) {
      supported = false;
      publishMode('unavailable', false);
      fileState('Gestion native des fichiers projet indisponible — utilisez Google Chrome', true);
      renderButtons();
    }
  }

  window.addEventListener('webeeblocks-runtime-v2', function(event) {
    var state = event && event.detail ? event.detail.state : null;
    setRuntimeLocked(state === 'EN VOL' || state === 'RÉINITIALISATION');
    if (brokerFallbackAllowed && !supported) tryWwiBroker();
  });

  window.addEventListener('load', function() {
    if (!workspace || !runtimeProfile) {
      fileState('Fichiers projet indisponibles', true);
      renderButtons();
      return;
    }

    var browserTransport = WebeeBlocksProjectFiles.createBrowserTransport(window, document);
    if (browserTransport.nativeFileSystemAccess) {
      activateTransport(browserTransport, 'browser-native', true);
      return;
    }

    brokerFallbackAllowed = true;
    publishMode('probing-native-broker', false);
    fileState('Recherche du gestionnaire natif de fichiers…', false);
    renderButtons();
    tryWwiBroker();
  });
})();
