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
var runtimeDebug = null;
var runtimeExecutionSettled = null;
var debugCurrentBlockId = null;
var debugFollowExecution = true;
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
    scrollbarColour: '#64778c', scrollbarOpacity: 0.95, insertionMarkerColour: '#167f91', insertionMarkerOpacity: 0.35,
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
  var stop = document.getElementById('stopSimulation');
  var stopSupported = !!(runtimeBackend && runtimeBackend.capabilities && runtimeBackend.capabilities.simulationStop === true);
  var primaryIsStop = runtimeRunning === true || runtimeOutcomePending === true;
  var primaryLabel = primaryIsStop ? 'Arrêter le vol' : 'Lancer le vol';
  submit.textContent = primaryLabel;
  if (typeof submit.setAttribute === 'function') submit.setAttribute('aria-label', primaryLabel);
  submit.disabled = primaryIsStop
    ? (!stopSupported || !ready || runtimeOutcomePending || runtimeStopPending || runtimeStopRequested)
    : (!ready || runtimeTerminal || runtimeOutcomePending || runtimeResetPending || runtimeStopPending || runtimeScenePending || runtimeProjectPending);
  if (stop) {
    stop.hidden = true;
    stop.disabled = true;
  }
  if (reset) {
    var resetSupported = !!(runtimeBackend && runtimeBackend.capabilities && runtimeBackend.capabilities.simulationReset === true);
    reset.hidden = !resetSupported;
    var pausedDebugStop = runtimeRunning && runtimeDebug && runtimeDebug.waiter &&
      stopSupported && !runtimeStopRequested;
    reset.disabled = !resetSupported || !ready || (runtimeRunning && !pausedDebugStop) ||
      runtimeOutcomePending || runtimeResetPending || runtimeStopPending ||
      runtimeScenePending || runtimeProjectPending || (!runtimeTerminal && !pausedDebugStop);
    reset.textContent = pausedDebugStop ? 'Arrêter puis réinitialiser' : 'Réinitialiser';
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
  var detail = presentation.detail;
  if (missionOutcome && runtimeProfile && runtimeProfile.evaluation &&
      runtimeProfile.evaluation.oracle === 'grand-prix-route-v2' &&
      error && error.code === 'TIME_LIMIT')
    detail += ' | Sécurité : atterrissage imposé';
  setRuntimeStatus(presentation.state, detail);
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

// Toolbox shadows are explicit editable Blockly numbers, not runtime fallbacks.
function appendNumericShadow(block, socket, number) {
  var value = document.createElement('value');
  value.setAttribute('name', socket);
  var shadow = document.createElement('shadow');
  shadow.setAttribute('type', 'math_number');
  var field = document.createElement('field');
  field.setAttribute('name', 'NUM');
  field.textContent = String(number);
  shadow.appendChild(field);
  value.appendChild(shadow);
  block.appendChild(value);
}

function profileNumberDefault(profile, preferred) {
  var limits = profile.parameterBounds && profile.parameterBounds.math_number &&
    profile.parameterBounds.math_number.NUM || {};
  var min = Number.isFinite(limits.min) ? limits.min : preferred;
  var max = Number.isFinite(limits.max) ? limits.max : preferred;
  return Math.max(min, Math.min(preferred, max));
}

function buildToolbox(profile) {
  var toolbox = document.createElement('xml');
  var groups = {flight: [], control: [], sensor: [], operator: [], variable: [], procedure: []};
  profile.toolbox.forEach(function(type) {
    var definition = WebeeBlocksActivities.BLOCK_CATALOG[type];
    var category = (definition && definition.category) || 'control';
    if (!Object.prototype.hasOwnProperty.call(groups, category)) throw new Error('unsupported toolbox category for ' + type + ': ' + category);
    // A number remains an allowed block in the profile and in saved projects.
    // Numeric expression sockets now already offer one without a separate flyout item.
    if (type !== 'math_number') groups[category].push(type);
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
      if (type === 'webeeblocks_v2_takeoff' || type === 'webeeblocks_v2_move' ||
          type === 'webeeblocks_v2_vertical') {
        var bounds = profile.runtime && profile.runtime.astBounds || {};
        var name = type === 'webeeblocks_v2_takeoff' ? 'takeoff.height_m' :
          type === 'webeeblocks_v2_vertical' ? 'vertical.distance_m' : 'move.distance_m';
        var limits = bounds[name] || {};
        var preferred = type === 'webeeblocks_v2_takeoff' ? 0.5 :
          type === 'webeeblocks_v2_vertical' ? 0.2 : 0.3;
        var minimum = Number.isFinite(limits.min) ? limits.min : preferred;
        var maximum = Number.isFinite(limits.max) ? limits.max : preferred;
        appendNumericShadow(block, type === 'webeeblocks_v2_takeoff' ? 'HEIGHT' : 'DISTANCE',
          Math.max(minimum, Math.min(preferred, maximum)));
      }
      var defaults = {
        controls_repeat_ext: [['TIMES', 3]],
        variables_set: [['VALUE', 0]],
        math_change: [['DELTA', 1]],
        logic_compare: [['A', 0], ['B', 1]],
        math_arithmetic: [['A', 1], ['B', 1]]
      }[type] || [];
      defaults.forEach(function(entry) {
        appendNumericShadow(block, entry[0], profileNumberDefault(profile, entry[1]));
      });
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
  document.getElementById('stepContinue').disabled = !paused;
  document.getElementById('debugShowCurrent').disabled = !paused || !debugCurrentBlockId;
  document.getElementById('stepMode').disabled = runtimeRunning || runtimeResetPending;
}

function markManualDebugNavigation() {
  if (runtimeRunning && runtimeDebug && runtimeDebug.enabled) debugFollowExecution = false;
}

// Blockly's native view movement is not a Blockly program change.
function showDebugCurrentBlock(force) {
  if (!workspace || !debugCurrentBlockId || typeof workspace.centerOnBlock !== 'function') return false;
  var block = workspace.getBlockById(debugCurrentBlockId);
  if (!block) return false;
  if (!force && typeof block.getSvgRoot === 'function' && typeof workspace.getParentSvg === 'function') {
    var svg = block.getSvgRoot();
    var background = workspace.getParentSvg().querySelector('.blocklyMainBackground');
    if (svg && background) {
      var bounds = svg.getBoundingClientRect();
      var view = background.getBoundingClientRect();
      var margin = 16;
      if (bounds.width > 0 && bounds.height > 0 &&
          bounds.left >= view.left + margin && bounds.right <= view.right - margin &&
          bounds.top >= view.top + margin && bounds.bottom <= view.bottom - margin)
        return true; // Do not jump when the block is already visible.
    }
  }
  workspace.centerOnBlock(debugCurrentBlockId, true);
  return true;
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
      debugCurrentBlockId = null;
      debugFollowExecution = true;
      document.getElementById('debugState').textContent = detail.enabled ? 'Pas à pas actif' : 'Observation inactive';
      renderSensorValues({}); renderVariables(null); setDebugControls(false);
    },
    onActive: function(detail) {
      debugCurrentBlockId = detail.blockId || null;
      var block = detail.blockId ? workspace.getBlockById(detail.blockId) : null;
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-active', { detail: {
        path: detail.path, kind: detail.node && detail.node.kind, blockId: detail.blockId, blockType: block ? block.type : null
      }}));
    },
    onPause: function(detail) {
      debugCurrentBlockId = detail.blockId || null;
      if (debugFollowExecution) showDebugCurrentBlock(false);
      document.getElementById('debugState').textContent = detail.reason === 'breakpoint' ? 'Point d’arrêt' : 'En pause'; setDebugControls(true); updateRuntimeActions();
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-paused', {detail: detail}));
    },
    onResume: function(detail) {
      document.getElementById('debugState').textContent = 'Exécution'; setDebugControls(false); updateRuntimeActions();
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-resumed', {detail: detail}));
    },
    onSensor: function(detail) {
      renderSensorValues(detail.values);
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-sensor', { detail: {
        path: detail.path, blockId: detail.blockId, direction: detail.direction, value: detail.value
      }}));
    },
    onVariables: function(detail) { renderVariables(detail.values); },
    onFinish: function() {
      debugCurrentBlockId = null;
      document.getElementById('debugState').textContent = 'Observation terminée'; setDebugControls(false);
    }
  });
  document.getElementById('stepNext').addEventListener('click', function() { runtimeDebug.next(); });
  document.getElementById('stepContinue').addEventListener('click', function() { runtimeDebug.continueRun(); });

  // Native Blockly menu before execution; registry preserves built-in and
  // procedure-specific menu entries. No block field or .wbb metadata is changed.
  Blockly.ContextMenuRegistry.registry.register({
    id: 'webeeblocks-toggle-breakpoint',
    scopeType: Blockly.ContextMenuRegistry.ScopeType.BLOCK,
    weight: 25,
    preconditionFn: function(scope) {
      var block = scope.block;
      return block && block.workspace === workspace && block.type !== 'procedures_defnoreturn' &&
        runtimeDebug && !runtimeRunning ? 'enabled' : 'hidden';
    },
    displayText: function(scope) {
      return runtimeDebug.hasBreakpoint(scope.block.id) ? 'Retirer le point d’arrêt' : 'Ajouter un point d’arrêt';
    },
    callback: function(scope) { runtimeDebug.toggleBreakpoint(scope.block.id); }
  });

  // Blockly 13 deliberately suppresses its own menu on a read-only workspace.
  // During a debugger pause, offer the same single action on right-click;
  // never make the Blockly program editable while a flight is in progress.
  var breakpointMenu = document.createElement('button');
  breakpointMenu.id = 'debugBreakpointMenu';
  breakpointMenu.type = 'button';
  breakpointMenu.hidden = true;
  breakpointMenu.className = 'webee-debug-breakpoint-menu';
  document.body.appendChild(breakpointMenu);
  function closeBreakpointMenu() { breakpointMenu.hidden = true; }
  breakpointMenu.addEventListener('click', function() {
    if (!breakpointMenu.hidden && runtimeDebug && runtimeDebug.waiter)
      runtimeDebug.toggleBreakpoint(breakpointMenu.dataset.blockId);
    closeBreakpointMenu();
  });
  window.addEventListener('click', closeBreakpointMenu);
  window.addEventListener('keydown', function(event) { if (event.key === 'Escape') closeBreakpointMenu(); });
  var blocklyView = document.getElementById('blocklyDiv');
  blocklyView.addEventListener('contextmenu', function(event) {
    if (!runtimeDebug || !runtimeDebug.enabled || !runtimeDebug.waiter ||
        !workspace || !workspace.isReadOnly || !workspace.isReadOnly()) return;
    // Resolve the innermost real block (expressions are nested SVG groups).
    var clicked = null;
    workspace.getAllBlocks(false).forEach(function(block) {
      var svg = block && block.getSvgRoot && block.getSvgRoot();
      if (svg && svg.contains(event.target) && (!clicked ||
          clicked.getSvgRoot().contains(svg))) clicked = block;
    });
    if (!clicked || clicked.type === 'procedures_defnoreturn') return;
    event.preventDefault();
    event.stopPropagation();
    breakpointMenu.dataset.blockId = clicked.id;
    breakpointMenu.textContent = runtimeDebug.hasBreakpoint(clicked.id) ?
      'Retirer le point d’arrêt' : 'Ajouter un point d’arrêt';
    breakpointMenu.style.left = Math.max(4, Math.min(event.clientX, window.innerWidth - 230)) + 'px';
    breakpointMenu.style.top = Math.max(4, Math.min(event.clientY, window.innerHeight - 46)) + 'px';
    breakpointMenu.hidden = false;
    breakpointMenu.focus();
  }, true);
  document.getElementById('debugShowCurrent').addEventListener('click', function() {
    if (this.disabled) return;
    debugFollowExecution = true;
    showDebugCurrentBlock(true);
  });
  // Capture genuine student navigation, not viewport events generated by centerOnBlock().
  var view = document.getElementById('blocklyDiv');
  view.addEventListener('pointerdown', markManualDebugNavigation, true);
  view.addEventListener('wheel', markManualDebugNavigation, {capture: true, passive: true});
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
    return false;
  if (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationStop !== true)
    return false;
  runtimeStopPending = true;
  runtimeStopRequested = true;
  updateRuntimeActions();
  setDebugControls(false);
  if (runtimeDebug) runtimeDebug.cancel();
  try {
    await runtimeBackend.stopSimulation();
    runtimeTerminal = true;
    setRuntimeFailure(userStoppedError());
    return true;
  } catch (error) {
    runtimeTerminal = true;
    setRuntimeFailure(error);
    return false;
  } finally {
    runtimeStopPending = false;
    updateRuntimeActions();
  }
}

async function resetSimulation() {
  // RESET during a debugger wait must first obtain the ordinary native STOP ACK.
  // No direct native RESET while an attempt is running or its outcome is pending.
  if (runtimeRunning && runtimeDebug && runtimeDebug.waiter && !runtimeStopPending) {
    var executionSettled = runtimeExecutionSettled;
    if (await stopSimulation() !== true) return;
    if (executionSettled) await executionSettled;
  }
  if (runtimeRunning || runtimeOutcomePending || runtimeResetPending || runtimeStopPending ||
      !runtimeTerminal || !runtimeBackend || !runtimeBackend.ready)
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
    runtimeStopRequested = false;
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
  if (runtimeRunning || runtimeTerminal || runtimeOutcomePending || runtimeResetPending || runtimeStopPending || runtimeScenePending || runtimeProjectPending || !runtimeBackend || !runtimeBackend.ready) return;
  var submit = document.getElementById('submit');
  var stepMode = document.getElementById('stepMode');
  var debugRequested = stepMode.checked === true;
  if (debugRequested && (!runtimeBackend.capabilities || runtimeBackend.capabilities.simulationDebug !== true)) {
    setRuntimeFailure(new Error('Simulation step debug unavailable'));
    return;
  }
  submit.disabled = true;
  var settleExecution;
  runtimeExecutionSettled = new Promise(function(resolve) { settleExecution = resolve; });
  runtimeTerminal = false;
  runtimeStopRequested = false;
  var hooks = runtimeDebug ? runtimeDebug.begin(debugRequested) : null;
  try {
    await WebeeBlocksActivityContract.execute(runtimeProfile, workspace, WebeeBlocksSemanticAst, WebeeBlocksInterpreter, runtimeBackend, {
      maxSteps: runtimeProfile.runtime.maxSteps || 1000,
      hooks: hooks,
      onAst: function(ast) {
        window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-ast', {detail: ast}));
        runtimeRunning = true; setDebugControls(false); setRuntimeStatus('EXÉCUTION', 'Programme en cours — vol non confirmé');
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
    settleExecution();
    runtimeExecutionSettled = null;
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
  if (event && event.type === Blockly.Events.BLOCK_DELETE && runtimeDebug)
    runtimeDebug.pruneBreakpoints();
  if (!event || event.isUiEvent === true || event.type === Blockly.Events.UI ||
      event.type === Blockly.Events.VIEWPORT_CHANGE || isPureVisualWorkspaceMove(event)) return;
  try {
    if (event.type === Blockly.Events.BLOCK_CREATE)
      profileFieldOptions.applyWorkspace(workspace);
    WebeeBlocksActivityContract.applyFieldBounds(runtimeProfile, workspace);
  } catch (error) { console.error(error); }
  if (!runtimeRunning && runtimeTerminal)
    document.getElementById('runtimeDetail').textContent = 'Programme modifié — réinitialisez la simulation avant de relancer';
}
function wireWorkspaceControls() {
  document.getElementById('zoomIn').addEventListener('click', function() { markManualDebugNavigation(); workspace.zoomCenter(1); });
  document.getElementById('zoomOut').addEventListener('click', function() { markManualDebugNavigation(); workspace.zoomCenter(-1); });
  document.getElementById('zoomFit').addEventListener('click', function() { markManualDebugNavigation(); workspace.zoomToFit(); });
  document.getElementById('zoomReset').addEventListener('click', function() {
    markManualDebugNavigation();
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
  document.getElementById('activityGoal').textContent = runtimeProfile.brief.mission || runtimeProfile.brief.goal || '';
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
  wireWorkspaceControls(); wireDebugControls(); workspace.addChangeListener(onWorkspaceChange);
  window.addEventListener('resize', function() { Blockly.svgResize(workspace); });
  window.dispatchEvent(new CustomEvent('webeeblocks-ui-ready', {detail: {blocklyVersion: Blockly.VERSION, renderer: 'zelos', theme: 'webeeblocksStudent'}}));
  try {
    var module = await import(new URL('./webots/RobotWindow.js', WEBEEBLOCKS_MAIN_SCRIPT_URL).href);
    robotWindow = new module.default();
    runtimeBackend = new WebeeBlocksWwiBackend(robotWindow, {timeoutMs: 35000, simulationDebug: true, simulationReset: true, simulationStop: true, simulationScenes: true});
    robotWindow.receive = receiveMessage;
    setRuntimeStatus('INITIALISATION', 'Connexion à la simulation');
    await runtimeBackend.waitUntilReady();
    if (runtimeBackend.capabilities && runtimeBackend.capabilities.simulationDebug === true) document.getElementById('debugPanel').hidden = false;
    updateRuntimeActions();
    setRuntimeStatus('PRÊT', 'Simulation connectée');
  } catch (error) { setRuntimeFailure(error); }
};

document.getElementById('submit').onclick = activatePrimaryExecution;
