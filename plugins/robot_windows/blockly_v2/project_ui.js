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
    var activity = document.getElementById('projectActivity');
    var open = document.getElementById('projectOpen');
    var save = document.getElementById('projectSave');
    var saveAs = document.getElementById('projectSaveAs');
    var locked = busy || !supported || runtimeLocked;
    if (activity) activity.disabled = locked;
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
        fileState((name === 'open' || name === 'activity') ? 'Impossible d’ouvrir ce projet' : 'Impossible d’enregistrer ce projet', true);
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
      browserTransport.mode = 'browser-native';
      return browserTransport;
    }

    await import('../blockly/webeeblocks/project_file_wwi_transport.js?rev=20260912-2');
    if (typeof window.WebeeBlocksProjectFileWwiTransport !== 'function')
      throw new Error('Project file WWI transport module unavailable');
    var directRobotWindow = await waitForRobotWindow(5000);
    if (typeof runtimeBackend === 'undefined' || !runtimeBackend || typeof runtimeBackend.waitUntilReady !== 'function')
      throw new Error('Runtime v2 backend unavailable for project files');

    // The Qt file broker lives in the controller receive loop. Waiting for the
    // Runtime handshake prevents an automatically opened Firefox window from
    // spending its short broker readiness budget before that loop is live.
    await runtimeBackend.waitUntilReady();
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

  function markProjectChanged(detail) {
    if (runtimeBackend && runtimeBackend.ready) {
      if (runtimeTerminal) {
        document.getElementById('runtimeDetail').textContent = detail + ' — réinitialisez la simulation avant de relancer';
        updateRuntimeActions();
      } else {
        setRuntimeStatus('PRÊT', detail);
      }
    }
  }

  function progressionProfiles() {
    var documentModel = WebeeBlocksActivities && WebeeBlocksActivities.DOCUMENT;
    var activities = documentModel && Array.isArray(documentModel.activities) ? documentModel.activities : [];
    var profiles = activities.filter(function(profile) {
      return profile && typeof profile.id === 'string' && profile.id.indexOf('progression-') === 0;
    });
    if (!profiles.length) throw new Error('aucune activité de progression disponible');
    return profiles;
  }

  function chooseActivityProfile() {
    return new Promise(function(resolve, reject) {
      if (typeof HTMLDialogElement === 'undefined') {
        reject(new Error('sélecteur d’activité indisponible dans ce navigateur'));
        return;
      }

      var profiles;
      try { profiles = progressionProfiles(); }
      catch (error) { reject(error); return; }

      var dialog = document.createElement('dialog');
      dialog.id = 'activityChooser';
      dialog.setAttribute('aria-labelledby', 'activityChooserTitle');
      dialog.style.maxWidth = 'min(560px, calc(100vw - 32px))';
      dialog.style.border = '1px solid #c8d2dd';
      dialog.style.borderRadius = '12px';
      dialog.style.padding = '18px';

      var title = document.createElement('h2');
      title.id = 'activityChooserTitle';
      title.textContent = 'Démarrer une activité';
      title.style.margin = '0 0 8px';
      title.style.fontSize = '19px';
      dialog.appendChild(title);

      var introduction = document.createElement('p');
      introduction.textContent = 'Choisis l’activité à commencer. Ton travail devra ensuite être enregistré avec Enregistrer sous.';
      introduction.style.marginBottom = '14px';
      dialog.appendChild(introduction);

      var list = document.createElement('div');
      list.setAttribute('role', 'list');
      list.style.display = 'grid';
      list.style.gap = '7px';
      profiles.forEach(function(profile) {
        var button = document.createElement('button');
        button.type = 'button';
        button.setAttribute('role', 'listitem');
        button.textContent = profile.brief && profile.brief.title ? profile.brief.title : profile.id;
        button.style.textAlign = 'left';
        button.addEventListener('click', function() { finish(profile); });
        list.appendChild(button);
      });
      dialog.appendChild(list);

      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.textContent = 'Annuler';
      cancel.style.marginTop = '14px';
      cancel.addEventListener('click', function() { finish(null); });
      dialog.appendChild(cancel);

      var settled = false;
      function finish(profile) {
        if (settled) return;
        settled = true;
        if (dialog.open) dialog.close();
        dialog.remove();
        resolve(profile);
      }
      dialog.addEventListener('cancel', function(event) {
        event.preventDefault();
        finish(null);
      });

      document.body.appendChild(dialog);
      dialog.showModal();
    });
  }

  function bindProjectButtons() {
    document.getElementById('projectActivity').addEventListener('click', function() {
      operation('activity', async function() {
        var profile = await chooseActivityProfile();
        if (!profile) return null;
        var starterName = profile.id + '.wbb';
        var starterText = WebeeBlocksProjectFiles.createStarterText(profile.id);
        var result = await manager.openTemplateText(starterName, starterText);
        fileState('Activité : ' + profile.brief.title + ' — utilisez Enregistrer sous pour votre travail', false);
        markProjectChanged('Activité démarrée');
        return result;
      });
    });

    // `manager.openTemplate()` remains the explicit external-template API used
    // by compatibility/tests. The Start activity action above deliberately uses
    // embedded starter bytes so it never opens the generic OS project picker.
    document.getElementById('projectOpen').addEventListener('click', function() {
      operation('open', async function() {
        var result = await manager.open();
        fileState('Projet : ' + result.name, false);
        markProjectChanged('Projet ouvert');
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
