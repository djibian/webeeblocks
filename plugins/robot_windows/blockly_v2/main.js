var runtimeProfile = null;
var workspace = null;
var robotWindow = null;
var runtimeBackend = null;
var runtimeRunning = false;
var runtimeTerminal = false;
var runtimeResetPending = false;
var runtimeDebug = null;

var WEBEEBLOCKS_WORKSPACE_SCALE = 0.90;

var WebeeBlocksStudentTheme = Blockly.Theme.defineTheme('webeeblocksStudent', {
  base: Blockly.Themes.Classic,
  blockStyles: {
    flight_blocks: { colourPrimary: '#2563EB', colourSecondary: '#1D4ED8', colourTertiary: '#1E40AF' },
    control_blocks: { colourPrimary: '#7C3AED', colourSecondary: '#6D28D9', colourTertiary: '#5B21B6' },
    sensor_blocks: { colourPrimary: '#0E7490', colourSecondary: '#0F5F73', colourTertiary: '#164E63' },
    operator_blocks: { colourPrimary: '#047857', colourSecondary: '#046C4E', colourTertiary: '#065F46' },
    logic_blocks: { colourPrimary: '#7C3AED', colourSecondary: '#6D28D9', colourTertiary: '#5B21B6' },
    loop_blocks: { colourPrimary: '#7C3AED', colourSecondary: '#6D28D9', colourTertiary: '#5B21B6' },
    math_blocks: { colourPrimary: '#047857', colourSecondary: '#046C4E', colourTertiary: '#065F46' }
  },
  categoryStyles: {
    flight_category: {colour: '#2563EB'},
    control_category: {colour: '#7C3AED'},
    sensor_category: {colour: '#0E7490'},
    operator_category: {colour: '#047857'}
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
  var ready = !!(runtimeBackend && runtimeBackend.ready);
  var submit = document.getElementById('submit');
  var reset = document.getElementById('resetSimulation');
  submit.disabled = !ready || runtimeRunning || runtimeTerminal || runtimeResetPending;
  if (reset) {
    var resetSupported = !!(runtimeBackend && runtimeBackend.capabilities && runtimeBackend.capabilities.simulationReset === true);
    reset.hidden = !resetSupported;
    reset.disabled = !resetSupported || !ready || runtimeRunning || runtimeResetPending || !runtimeTerminal;
  }
}

function setRuntimeStatus(state, detail) {
  document.getElementById('runtimeState').textContent = state;
  document.getElementById('runtimeDetail').textContent = detail || '';
  document.body.dataset.runtimeState = state;
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2', { detail: {state: state, detail: detail || null} }));
  updateRuntimeActions();
}

function setRuntimeFailure(error) {
  var outcome = WebeeBlocksRuntimeOutcome.classify(error);
  console.error(error);
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-diagnostic', {
    detail: {
      studentState: outcome.state,
      machineCode: outcome.machineCode,
      technicalMessage: error && error.message ? error.message : String(error)
    }
  }));
  setRuntimeStatus(outcome.state, outcome.detail);
}

function categoryLabel(category) {
  if (category === 'flight') return 'Vol';
  if (category === 'control') return 'Contrôle';
  if (category === 'sensor') return 'Capteurs';
  if (category === 'operator') return 'Opérateurs';
  throw new Error('unknown toolbox category: ' + category);
}
function categoryStyle(category) {
  if (category === 'flight') return 'flight_category';
  if (category === 'control') return 'control_category';
  if (category === 'sensor') return 'sensor_category';
  if (category === 'operator') return 'operator_category';
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
}

function buildToolbox(profile) {
  var toolbox = document.createElement('xml');
  var groups = {flight: [], control: [], sensor: [], operator: []};
  profile.toolbox.forEach(function(type) {
    var definition = WebeeBlocksActivities.BLOCK_CATALOG[type];
    var category = (definition && definition.category) || 'control';
    if (!Object.prototype.hasOwnProperty.call(groups, category)) throw new Error('unsupported toolbox category for ' + type + ': ' + category);
    groups[category].push(type);
  });
  ['flight', 'control', 'sensor', 'operator'].forEach(function(category) {
    if (!groups[category].length) return;
    var categoryNode = document.createElement('category');
    categoryNode.setAttribute('name', categoryLabel(category));
    categoryNode.setAttribute('categorystyle', categoryStyle(category));
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
  if (runtimeBackend && runtimeBackend.handleMessage(value)) {
    window.dispatchEvent(new CustomEvent('webeeblocks-wwi', {detail: value}));
    return;
  }
  console.log('Unhandled Robot Window message:', value);
}

function setDebugControls(paused) {
  document.getElementById('stepNext').disabled = !paused;
  document.getElementById('stepContinue').disabled = !runtimeRunning;
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

function serializedWorkspace() {
  if (!workspace || !Blockly.serialization || !Blockly.serialization.workspaces)
    throw new Error('Blockly workspace serialization unavailable');
  return JSON.stringify(Blockly.serialization.workspaces.save(workspace));
}

async function resetSimulation() {
  if (runtimeRunning || runtimeResetPending || !runtimeTerminal || !runtimeBackend || !runtimeBackend.ready)
    return;
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
    renderSensorValues({});
    renderVariables(null);
    if (runtimeDebug) runtimeDebug.finish();
    document.getElementById('debugState').textContent = 'Observation inactive';
    setRuntimeStatus('PRÊT', 'Simulation réinitialisée');
    window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-reset', {detail: {workspacePreserved: true}}));
  } catch (error) {
    runtimeTerminal = true;
    setRuntimeFailure(error);
  } finally {
    runtimeResetPending = false;
    setDebugControls(false);
    updateRuntimeActions();
  }
}

async function runProgram() {
  if (runtimeRunning || runtimeTerminal || runtimeResetPending || !runtimeBackend || !runtimeBackend.ready) return;
  var submit = document.getElementById('submit');
  var stepMode = document.getElementById('stepMode');
  var debugRequested = stepMode.checked === true;
  if (debugRequested && (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationDebug !== true)) {
    setRuntimeFailure(new Error('Simulation step debug unavailable'));
    return;
  }
  submit.disabled = true;
  runtimeTerminal = false;
  var hooks = runtimeDebug ? runtimeDebug.begin(debugRequested) : null;
  try {
    await WebeeBlocksActivityContract.execute(runtimeProfile, workspace, WebeeBlocksSemanticAst, WebeeBlocksInterpreter, runtimeBackend, {
      maxSteps: 1000,
      hooks: hooks,
      onAst: function(ast) {
        window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-ast', {detail: ast}));
        runtimeRunning = true; setDebugControls(false); setRuntimeStatus('EN VOL', 'Programme réactif en cours');
      }
    });
    runtimeRunning = false; runtimeTerminal = true; setRuntimeStatus('TERMINÉ', 'Programme exécuté');
  } catch (error) {
    runtimeRunning = false; runtimeTerminal = true; setRuntimeFailure(error);
  } finally {
    if (runtimeDebug) runtimeDebug.finish();
    stepMode.disabled = false;
    updateRuntimeActions();
  }
}

function onWorkspaceChange(event) {
  if (!event || event.type === Blockly.Events.UI) return;
  try { WebeeBlocksActivityContract.applyFieldBounds(runtimeProfile, workspace); } catch (error) { console.error(error); }
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
}

window.onload = async function() {
  runtimeProfile = WebeeBlocksActivityProfiles.resolveById(WebeeBlocksActivities.DOCUMENT, 'reactive-obstacle-v2', WebeeBlocksActivities.BLOCK_CATALOG);
  document.getElementById('activityTitle').textContent = runtimeProfile.brief.title;
  document.getElementById('activityGoal').textContent = runtimeProfile.brief.goal;
  applySemanticBuiltinStyles();
  workspace = Blockly.inject('blocklyDiv', {
    toolbox: buildToolbox(runtimeProfile), renderer: 'zelos', theme: WebeeBlocksStudentTheme, scrollbars: true,
    move: {scrollbars: true, drag: true, wheel: true},
    zoom: {controls: false, wheel: true, startScale: WEBEEBLOCKS_WORKSPACE_SCALE, maxScale: 1.40, minScale: 0.55, scaleSpeed: 1.10, pinch: true},
    trashcan: true, media: 'vendor/media/', sounds: false
  });
  wireWorkspaceControls(); wireDebugControls(); workspace.addChangeListener(onWorkspaceChange);
  window.addEventListener('resize', function() { Blockly.svgResize(workspace); });
  window.dispatchEvent(new CustomEvent('webeeblocks-ui-ready', {detail: {blocklyVersion: Blockly.VERSION, renderer: 'zelos', theme: 'webeeblocksStudent'}}));
  try {
    var module = await import('./webots/RobotWindow.js');
    robotWindow = new module.default();
    runtimeBackend = new WebeeBlocksWwiBackend(robotWindow, {timeoutMs: 35000, simulationDebug: true, simulationReset: true});
    robotWindow.receive = receiveMessage;
    setRuntimeStatus('INITIALISATION', 'Connexion à la simulation');
    await runtimeBackend.waitUntilReady();
    if (runtimeBackend.capabilities && runtimeBackend.capabilities.simulationDebug === true) document.getElementById('debugPanel').hidden = false;
    updateRuntimeActions();
    setRuntimeStatus('PRÊT', 'Simulation connectée');
  } catch (error) { setRuntimeFailure(error); }
};

document.getElementById('submit').onclick = runProgram;
