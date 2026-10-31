var runtimeProfile = null;
var profileFieldOptions = null;
var workspace = null;
var robotWindow = null;
var runtimeBackend = null;
var runtimeRunning = false;
var runtimeTerminal = false;
// The interpreter can finish before the live-world evaluator settles.
var runtimeOutcomePending = false;
var runtimeResetPending = false;
var runtimeStopPending = false;
var runtimeStopRequested = false;
var runtimeScenePending = false;
var runtimeProjectPending = false;
var runtimeRecoveryPending = false;
var runtimeNeedsRebuild = false;
var runtimeDebug = null;
var WEBEEBLOCKS_MAIN_SCRIPT_URL = document.currentScript && document.currentScript.src;

var WEBEEBLOCKS_WORKSPACE_SCALE = 0.90;
var WEBEEBLOCKS_CREATE_VARIABLE_CALLBACK = 'WEBEEBLOCKS_CREATE_VARIABLE';

var WebeeBlocksStudentTheme = Blockly.Theme.defineTheme('webeeblocksStudent', {
  base: Blockly.Themes.Classic,
  blockStyles: {
    flight_blocks: { colourPrimary: '#2563EB', colourSecondary: '#1D4ED8', colourTertiary: '#1E40AF' },
    control_blocks: { colourPrimary: '#7C3AED', colourSecondary: '#6D28D9', colourTertiary: '#5B21B6' },
    sensor_blocks: { colourPrimary: '#0E7490', colourSecondary: '#0F5F73', colourTertiary: '#164E63' },
    operator_blocks: { colourPrimary: '#047857', colourSecondary: '#046C4E', colourTertiary: '#065F46' },
    variable_blocks: { colourPrimary: '#B45309', colourSecondary: '#92400E', colourTertiary: '#78350F' },
    logic_blocks: { colourPrimary: '#7C3AED', colourSecondary: '#6D28D9', colourTertiary: '#5B21B6' },
    loop_blocks: { colourPrimary: '#7C3AED', colourSecondary: '#6D28D9', colourTertiary: '#5B21B6' },
    math_blocks: { colourPrimary: '#047857', colourSecondary: '#046C4E', colourTertiary: '#065F46' },
    procedure_blocks: { colourPrimary: '#A21CAF', colourSecondary: '#86198F', colourTertiary: '#701A75' }
  },
  categoryStyles: {
    flight_category: {colour: '#2563EB'},
    control_category: {colour: '#7C3AED'},
    sensor_category: {colour: '#0E7490'},
    operator_category: {colour: '#047857'},
    variable_category: {colour: '#B45309'},
    procedure_category: {colour: '#A21CAF'}
  },
  componentStyles: {
    workspaceBackgroundColour: '#f7f9fc', toolboxBackgroundColour: '#ffffff', toolboxForegroundColour: '#263342',
    flyoutBackgroundColour: '#eef2f7', flyoutForegroundColour: '#263342', flyoutOpacity: 1,
    scrollbarColour: '#9aa7b5', scrollbarOpacity: 0.55, insertionMarkerColour: '#167f91', insertionMarkerOpacity: 0.35,
    cursorColour: '#167f91', selectedGlowColour: '#167f91', selectedGlowOpacity: 0.18,
    replacementGlowColour: '#167f91', replacementGlowOpacity: 0.18
  },
  fontStyle: { family: 'Inter, Aptos, Segoe UI, Arial, sans-serif', weight: '600', size: 12 },
  startHats: false
});

function updateRuntimeActions() {
  var ready = !!(runtimeBackend && runtimeBackend.ready && runtimeBackend.authorized);
  var submit = document.getElementById('submit');
  var reset = document.getElementById('resetSimulation');
  if (reset) reset.textContent = runtimeNeedsRebuild ? 'Reconstruire' : 'Réinitialiser';
  var stop = document.getElementById('stopSimulation');
  var stopSupported = !!(runtimeBackend && runtimeBackend.capabilities && runtimeBackend.capabilities.simulationStop === true);
  var primaryIsStop = runtimeRunning === true || runtimeOutcomePending === true;
  var primaryLabel = primaryIsStop ? 'Arrêter le vol' : 'Lancer le vol';
  submit.textContent = primaryLabel;
  if (typeof submit.setAttribute === 'function') submit.setAttribute('aria-label', primaryLabel);
  submit.disabled = primaryIsStop
    ? (!stopSupported || !ready || runtimeOutcomePending || runtimeStopPending || runtimeStopRequested)
    : (!ready || runtimeTerminal || runtimeOutcomePending || runtimeResetPending || runtimeStopPending || runtimeScenePending || runtimeProjectPending || runtimeRecoveryPending);
  if (stop) {
    stop.hidden = true;
    stop.disabled = true;
  }
  if (reset) {
    var resetSupported = !!(runtimeBackend && runtimeBackend.capabilities && runtimeBackend.capabilities.simulationReset === true);
    reset.hidden = !resetSupported;
    reset.disabled = !resetSupported || !ready || runtimeRunning || runtimeOutcomePending || runtimeResetPending || runtimeStopPending || runtimeScenePending || runtimeProjectPending || runtimeRecoveryPending || !runtimeTerminal;
  }
}

function setRuntimeStatus(state, detail) {
  document.getElementById('runtimeState').textContent = state;
  document.getElementById('runtimeDetail').textContent = detail || '';
  document.body.dataset.runtimeState = state;
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2', { detail: {state: state, detail: detail || null} }));
  updateRuntimeActions();
}

function setRuntimeFailure(error, missionOutcome) {
  var outcome = WebeeBlocksRuntimeOutcome.classify(error);
  var presentation = missionOutcome || outcome;
  console.error(error);
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-diagnostic', {
    detail: {
      studentState: presentation.state,
      machineCode: outcome.machineCode,
      technicalMessage: error && error.message ? error.message : String(error)
    }
  }));
  setRuntimeStatus(presentation.state, presentation.detail);
}

function categoryLabel(category) {
  if (category === 'flight') return 'Vol';
  if (category === 'control') return 'Contrôle';
  if (category === 'sensor') return 'Capteurs';
  if (category === 'operator') return 'Opérateurs';
  if (category === 'variable') return 'Variables';
  if (category === 'procedure') return 'Procédures';
  throw new Error('unknown toolbox category: ' + category);
}
function categoryStyle(category) {
  if (category === 'flight') return 'flight_category';
  if (category === 'control') return 'control_category';
  if (category === 'sensor') return 'sensor_category';
  if (category === 'operator') return 'operator_category';
  if (category === 'variable') return 'variable_category';
  if (category === 'procedure') return 'procedure_category';
  throw new Error('unknown toolbox category: ' + category);
}
function overrideBuiltinBlockStyle(type, style) {
  var definition = Blockly.Blocks[type];
  if (!definition || typeof definition.init !== 'function') throw new Error('cannot style unknown Blockly block: ' + type);
  var originalInit = definition.init;
  definition.init = function() { originalInit.call(this); this.setStyle(style); };
}
function applySemanticBuiltinStyles() {
  overrideBuiltinBlockStyle('logic_compare', 'operator_blocks');
  overrideBuiltinBlockStyle('logic_operation', 'operator_blocks');
  overrideBuiltinBlockStyle('math_number', 'operator_blocks');
  overrideBuiltinBlockStyle('math_arithmetic', 'operator_blocks');
  overrideBuiltinBlockStyle('math_change', 'variable_blocks');
  overrideBuiltinBlockStyle('variables_set', 'variable_blocks');
  overrideBuiltinBlockStyle('variables_get', 'variable_blocks');
}

function buildToolbox(profile) {
  var toolbox = document.createElement('xml');
  var groups = {flight: [], control: [], sensor: [], operator: [], variable: [], procedure: []};
  profile.toolbox.forEach(function(type) {
    var definition = WebeeBlocksActivities.BLOCK_CATALOG[type];
    var category = (definition && definition.category) || 'control';
    if (!Object.prototype.hasOwnProperty.call(groups, category)) throw new Error('unsupported toolbox category for ' + type + ': ' + category);
    groups[category].push(type);
  });
  ['flight', 'control', 'sensor', 'operator', 'variable', 'procedure'].forEach(function(category) {
    if (!groups[category].length) return;
    var categoryNode = document.createElement('category');
    categoryNode.setAttribute('name', categoryLabel(category));
    categoryNode.setAttribute('categorystyle', categoryStyle(category));
    if (category === 'procedure') {
      categoryNode.setAttribute('custom', 'WEBEEBLOCKS_PROCEDURES');
      toolbox.appendChild(categoryNode);
      return;
    }
    if (category === 'variable') {
      var createButton = document.createElement('button');
      createButton.setAttribute('text', 'Créer une variable…');
      createButton.setAttribute('callbackKey', WEBEEBLOCKS_CREATE_VARIABLE_CALLBACK);
      categoryNode.appendChild(createButton);
    }
    groups[category].forEach(function(type) {
      var block = document.createElement('block'); block.setAttribute('type', type);
      if (type === 'controls_repeat_ext') {
        var value = document.createElement('value'); value.setAttribute('name', 'TIMES');
        var shadow = document.createElement('shadow'); shadow.setAttribute('type', 'math_number');
        var field = document.createElement('field'); field.setAttribute('name', 'NUM'); field.textContent = '3';
        shadow.appendChild(field); value.appendChild(shadow); block.appendChild(value);
      }
      categoryNode.appendChild(block);
    });
    toolbox.appendChild(categoryNode);
  });
  return toolbox;
}

function receiveMessage(value) {
  if (value === 'WEBEEBLOCKS_RUNTIME_V2 WORLD_RELOAD_DENIED') {
    runtimeTerminal = true;
    runtimeRecoveryPending = true;
    runtimeNeedsRebuild = true;
    setRuntimeFailure(new Error('Le témoin natif n’a pas pu être enregistré : reconstruction refusée'));
    document.getElementById('runtimeDetail').textContent =
      'Reconstruction refusée : impossible de protéger le programme hors du navigateur. Exécution verrouillée.';
    return;
  }
  if (runtimeBackend && runtimeBackend.handleMessage(value)) {
    window.dispatchEvent(new CustomEvent('webeeblocks-wwi', {detail: value}));
    return;
  }
  console.log('Unhandled Robot Window message:', value);
}

function setDebugControls(paused) {
  document.getElementById('stepNext').disabled = !paused;
  document.getElementById('stepContinue').disabled = !paused;
  document.getElementById('stepMode').disabled = runtimeRunning || runtimeResetPending;
}
function studentDirectionLabel(direction) {
  var labels = {front: 'devant', back: 'derrière', left: 'à gauche', right: 'à droite', up: 'au-dessus'};
  if (!Object.prototype.hasOwnProperty.call(labels, direction)) throw new Error('unsupported student direction: ' + direction);
  return labels[direction];
}
function renderSensorValues(values) {
  var keys = Object.keys(values || {});
  document.getElementById('debugSensors').textContent = keys.length ? keys.map(function(direction) {
    return studentDirectionLabel(direction) + ' = ' + String(values[direction]) + ' m';
  }).join(' · ') : '—';
}
function renderVariables(values) {
  var row = document.getElementById('debugVariablesRow');
  var target = document.getElementById('debugVariables');
  var keys = values ? Object.keys(values) : [];
  row.hidden = keys.length === 0;
  target.textContent = keys.map(function(name) { return name + ' = ' + String(values[name]); }).join(' · ');
}
function wireDebugControls() {
  runtimeDebug = WebeeBlocksExecutionObserver.create(workspace, {
    onBegin: function(detail) {
      document.getElementById('debugState').textContent = detail.enabled ? 'Pas à pas actif' : 'Observation inactive';
      renderSensorValues({}); renderVariables(null); setDebugControls(false);
    },
    onActive: function(detail) {
      var block = detail.blockId ? workspace.getBlockById(detail.blockId) : null;
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-active', { detail: {
        path: detail.path, kind: detail.node && detail.node.kind, blockId: detail.blockId, blockType: block ? block.type : null
      }}));
    },
    onPause: function(detail) {
      document.getElementById('debugState').textContent = 'En pause'; setDebugControls(true);
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-paused', {detail: detail}));
    },
    onResume: function(detail) {
      document.getElementById('debugState').textContent = 'Exécution'; setDebugControls(false);
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-resumed', {detail: detail}));
    },
    onSensor: function(detail) {
      renderSensorValues(detail.values);
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-sensor', { detail: {
        path: detail.path, blockId: detail.blockId, direction: detail.direction, value: detail.value
      }}));
    },
    onVariables: function(detail) { renderVariables(detail.values); },
    onFinish: function() { document.getElementById('debugState').textContent = 'Observation terminée'; setDebugControls(false); }
  });
  document.getElementById('stepNext').addEventListener('click', function() { runtimeDebug.next(); });
  document.getElementById('stepContinue').addEventListener('click', function() { runtimeDebug.continueRun(); });
}

function userStoppedError() {
  var error = new Error('Runtime v2 simulation stopped by user');
  error.code = 'USER_STOPPED';
  return error;
}

function serializedWorkspace() {
  if (!workspace || !Blockly.serialization || !Blockly.serialization.workspaces)
    throw new Error('Blockly workspace serialization unavailable');
  return JSON.stringify(Blockly.serialization.workspaces.save(workspace));
}

async function stopSimulation() {
  if (!runtimeRunning || runtimeStopPending || !runtimeBackend || !runtimeBackend.ready)
    return;
  if (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationStop !== true)
    return;
  runtimeStopPending = true;
  runtimeStopRequested = true;
  updateRuntimeActions();
  setDebugControls(false);
  if (runtimeDebug) runtimeDebug.continueRun();
  try {
    await runtimeBackend.stopSimulation();
    runtimeTerminal = true;
    setRuntimeFailure(userStoppedError());
  } catch (error) {
    runtimeTerminal = true;
    setRuntimeFailure(error);
  } finally {
    runtimeStopPending = false;
    updateRuntimeActions();
  }
}

async function rebuildSimulation() {
  if (runtimeRunning || runtimeOutcomePending || runtimeResetPending || runtimeRecoveryPending ||
      !runtimeTerminal || !runtimeBackend || !runtimeBackend.ready ||
      !runtimeBackend.capabilities || runtimeBackend.capabilities.simulationWorldReload !== true)
    return;
  // Block the old tab immediately, including while acquiring the shared Web
  // Lock. Producing two checkpoints is more dangerous than a refused retry.
  runtimeRecoveryPending = true;
  runtimeTerminal = true;
  setDebugControls(false);
  if (runtimeDebug) runtimeDebug.finish();
  setRuntimeStatus('RECONSTRUCTION', 'Protection du programme avant reconstruction');
  try {
    if (!window.WebeeBlocksWindowRenewal)
      throw new Error('Verrou de reprise indisponible — reconstruction refusée');
    await window.WebeeBlocksWindowRenewal.withRecoveryLock(async function() {
      if (!runtimeBackend || !runtimeBackend.ready || !runtimeProfile || !workspace)
        throw new Error('Ancien document de reconstruction non autorisé');
      var profileId = runtimeProfile.id;
      var original = serializedWorkspace();
      // Crypto runs inside the lock; an unavailable primitive must not create
      // an unbound checkpoint or arm a native world reload.
      var digest = await WebeeBlocksSimulationRecovery.fingerprint(profileId, original);
      if (runtimeProfile.id !== profileId || serializedWorkspace() !== original)
        throw new Error('Programme modifié pendant la préparation du témoin');
      // Absence check + write + arm + irreversible native request are one
      // critical section. save() refuses even a malformed existing record.
      var checkpoint = WebeeBlocksSimulationRecovery.save(
        profileId, original, runtimeBackend.nextId, digest);
      if (!window.WebeeBlocksWindowRenewal.arm(checkpoint.token))
        throw new Error('Impossible de préparer le renouvellement de la fenêtre Blockly');
      // window.name belongs to this browsing context, unlike origin-wide
      // localStorage or clonable sessionStorage. It is cleared synchronously
      // by the successor before opening any WebSocket. A new popup has its
      // own name, and must not inherit the old native authority.
      window.name = 'webeeblocks-r3-handoff:' + runtimeBackend.authorityHandoff();
      runtimeBackend.requestWorldReload(checkpoint.token, digest);
      window.WebeeBlocksWindowRenewal.begin();
    });
    // Never declare the old incarnation ready after requesting world reload.
  } catch (error) {
    // Handoff may already be written while arm/reload/navigation fails.
    // Keep the durable checkpoint untouched; discard the no-longer-needed
    // document-name capability immediately for every controlled failure.
    if (window.name.startsWith('webeeblocks-r3-handoff:')) window.name = '';
    window.WebeeBlocksWindowRenewal && window.WebeeBlocksWindowRenewal.disarm();
    runtimeTerminal = true;
    runtimeRecoveryPending = true; // Preserve checkpoint/witness; fail closed.
    runtimeNeedsRebuild = true;
    setRuntimeFailure(error);
    updateRuntimeActions();
  }
}

async function resetSimulation() {
  if (runtimeRunning || runtimeOutcomePending || runtimeResetPending || runtimeRecoveryPending || !runtimeTerminal || !runtimeBackend || !runtimeBackend.ready)
    return;
  if (runtimeNeedsRebuild) return rebuildSimulation();
  if (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationReset !== true) {
    setRuntimeFailure(new Error('Simulation reset unavailable'));
    return;
  }
  var before = serializedWorkspace();
  var profile = runtimeProfile;
  runtimeResetPending = true;
  updateRuntimeActions();
  setDebugControls(false);
  setRuntimeStatus('RÉINITIALISATION', 'Retour à l’état initial de la simulation');
  try {
    await runtimeBackend.resetSimulation();
    var after = serializedWorkspace();
    if (after !== before)
      throw new Error('Simulation reset changed Blockly workspace');
    if (runtimeProfile !== profile)
      throw new Error('Simulation reset changed activity profile');
    runtimeTerminal = false;
    runtimeNeedsRebuild = false;
    runtimeStopRequested = false;
    renderSensorValues({});
    renderVariables(null);
    if (runtimeDebug) runtimeDebug.finish();
    document.getElementById('debugState').textContent = 'Observation inactive';
    setRuntimeStatus('PRÊT', 'Simulation réinitialisée');
    window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-reset', {detail: {workspacePreserved: true}}));
  } catch (error) {
    runtimeTerminal = true;
    runtimeNeedsRebuild = true; // No second superficial RESET after an unknown physical failure.
    setRuntimeFailure(error);
  } finally {
    runtimeResetPending = false;
    setDebugControls(false);
    updateRuntimeActions();
  }
}

async function runProgram() {
  if (runtimeRunning || runtimeTerminal || runtimeOutcomePending || runtimeResetPending || runtimeStopPending || runtimeScenePending || runtimeProjectPending || runtimeRecoveryPending || !runtimeBackend || !runtimeBackend.ready) return;
  var submit = document.getElementById('submit');
  var stepMode = document.getElementById('stepMode');
  var debugRequested = stepMode.checked === true;
  if (debugRequested && (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationDebug !== true)) {
    setRuntimeFailure(new Error('Simulation step debug unavailable'));
    return;
  }
  submit.disabled = true;
  runtimeTerminal = false;
  runtimeStopRequested = false;
  var hooks = runtimeDebug ? runtimeDebug.begin(debugRequested) : null;
  try {
    await WebeeBlocksActivityContract.execute(runtimeProfile, workspace, WebeeBlocksSemanticAst, WebeeBlocksInterpreter, runtimeBackend, {
      maxSteps: runtimeProfile.runtime.maxSteps || 1000,
      hooks: hooks,
      onAst: function(ast) {
        window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-ast', {detail: ast}));
        runtimeRunning = true; setDebugControls(false); setRuntimeStatus('EN VOL', 'Programme réactif en cours');
      }
    });
    if (runtimeStopRequested) throw userStoppedError();
    runtimeRunning = false;
    runtimeTerminal = true;
    runtimeOutcomePending = true;
    updateRuntimeActions();
    var missionOutcome = await WebeeBlocksRuntimeOutcome.evaluateMission(runtimeProfile, runtimeBackend);
    if (missionOutcome)
      setRuntimeStatus(missionOutcome.state, missionOutcome.detail);
    else
      setRuntimeStatus('TERMINÉ', 'Programme exécuté');
  } catch (error) {
    runtimeRunning = false;
    runtimeTerminal = !WebeeBlocksRuntimeOutcome.isRetryable(error);
    runtimeOutcomePending = true;
    updateRuntimeActions();
    var missionFailure = runtimeStopRequested ? null :
      await WebeeBlocksRuntimeOutcome.readMissionFailure(runtimeProfile, runtimeBackend, error);
    setRuntimeFailure(error, missionFailure);
  } finally {
    runtimeOutcomePending = false;
    if (runtimeDebug) runtimeDebug.finish();
    stepMode.disabled = false;
    updateRuntimeActions();
  }
}

function activatePrimaryExecution() {
  return runtimeRunning ? stopSimulation() : runProgram();
}

function isPureVisualWorkspaceMove(event) {
  return !!(event && event.type === Blockly.Events.BLOCK_MOVE &&
    event.oldParentId == null && event.newParentId == null);
}
function onWorkspaceChange(event) {
  if (!event || event.type === Blockly.Events.UI || isPureVisualWorkspaceMove(event)) return;
  try {
    if (event.type === Blockly.Events.BLOCK_CREATE)
      profileFieldOptions.applyWorkspace(workspace);
    WebeeBlocksActivityContract.applyFieldBounds(runtimeProfile, workspace);
  } catch (error) { console.error(error); }
  if (!runtimeRunning && runtimeTerminal)
    document.getElementById('runtimeDetail').textContent = 'Programme modifié — réinitialisez la simulation avant de relancer';
}
function wireWorkspaceControls() {
  document.getElementById('zoomIn').addEventListener('click', function() { workspace.zoomCenter(1); });
  document.getElementById('zoomOut').addEventListener('click', function() { workspace.zoomCenter(-1); });
  document.getElementById('zoomFit').addEventListener('click', function() { workspace.zoomToFit(); });
  document.getElementById('zoomReset').addEventListener('click', function() {
    workspace.setScale(WEBEEBLOCKS_WORKSPACE_SCALE); if (typeof workspace.scrollCenter === 'function') workspace.scrollCenter();
  });
  document.getElementById('resetSimulation').addEventListener('click', resetSimulation);
  var legacyStop = document.getElementById('stopSimulation');
  if (legacyStop) legacyStop.addEventListener('click', stopSimulation);
}

window.onload = async function() {
  profileFieldOptions = WebeeBlocksActivityProfiles.createFieldOptionController(WebeeBlocksActivities.DOCUMENT, WebeeBlocksActivities.BLOCK_CATALOG, Blockly);
  runtimeProfile = WebeeBlocksActivityProfiles.resolveById(WebeeBlocksActivities.DOCUMENT, typeof WebeeBlocksInitialActivityId === 'string' ? WebeeBlocksInitialActivityId : 'reactive-obstacle-v2', WebeeBlocksActivities.BLOCK_CATALOG);
  profileFieldOptions.setProfile(runtimeProfile, null);
  document.getElementById('activityTitle').textContent = runtimeProfile.brief.title;
  document.getElementById('activityGoal').textContent = runtimeProfile.brief.goal;
  applySemanticBuiltinStyles();
  workspace = Blockly.inject('blocklyDiv', {
    toolbox: buildToolbox(runtimeProfile), renderer: 'zelos', theme: WebeeBlocksStudentTheme, scrollbars: true,
    move: {scrollbars: true, drag: true, wheel: true},
    zoom: {controls: false, wheel: true, startScale: WEBEEBLOCKS_WORKSPACE_SCALE, maxScale: 1.40, minScale: 0.55, scaleSpeed: 1.10, pinch: true},
    trashcan: true, media: 'vendor/media/', sounds: false
  });
  if (typeof workspace.registerButtonCallback !== 'function' || !Blockly.Variables || typeof Blockly.Variables.createVariableButtonHandler !== 'function')
    throw new Error('Blockly variable creation callback unavailable');
  workspace.registerButtonCallback(WEBEEBLOCKS_CREATE_VARIABLE_CALLBACK, function() {
    Blockly.Variables.createVariableButtonHandler(workspace);
  });
  if (typeof workspace.registerToolboxCategoryCallback === 'function') workspace.registerToolboxCategoryCallback('WEBEEBLOCKS_PROCEDURES', function(target) {
    // Retain Blockly's automatic naming/call updates, expose only this profile.
    return Blockly.Procedures.flyoutCategory(target).filter(function(item) {
      return runtimeProfile.toolbox.indexOf(item.type) >= 0;
    });
  });
  profileFieldOptions.applyWorkspace(workspace);
  // Liveness does not authorize running: every incarnation must obtain a
  // fresh nonce-correlated verdict from the native witness before unlocking.
  runtimeRecoveryPending = true;
  runtimeTerminal = true;
  updateRuntimeActions();
  var recovery = null;
  var authorityHandoff = null;
  try {
    if (window.name.startsWith('webeeblocks-r3-handoff:')) {
      authorityHandoff = window.name.slice('webeeblocks-r3-handoff:'.length);
      window.name = ''; // Single use, before any await/network/browser popup.
      if (!/^[0-9a-f]{64}$/.test(authorityHandoff))
        throw new Error('Invalid document-specific native authority handoff');
    }
    recovery = WebeeBlocksSimulationRecovery.peek();
    if (authorityHandoff && !recovery)
      throw new Error('Native handoff without Blockly checkpoint: fail closed');
    if (recovery) {
      runtimeRecoveryPending = true;
      runtimeTerminal = true;
      runtimeNeedsRebuild = true;
      runtimeProfile = WebeeBlocksActivityProfiles.resolveById(
        WebeeBlocksActivities.DOCUMENT, recovery.profileId, WebeeBlocksActivities.BLOCK_CATALOG);
      profileFieldOptions.setProfile(runtimeProfile, workspace);
      workspace.updateToolbox(buildToolbox(runtimeProfile));
      Blockly.serialization.workspaces.load(JSON.parse(recovery.workspace), workspace);
      if (serializedWorkspace() !== recovery.workspace)
        throw new Error('Recovery altered the unsaved Blockly program');
      document.getElementById('activityTitle').textContent = runtimeProfile.brief.title;
      document.getElementById('activityGoal').textContent = runtimeProfile.brief.goal;
      setRuntimeStatus('RECONSTRUCTION', 'Vérification du nouveau monde et de la scène');
    }
  } catch (error) {
    runtimeRecoveryPending = true;
    runtimeTerminal = true;
    setRuntimeFailure(error);
    document.getElementById('runtimeDetail').textContent =
      'Checkpoint Blockly de reconstruction endommagé ou indisponible — exécution verrouillée. Aucune donnée n’a été effacée.';
    return; // Never start a program or overwrite a damaged checkpoint.
  }
  wireWorkspaceControls(); wireDebugControls(); workspace.addChangeListener(onWorkspaceChange);
  window.addEventListener('resize', function() { Blockly.svgResize(workspace); });
  window.dispatchEvent(new CustomEvent('webeeblocks-ui-ready', {detail: {blocklyVersion: Blockly.VERSION, renderer: 'zelos', theme: 'webeeblocksStudent'}}));
  try {
    var module = await import(new URL('./webots/RobotWindow.js', WEBEEBLOCKS_MAIN_SCRIPT_URL).href);
    robotWindow = new module.default();
    runtimeBackend = new WebeeBlocksWwiBackend(robotWindow, {timeoutMs: 35000, simulationDebug: true, simulationReset: true, simulationStop: true, simulationScenes: true, simulationWorldReload: true});
    // Keep every request ID greater than all IDs allocated before world reload.
    if (recovery) runtimeBackend.nextId = recovery.nextRequestId;
    robotWindow.receive = receiveMessage;
    if (!recovery) setRuntimeStatus('INITIALISATION', 'Connexion à la simulation');
    // Multiple tabs can exist when Webots' second browser launch succeeds.
    // A Web Lock is scoped to one browser storage partition and ensures that
    // only one matching checkpoint holder performs the native RESET/scene
    // sequence. A late duplicate detects the consumed checkpoint and FAILS
    // CLOSED rather than obtaining a second unrelated initial-boot authority.
    async function authorizeIncarnation() {
      if (recovery) {
        var latest = WebeeBlocksSimulationRecovery.peek();
        if (!latest || JSON.stringify(latest) !== JSON.stringify(recovery))
          throw new Error('Reconstruction déjà reprise par un autre document Blockly — ce document reste verrouillé');
      }
      await runtimeBackend.waitUntilReady();
      var nativeRecovery = await runtimeBackend.readRecoveryStatus(recovery ? recovery.token : undefined);
      if (!nativeRecovery || nativeRecovery.state === 'INVALID')
        throw new Error('Témoin natif de reconstruction absent, endommagé ou inaccessible — exécution verrouillée');
      if (nativeRecovery.state === 'PENDING' && (!recovery || nativeRecovery.matched !== true))
        throw new Error('Reconstruction inachevée : programme Blockly non disponible ou témoin incohérent — exécution verrouillée');
      if (recovery && nativeRecovery.state !== 'PENDING')
        throw new Error('Checkpoint Blockly sans témoin natif correspondant — exécution verrouillée');
      // Admission is C-native, not derived from READY, NONE or any browser lock.
      // During PENDING the previous document's capability is rotated before
      // RESET #1; after CLEAR it remains exclusively held in this JS document.
      if (recovery && !authorityHandoff)
        throw new Error('Native recovery requires the original browsing context');
      await runtimeBackend.claimAuthority(recovery ? authorityHandoff : undefined);
      if (recovery) {
        // READY alone is insufficient: this new incarnation must demonstrate
        // the unchanged strict physical stability and the restored scene.
        await runtimeBackend.resetSimulation(true);
        await runtimeBackend.prepareActivity(runtimeProfile);
        await runtimeBackend.resetSimulation(true);
        await runtimeBackend.prepareActivity(runtimeProfile);
        if (serializedWorkspace() !== recovery.workspace || runtimeProfile.id !== recovery.profileId)
          throw new Error('Recovery changed the pupil project');
        // Native commitment is consumed only after both physical RESETs, scene
        // acknowledgements and independent SHA-256 verification of the exact
        // restored serialized Blockly bytes and profile.
        var digest = await WebeeBlocksSimulationRecovery.fingerprint(
          runtimeProfile.id, serializedWorkspace());
        await runtimeBackend.clearRecoveryWitness(recovery.token, digest);
        WebeeBlocksSimulationRecovery.clear(recovery);
        runtimeTerminal = false;
        runtimeNeedsRebuild = false;
        runtimeRecoveryPending = false;
        renderSensorValues({});
        renderVariables(null);
        setRuntimeStatus('PRÊT', 'Monde reconstruit — programme à relancer');
        window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-reset', {
          detail: {workspacePreserved: true, worldRebuilt: true}
        }));
      } else {
        runtimeRecoveryPending = false;
        runtimeTerminal = false;
        setRuntimeStatus('PRÊT', 'Simulation connectée');
      }
    }
    if (recovery) {
      if (!window.WebeeBlocksWindowRenewal)
        throw new Error('Verrou de reprise indisponible — vol interdit');
      await window.WebeeBlocksWindowRenewal.withRecoveryLock(authorizeIncarnation);
    } else {
      await authorizeIncarnation();
    }
    if (runtimeBackend.capabilities && runtimeBackend.capabilities.simulationDebug === true) document.getElementById('debugPanel').hidden = false;
    updateRuntimeActions();
  } catch (error) {
    runtimeTerminal = true;
    runtimeNeedsRebuild = true;
    runtimeRecoveryPending = true; // No status, no execution; even if READY arrived.
    setRuntimeFailure(error);
    document.getElementById('runtimeDetail').textContent =
      'Récupération non vérifiée — exécution interdite. ' + (error && error.message ? error.message : String(error));
  }
};

document.getElementById('submit').onclick = activatePrimaryExecution;
