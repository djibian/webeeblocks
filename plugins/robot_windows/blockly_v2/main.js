var runtimeProfile = null;
var workspace = null;
var robotWindow = null;
var runtimeBackend = null;
var runtimeRunning = false;
var runtimeTerminal = false;

function setRuntimeStatus(state, detail) {
  document.getElementById('runtimeState').textContent = state;
  document.getElementById('runtimeDetail').textContent = detail || '';
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2', {
    detail: {state: state, detail: detail || null}
  }));
}

function categoryLabel(category) {
  if (category === 'flight') return 'Vol';
  if (category === 'sensor') return 'Capteurs';
  return 'Contrôle';
}

function categoryColour(category) {
  if (category === 'flight') return 20;
  if (category === 'sensor') return 60;
  return 240;
}

function buildToolbox(profile) {
  var toolbox = document.createElement('xml');
  var groups = {flight: [], sensor: [], control: []};
  profile.toolbox.forEach(function(type) {
    var definition = WebeeBlocksActivities.BLOCK_CATALOG[type];
    groups[(definition && definition.category) || 'control'].push(type);
  });
  ['flight', 'sensor', 'control'].forEach(function(category) {
    if (!groups[category].length) return;
    var categoryNode = document.createElement('category');
    categoryNode.setAttribute('name', categoryLabel(category));
    categoryNode.setAttribute('colour', categoryColour(category));
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
    WebeeBlocksActivityContract.preflightWorkspace(runtimeProfile, workspace);
    WebeeBlocksActivityContract.applyFieldBounds(runtimeProfile, workspace);
    var ast = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    var facts = WebeeBlocksActivityContract.preflightAst(runtimeProfile, ast);
    WebeeBlocksActivityContract.preflightBackend(runtimeProfile, facts, runtimeBackend);
    window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-ast', {detail: ast}));

    runtimeRunning = true;
    setRuntimeStatus('EN VOL', 'Programme réactif en cours');
    await WebeeBlocksInterpreter.run(ast, runtimeBackend, {maxSteps: 1000});
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

window.onload = async function() {
  runtimeProfile = WebeeBlocksActivityProfiles.resolveById(
    WebeeBlocksActivities.DOCUMENT,
    'reactive-obstacle-v2',
    WebeeBlocksActivities.BLOCK_CATALOG
  );
  document.getElementById('activityTitle').textContent = runtimeProfile.brief.title;
  document.getElementById('activityGoal').textContent = runtimeProfile.brief.goal;
  workspace = Blockly.inject('blocklyDiv', {
    toolbox: buildToolbox(runtimeProfile),
    scrollbars: true,
    media: 'vendor/media/'
  });
  workspace.addChangeListener(onWorkspaceChange);
  window.addEventListener('resize', function() { Blockly.svgResize(workspace); });

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
