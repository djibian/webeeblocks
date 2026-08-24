var runtimeProfile = null;
var workspace = null;
var robotWindow = null;
var runtimeBackend = null;
var runtimeRunning = false;
var runtimeTerminal = false;

var WEBEEBLOCKS_WORKSPACE_SCALE = 0.90;

var WebeeBlocksStudentTheme = Blockly.Theme.defineTheme('webeeblocksStudent', {
  base: Blockly.Themes.Classic,
  blockStyles: {
    flight_blocks: {
      colourPrimary: '#2563EB',
      colourSecondary: '#1D4ED8',
      colourTertiary: '#1E40AF'
    },
    control_blocks: {
      colourPrimary: '#7C3AED',
      colourSecondary: '#6D28D9',
      colourTertiary: '#5B21B6'
    },
    sensor_blocks: {
      colourPrimary: '#0E7490',
      colourSecondary: '#0F5F73',
      colourTertiary: '#164E63'
    },
    operator_blocks: {
      colourPrimary: '#047857',
      colourSecondary: '#046C4E',
      colourTertiary: '#065F46'
    },
    logic_blocks: {
      colourPrimary: '#7C3AED',
      colourSecondary: '#6D28D9',
      colourTertiary: '#5B21B6'
    },
    loop_blocks: {
      colourPrimary: '#7C3AED',
      colourSecondary: '#6D28D9',
      colourTertiary: '#5B21B6'
    },
    math_blocks: {
      colourPrimary: '#047857',
      colourSecondary: '#046C4E',
      colourTertiary: '#065F46'
    }
  },
  categoryStyles: {
    flight_category: {colour: '#2563EB'},
    control_category: {colour: '#7C3AED'},
    sensor_category: {colour: '#0E7490'},
    operator_category: {colour: '#047857'}
  },
  componentStyles: {
    workspaceBackgroundColour: '#f7f9fc',
    toolboxBackgroundColour: '#ffffff',
    toolboxForegroundColour: '#263342',
    flyoutBackgroundColour: '#eef2f7',
    flyoutForegroundColour: '#263342',
    flyoutOpacity: 1,
    scrollbarColour: '#9aa7b5',
    scrollbarOpacity: 0.55,
    insertionMarkerColour: '#167f91',
    insertionMarkerOpacity: 0.35,
    cursorColour: '#167f91',
    selectedGlowColour: '#167f91',
    selectedGlowOpacity: 0.18,
    replacementGlowColour: '#167f91',
    replacementGlowOpacity: 0.18
  },
  fontStyle: {
    family: 'Inter, Aptos, Segoe UI, Arial, sans-serif',
    weight: '600',
    size: 12
  },
  startHats: false
});

function setRuntimeStatus(state, detail) {
  document.getElementById('runtimeState').textContent = state;
  document.getElementById('runtimeDetail').textContent = detail || '';
  document.body.dataset.runtimeState = state;
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2', {
    detail: {state: state, detail: detail || null}
  }));
}

function categoryLabel(category) {
  if (category === 'flight') return 'Vol';
  if (category === 'control') return 'Contrôle';
  if (category === 'sensor') return 'Capteurs';
  if (category === 'operator') return 'Opérateurs';
  throw new Error('unknown toolbox category: ' + category);
}

function categoryColour(category) {
  if (category === 'flight') return '#2563EB';
  if (category === 'control') return '#7C3AED';
  if (category === 'sensor') return '#0E7490';
  if (category === 'operator') return '#047857';
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
  if (!definition || typeof definition.init !== 'function')
    throw new Error('cannot style unknown Blockly block: ' + type);
  var originalInit = definition.init;
  definition.init = function() {
    originalInit.call(this);
    this.setStyle(style);
  };
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
    if (!Object.prototype.hasOwnProperty.call(groups, category))
      throw new Error('unsupported toolbox category for ' + type + ': ' + category);
    groups[category].push(type);
  });
  ['flight', 'control', 'sensor', 'operator'].forEach(function(category) {
    if (!groups[category].length) return;
    var categoryNode = document.createElement('category');
    categoryNode.setAttribute('name', categoryLabel(category));
    categoryNode.setAttribute('colour', categoryColour(category));
    categoryNode.setAttribute('categorystyle', categoryStyle(category));
    groups[category].forEach(function(type) {
      var block = document.createElement('block');
      block.setAttribute('type', type);
      if (type === 'controls_repeat_ext') {
        var value = document.createElement('value');
        value.setAttribute('name', 'TIMES');
        var shadow = document.createElement('shadow');
        shadow.setAttribute('type', 'math_number');
        var field = document.createElement('field');
        field.setAttribute('name', 'NUM');
        field.textContent = '3';
        shadow.appendChild(field);
        value.appendChild(shadow);
        block.appendChild(value);
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

async function runProgram() {
  if (runtimeRunning || !runtimeBackend || !runtimeBackend.ready)
    return;
  var submit = document.getElementById('submit');
  submit.disabled = true;
  runtimeTerminal = false;
  try {
    await WebeeBlocksActivityContract.execute(
      runtimeProfile,
      workspace,
      WebeeBlocksSemanticAst,
      WebeeBlocksInterpreter,
      runtimeBackend,
      {
        maxSteps: 1000,
        onAst: function(ast) {
          window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-ast', {detail: ast}));
          runtimeRunning = true;
          setRuntimeStatus('EN VOL', 'Programme réactif en cours');
        }
      }
    );
    runtimeRunning = false;
    runtimeTerminal = true;
    setRuntimeStatus('TERMINÉ', 'Programme exécuté');
  } catch (error) {
    runtimeRunning = false;
    runtimeTerminal = true;
    console.error(error);
    setRuntimeStatus('ERREUR', error && error.message ? error.message : String(error));
  } finally {
    submit.disabled = !runtimeBackend.ready;
  }
}

function onWorkspaceChange(event) {
  if (!event || event.type === Blockly.Events.UI)
    return;
  try {
    WebeeBlocksActivityContract.applyFieldBounds(runtimeProfile, workspace);
  } catch (error) {
    console.error(error);
  }
  if (!runtimeRunning && runtimeTerminal) {
    runtimeTerminal = false;
    setRuntimeStatus('PRÊT', 'Programme modifié');
  }
}

function wireWorkspaceControls() {
  document.getElementById('zoomIn').addEventListener('click', function() {
    workspace.zoomCenter(1);
  });
  document.getElementById('zoomOut').addEventListener('click', function() {
    workspace.zoomCenter(-1);
  });
  document.getElementById('zoomFit').addEventListener('click', function() {
    workspace.zoomToFit();
  });
  document.getElementById('zoomReset').addEventListener('click', function() {
    workspace.setScale(WEBEEBLOCKS_WORKSPACE_SCALE);
    if (typeof workspace.scrollCenter === 'function')
      workspace.scrollCenter();
  });
}

window.onload = async function() {
  runtimeProfile = WebeeBlocksActivityProfiles.resolveById(
    WebeeBlocksActivities.DOCUMENT,
    'reactive-obstacle-v2',
    WebeeBlocksActivities.BLOCK_CATALOG
  );
  document.getElementById('activityTitle').textContent = runtimeProfile.brief.title;
  document.getElementById('activityGoal').textContent = runtimeProfile.brief.goal;
  applySemanticBuiltinStyles();
  workspace = Blockly.inject('blocklyDiv', {
    toolbox: buildToolbox(runtimeProfile),
    renderer: 'zelos',
    theme: WebeeBlocksStudentTheme,
    scrollbars: true,
    move: {
      scrollbars: true,
      drag: true,
      wheel: true
    },
    zoom: {
      controls: false,
      wheel: true,
      startScale: WEBEEBLOCKS_WORKSPACE_SCALE,
      maxScale: 1.40,
      minScale: 0.55,
      scaleSpeed: 1.10,
      pinch: true
    },
    trashcan: true,
    media: 'vendor/media/',
    sounds: false
  });
  wireWorkspaceControls();
  workspace.addChangeListener(onWorkspaceChange);
  window.addEventListener('resize', function() { Blockly.svgResize(workspace); });

  window.dispatchEvent(new CustomEvent('webeeblocks-ui-ready', {
    detail: {
      blocklyVersion: Blockly.VERSION,
      renderer: 'zelos',
      theme: 'webeeblocksStudent'
    }
  }));

  try {
    var module = await import('https://cyberbotics.com/wwi/R2025a/RobotWindow.js');
    robotWindow = new module.default();
    runtimeBackend = new WebeeBlocksWwiBackend(robotWindow, {timeoutMs: 35000});
    robotWindow.receive = receiveMessage;
    setRuntimeStatus('INITIALISATION', 'Attente du Runtime v2');
    await runtimeBackend.waitUntilReady();
    document.getElementById('submit').disabled = false;
    setRuntimeStatus('PRÊT', 'Runtime v2 connecté');
  } catch (error) {
    console.error(error);
    setRuntimeStatus('ERREUR', error && error.message ? error.message : 'Connexion Robot Window impossible');
  }
};

document.getElementById('submit').onclick = runProgram;
