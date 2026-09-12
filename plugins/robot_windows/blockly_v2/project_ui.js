(function() {
  'use strict';

  var manager = null;
  var busy = false;
  var supported = false;
  var runtimeLocked = false;
  var brokerTransport = null;

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

  function waitForRobotWindow(timeoutMs) {
    return new Promise(function(resolve, reject) {
      var deadline = Date.now() + timeoutMs;
      function poll() {
        if (typeof robotWindow !== 'undefined' && robotWindow && typeof robotWindow.send === 'function' && typeof robotWindow.receive === 'function') {
          resolve(robotWindow);
          return;
        }
        if (Date.now() >= deadline) {
          reject(new Error('Robot Window transport unavailable for project files'));
          return;
        }
        setTimeout(poll, 25);
      }
      poll();
    });
  }

  async function createDirectTransport() {
    var browserTransport = WebeeBlocksProjectFiles.createBrowserTransport(window, document);
    if (browserTransport.nativeFileSystemAccess) {
      browserTransport.mode = 'native';
      return browserTransport;
    }

    await import('../blockly/webeeblocks/project_file_wwi_transport.js');
    if (typeof window.WebeeBlocksProjectFileWwiTransport !== 'function')
      throw new Error('Project file WWI transport module unavailable');
    var directRobotWindow = await waitForRobotWindow(5000);
    brokerTransport = new window.WebeeBlocksProjectFileWwiTransport(directRobotWindow, {timeoutMs: 5000});

    // RobotWindow has one receive callback. Runtime v2 keeps ownership of the
    // existing handler; the broker consumes only its own prefixed responses and
    // forwards every other message unchanged.
    var runtimeReceive = directRobotWindow.receive;
    directRobotWindow.receive = function(value) {
      if (brokerTransport && brokerTransport.handleMessage(value)) {
        window.dispatchEvent(new CustomEvent('webeeblocks-wwi', {detail: value}));
        return;
      }
      return runtimeReceive.call(directRobotWindow, value);
    };
    await brokerTransport.waitUntilReady();
    window.WebeeBlocksProjectTransport = brokerTransport;
    return brokerTransport;
  }

  function bindProjectButtons() {
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

  window.addEventListener('webeeblocks-runtime-v2', function(event) {
    var state = event && event.detail ? event.detail.state : null;
    setRuntimeLocked(state === 'EN VOL' || state === 'RÉINITIALISATION');
  });

  window.addEventListener('load', function() {
    (async function() {
      if (!workspace || !runtimeProfile) {
        fileState('Fichiers projet indisponibles', true);
        renderButtons();
        return;
      }

      var transport;
      try {
        transport = await createDirectTransport();
      } catch (error) {
        diagnostic('initialisation', error);
        fileState('Gestion des fichiers projet indisponible dans ce navigateur', true);
        document.body.dataset.projectFileMode = 'unavailable';
        renderButtons();
        return;
      }

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
      supported = manager.nativeFileSystemAccess;
      document.body.dataset.projectFileMode = transport.mode || 'native';
      window.dispatchEvent(new CustomEvent('webeeblocks-project-files-ready', {
        detail: {nativeFileSystemAccess: supported, mode: document.body.dataset.projectFileMode}
      }));

      if (!supported) {
        fileState('Gestion des fichiers projet indisponible dans ce navigateur', true);
        renderButtons();
        return;
      }

      fileState('Aucun fichier projet sélectionné', false);
      bindProjectButtons();
      renderButtons();
    })().catch(function(error) {
      diagnostic('initialisation', error);
      fileState('Gestion des fichiers projet indisponible dans ce navigateur', true);
      renderButtons();
    });
  });
})();
