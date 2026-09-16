(function() {
  'use strict';

  var manager = null;
  var busy = false;
  var supported = false;
  var runtimeLocked = false;
  var brokerTransport = null;
  var activityCatalog = null;
  var activityLoading = false;
  var progressionRoot = 'vendor/classroom-activities/progression/';

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
    var activity = document.getElementById('activityStarter');
    var start = document.getElementById('activityStart');
    var locked = busy || !supported || runtimeLocked;
    if (open) open.disabled = locked;
    if (saveAs) saveAs.disabled = locked;
    if (save) save.disabled = locked || !manager || !manager.hasCurrentTarget();
    if (activity) activity.disabled = locked || activityLoading || !activityCatalog;
    if (start) start.disabled = locked || activityLoading || !activityCatalog || !activity || !activity.value;
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
        var message = name === 'open'
          ? 'Impossible d’ouvrir ce projet'
          : (name === 'activity' ? 'Impossible de démarrer cette activité' : 'Impossible d’enregistrer ce projet');
        fileState(message, true);
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

  function createTemplateTransport(baseTransport, text, name) {
    var pendingTemplate = true;
    return {
      nativeFileSystemAccess: !!baseTransport.nativeFileSystemAccess,
      mode: baseTransport.mode || 'native',
      async open() {
        if (pendingTemplate) {
          pendingTemplate = false;
          return {handle: null, name: name, text: text, mode: 'template'};
        }
        return baseTransport.open();
      },
      async saveAs(targetName, targetText) {
        return baseTransport.saveAs(targetName, targetText);
      },
      async save(target, targetName, targetText) {
        return baseTransport.save(target, targetName, targetText);
      },
      async release(target) {
        if (typeof baseTransport.release === 'function') return baseTransport.release(target);
      }
    };
  }

  function profileForActivity(activityId) {
    return WebeeBlocksActivityProfiles.resolveById(
      WebeeBlocksActivities.DOCUMENT,
      activityId,
      WebeeBlocksActivities.BLOCK_CATALOG
    );
  }

  function validateActivityCatalog(value) {
    if (!value || value.version !== 1 || !Array.isArray(value.starters) || !value.starters.length)
      throw new Error('invalid progression starter manifest');
    var files = Object.create(null);
    var ids = Object.create(null);
    return value.starters.map(function(entry) {
      if (!entry || typeof entry.file !== 'string' || typeof entry.activityId !== 'string')
        throw new Error('invalid progression starter entry');
      if (!/^\d{2}-[a-z0-9-]+\.wbb$/.test(entry.file))
        throw new Error('invalid progression starter filename: ' + entry.file);
      if (!/^progression-[a-z0-9-]+-v1$/.test(entry.activityId))
        throw new Error('invalid progression activity id: ' + entry.activityId);
      if (files[entry.file] || ids[entry.activityId])
        throw new Error('duplicate progression starter entry');
      files[entry.file] = true;
      ids[entry.activityId] = true;
      var profile = profileForActivity(entry.activityId);
      if (!profile.brief || profile.brief.visible !== true)
        throw new Error('progression starter has no visible activity brief: ' + entry.activityId);
      if (!runtimeProfile || profile.world !== runtimeProfile.world)
        throw new Error('progression starter is incompatible with the current Webots world: ' + entry.activityId);
      return {file: entry.file, activityId: entry.activityId, title: profile.brief.title};
    });
  }

  async function loadActivityCatalog() {
    var response = await fetch(new URL(progressionRoot + 'index.json', window.location.href).href, {cache: 'no-store'});
    if (response.status === 404) return null;
    if (!response.ok) throw new Error('progression starter manifest unavailable: HTTP ' + response.status);
    return validateActivityCatalog(await response.json());
  }

  function renderActivityCatalog(entries) {
    var shell = document.getElementById('activityStarterControls');
    var select = document.getElementById('activityStarter');
    var start = document.getElementById('activityStart');
    if (!shell || !select || !start) return;
    while (select.options.length > 1) select.remove(1);
    entries.forEach(function(entry) {
      var option = document.createElement('option');
      option.value = entry.file;
      option.textContent = entry.title;
      option.dataset.activityId = entry.activityId;
      select.appendChild(option);
    });
    shell.hidden = false;
    select.addEventListener('change', renderButtons);
    start.addEventListener('click', function() { startSelectedActivity(); });
    renderButtons();
  }

  async function startActivityTemplate(transport, text, name) {
    if (typeof text !== 'string' || !text.trim()) throw new Error('activity starter is empty');
    if (typeof name !== 'string' || !name.trim()) throw new Error('activity starter has no name');
    var nextManager = createManager(createTemplateTransport(transport, text, name));
    var result = await nextManager.open();
    manager = nextManager;
    window.WebeeBlocksProjectManager = manager;
    fileState('Activité chargée — utilisez Enregistrer sous pour conserver votre travail', false);
    if (runtimeBackend && runtimeBackend.ready) {
      if (runtimeTerminal) {
        document.getElementById('runtimeDetail').textContent = 'Activité chargée — réinitialisez la simulation avant de relancer';
        updateRuntimeActions();
      } else {
        setRuntimeStatus('PRÊT', 'Activité chargée');
      }
    }
    return result;
  }

  async function startSelectedActivity() {
    var select = document.getElementById('activityStarter');
    if (activityLoading || !activityCatalog || !select || !select.value) return null;
    var selected = activityCatalog.find(function(entry) { return entry.file === select.value; });
    if (!selected) return null;
    activityLoading = true;
    renderButtons();
    try {
      return await operation('activity', async function() {
        var response = await fetch(new URL(progressionRoot + selected.file, window.location.href).href, {cache: 'no-store'});
        if (!response.ok) throw new Error('activity starter unavailable: HTTP ' + response.status);
        var result = await startActivityTemplate(window.WebeeBlocksProjectTransport || projectTransport, await response.text(), selected.file);
        if (result) {
          select.value = '';
          window.dispatchEvent(new CustomEvent('webeeblocks-activity-started', {
            detail: {activityId: selected.activityId, starter: selected.file}
          }));
        }
        return result;
      });
    } finally {
      activityLoading = false;
      renderButtons();
    }
  }

  async function initializeActivityEntry() {
    try {
      var entries = await loadActivityCatalog();
      if (!entries) return;
      activityCatalog = entries;
      renderActivityCatalog(entries);
    } catch (error) {
      console.error('WebeeBlocks classroom progression starters unavailable', error);
      window.dispatchEvent(new CustomEvent('webeeblocks-activity-starter-diagnostic', {
        detail: {technicalMessage: error && error.message ? error.message : String(error)}
      }));
    }
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
    brokerTransport = new window.WebeeBlocksProjectFileWwiTransport(directRobotWindow, {timeoutMs: 5000});

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

      manager = createManager(transport);
      window.WebeeBlocksProjectManager = manager;
      window.WebeeBlocksProjectTransport = transport;
      supported = manager.nativeFileSystemAccess;
      document.body.dataset.projectFileMode = transport.mode || 'native';

      if (!supported) {
        fileState('Gestion des fichiers projet indisponible dans ce navigateur', true);
        renderButtons();
        return;
      }

      fileState('Aucun fichier projet sélectionné', false);
      bindProjectButtons();
      renderButtons();
      await initializeActivityEntry();
    })().catch(function(error) {
      diagnostic('initialisation', error);
      fileState('Gestion des fichiers projet indisponible dans ce navigateur', true);
      renderButtons();
    });
  });
})();
