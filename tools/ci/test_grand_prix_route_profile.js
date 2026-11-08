'use strict';
// Static profile + project-identity contract only; native GUI/mission not claimed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Projects = require('../../plugins/robot_windows/blockly/webeeblocks/project_files');

const variable = fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/setup.js', 'utf8');
const historical = fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js', 'utf8');
const html = fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html', 'utf8');

function load(source, catalog) {
  const context = {
    WebeeBlocksActivities: {BLOCK_CATALOG: catalog, DOCUMENT: Activities.DOCUMENT},
    WebeeBlocksRuntimeOutcome: {classify: () => null},
    Blockly: {inject: (_element, options) => options},
    WebeeBlocksWwiBackend: function (_window, options) { this.options = options; }
  };
  context.window = context;
  vm.runInNewContext(source, context);
  const profile = Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,
    context.WebeeBlocksInitialActivityId, catalog);
  return {profile, context};
}

function run(loops) {
  const catalog = Object.assign({}, Activities.BLOCK_CATALOG);
  if (loops) catalog.controls_whileUntil = {category: 'control'};
  else delete catalog.controls_whileUntil;
  const a = load(variable, catalog);
  const u = load(historical, catalog);
  const profile = a.profile;
  assert.equal(profile.id, 'progression-grand-prix-route-v2');
  assert.equal(profile.world, 'worlds/grand_prix_route_v2.wbt');
  assert.equal(profile.evaluation.oracle, 'grand-prix-route-v2');
  assert.equal(profile.evaluation.type, 'mission-state-v1');
  assert.equal(a.context.WebeeBlocksInitialActivityId, profile.id);
  assert.equal(profile.toolbox.includes('controls_whileUntil'), loops);
  assert.equal(profile.runtime.maxSteps, 20000);
  assert.equal(JSON.stringify(profile.toolbox), JSON.stringify(u.profile.toolbox),
    'use the existing generic block vocabulary unchanged');
  assert.equal(JSON.stringify(profile.runtime), JSON.stringify(u.profile.runtime),
    'retain existing AST/preflight bounds and runtime policy');
  assert.equal(JSON.stringify(profile.parameterBounds), JSON.stringify(u.profile.parameterBounds));
  assert.equal(JSON.stringify(profile.fieldOptions), JSON.stringify(u.profile.fieldOptions));
  assert.equal(new a.context.WebeeBlocksWwiBackend({}, {}).options.simulationScenes, false);
  assert.equal(a.context.WebeeBlocksRuntimeOutcome.classify({code: 'TIME_LIMIT'}).state, 'MISSION ÉCHOUÉE');
  for (const forbidden of ['seed', 'lengths', 'turns', 'gates', 'course', 'route', 'identifier'])
    assert.equal(Object.hasOwn(profile, forbidden), false, 'host-only parameter: ' + forbidden);
  assert.equal(profile.brief.visible, true);
  assert.match(profile.brief.mission, /droite/);
  assert.match(profile.brief.mission, /210 secondes/);

  // The actual .wbb codec must store the stable activity identity only.
  // This is intentionally not a mock of native dialogs or a cross-world GUI test.
  const text = Projects.createStarterText(profile.id);
  const document = Projects.parseProject(text);
  assert.deepEqual(Object.keys(document.activity).sort(), ['id', 'semantics']);
  assert.equal(document.activity.id, profile.id);
  assert.equal(JSON.stringify(document).includes('gp-route-v2-L'), false);
  const options = {
    Blockly: {
      Workspace: class {
        getAllBlocks() { return []; }
        dispose() {}
      },
      serialization: {workspaces: {load(_data, workspace) { workspace.loaded = true; }}}
    },
    profiles: Profiles,
    activitiesDocument: a.context.WebeeBlocksActivities.DOCUMENT,
    blockCatalog: catalog,
    semanticAst: {compileWorkspace() { throw new Error('Crazyflie program must have exactly one top-level sequence'); }},
    activityContract: {preflightWorkspace() {}}
  };
  const checked = Projects.validateProjectText(text, profile, options);
  assert.equal(checked.profile.world, profile.world);
  assert.equal(checked.ast, null, 'an unfinished pupil starter remains editable');
  assert.throws(() => Projects.validateProjectText(text, {...profile, world: 'worlds/grand_prix_u_seed4.wbt'}, options),
    /incompatible with the current Webots world/);
  const injected = JSON.parse(text);
  injected.activity.route = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2';
  assert.throws(() => Projects.parseProject(JSON.stringify(injected)), /unsupported fields/);
  assert.throws(() => Projects.validateProjectText(Projects.createStarterText(u.profile.id), profile, options),
    /exactly once/);
}


/*
 * #826: exercise the real .wbb codec + manager over two host-selected routes,
 * with an in-memory transport. This proves no OS dialog, native Webots scene,
 * pupil AST execution or mission result.
 */
async function proveSameFileAcrossHostRoutes() {
  const catalog = Object.assign({}, Activities.BLOCK_CATALOG);
  const {profile, context} = load(variable, catalog);
  const clone = value => JSON.parse(JSON.stringify(value));
  const empty = () => ({blocks: {languageVersion: 0, blocks: []}});
  class Workspace {
    constructor() { this.state = empty(); }
    clear() { this.state = empty(); }
    getAllBlocks() { return []; } // transport test, not Blockly preflight
    dispose() {}
  }
  const Blockly = {
    Workspace,
    serialization: {workspaces: {
      save(workspace) { return clone(workspace.state); },
      load(state, workspace) { workspace.state = clone(state); }
    }}
  };
  const dependencies = {
    Blockly, profiles: Profiles,
    activitiesDocument: context.WebeeBlocksActivities.DOCUMENT,
    blockCatalog: catalog,
    semanticAst: {
      compileWorkspace() {
        // An unfinished pupil sketch is editable and savable, not successful.
        throw new Error('Crazyflie program must have exactly one top-level sequence');
      }
    },
    activityContract: {
      preflightWorkspace() {},
      applyFieldBounds() {}
    }
  };
  const handle = {name: 'programme-grand-prix.wbb'};
  const writes = [];
  let fileText = null;
  const transport = {
    nativeFileSystemAccess: true,
    async open() { return {handle, name: handle.name, text: fileText, mode: 'test'}; },
    async saveAs(name, text) {
      fileText = text;
      writes.push({operation: 'saveAs', name, handle});
      return {handle, name: handle.name, mode: 'test'};
    },
    async save(target, name, text) {
      assert.equal(target, handle, 'Save must preserve the exact selected handle');
      fileText = text;
      writes.push({operation: 'save', name, handle: target});
      return {handle: target, name: handle.name, mode: 'test'};
    },
    async release() {}
  };
  const makeManager = workspace => Projects.createManager({
    ...dependencies, workspace,
    getProfile() { return profile; },
    setProfile(next) { assert.equal(next.id, profile.id); },
    transport
  });
  const pupilSketch = {blocks: {languageVersion: 0, blocks: [{
    type: 'webeeblocks_v2_move', id: 'pupil-unfinished-move',
    fields: {DIRECTION: 'forward'},
    inputs: {DISTANCE: {shadow: {type: 'math_number', fields: {NUM: 0.3}}}}
  }]}};
  let hostRoute = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2';
  const editingWorkspace = new Workspace();
  editingWorkspace.state = clone(pupilSketch);
  const editing = makeManager(editingWorkspace);
  assert.equal(editing.hasCurrentTarget(), false);
  await editing.saveAs('programme-grand-prix');
  assert.equal(editing.hasCurrentTarget(), true);
  await editing.save();
  assert.deepEqual(writes.map(write => write.operation), ['saveAs', 'save']);
  const originalFile = fileText;
  const parsed = Projects.parseProject(originalFile);
  assert.deepEqual(Object.keys(parsed.activity).sort(), ['id', 'semantics']);
  assert.equal(parsed.activity.id, profile.id);
  assert.deepEqual(parsed.workspace, pupilSketch);
  assert(!originalFile.includes(hostRoute), 'host route leaked into the .wbb');

  // Change only the native host route; Open must consume identical project bytes.
  hostRoute = 'gp-route-v2-L3000-2000-2500-TDG-s5-H3';
  const reopenedWorkspace = new Workspace();
  const reopened = makeManager(reopenedWorkspace);
  await reopened.open();
  assert.equal(reopened.hasCurrentTarget(), true);
  assert.deepEqual(reopenedWorkspace.state, pupilSketch);
  assert.equal(reopened.encodeCurrent(), originalFile);
  await reopened.save();
  assert.equal(fileText, originalFile, 'same-file Save changed an unchanged project');
  assert.deepEqual(writes.map(write => write.operation), ['saveAs', 'save', 'save']);
  assert(!fileText.includes(hostRoute), 'new host route leaked into .wbb on Save');

  // Reopening a historical U file must not silently replace the variable world.
  const historicalProfile = load(historical, catalog).profile;
  fileText = Projects.createStarterText(historicalProfile.id);
  await assert.rejects(() => reopened.open(), /exactly once/);
  assert.deepEqual(reopenedWorkspace.state, pupilSketch);
  assert.equal(reopened.hasCurrentTarget(), true);
  fileText = originalFile;
}


/* #826/#905: a real Runtime-v2 diagnostic must be readable AFTER the
 * interpreter's finish callback; this is a DOM/JS test, not a Webots GUI PASS. */
async function proveRouteTechnicalDiagnostics() {
  const events = new Map();
  const rows = {
    runtimeState: {textContent: 'EXÉCUTION'},
    debugState: {textContent: 'En pause'}
  };
  const context = {
    WebeeBlocksActivities: {BLOCK_CATALOG: Activities.BLOCK_CATALOG, DOCUMENT: Activities.DOCUMENT},
    WebeeBlocksRuntimeOutcome: {classify() { return {state: 'ERREUR'}; }},
    Blockly: {inject() {}},
    WebeeBlocksWwiBackend: function() {},
    addEventListener(name, fn) { events.set(name, fn); },
    document: {getElementById(id) { return rows[id] || null; }}
  };
  context.window = context;
  vm.runInNewContext(variable, context);
  const listener = events.get('webeeblocks-runtime-v2-diagnostic');
  assert.equal(typeof listener, 'function', 'Grand Prix diagnostic listener is missing');
  const flush = () => new Promise(resolve => setImmediate(resolve));

  // Event arrives before generic Runtime-v2 state, and onFinish may overwrite
  // the debug text synchronously. A deferred diagnostic must win only on ERREUR.
  listener({detail: {studentState: 'ERREUR', machineCode: null,
    technicalMessage: 'WWI timeout id=129 command=LAND'}});
  rows.debugState.textContent = 'Observation terminée';
  rows.runtimeState.textContent = 'ERREUR';
  await flush();
  assert.equal(rows.debugState.textContent, 'Diagnostic : WWI timeout id=129 command=LAND');

  rows.debugState.textContent = 'Observation inactive';
  rows.runtimeState.textContent = 'PRÊT';
  listener({detail: {studentState: 'ERREUR', machineCode: 'BACKEND_FAILURE',
    technicalMessage: 'old technical error'}});
  await flush();
  assert.equal(rows.debugState.textContent, 'Observation inactive',
    'a late diagnostic must not contaminate a fresh RESET');

  rows.runtimeState.textContent = 'ARRÊTÉ';
  listener({detail: {studentState: 'ARRÊTÉ', machineCode: 'USER_STOPPED',
    technicalMessage: 'stopped by user'}});
  await flush();
  assert.equal(rows.debugState.textContent, 'Observation inactive',
    'a voluntary stop must not display a technical failure');

  rows.runtimeState.textContent = 'ERREUR';
  listener({detail: {studentState: 'ERREUR', machineCode: 'E\\nCODE',
    technicalMessage: '  line 1\\n  line 2 '.repeat(50)}});
  await flush();
  assert(rows.debugState.textContent.startsWith('Diagnostic : E nCODE — line 1 line 2 '));
  assert(rows.debugState.textContent.length <= 'Diagnostic : '.length + 40 + 3 + 240);
  assert(!rows.debugState.textContent.includes('\\n'),
    'diagnostic must remain one bounded visible line');
}

run(false);
run(true);
for (const id of ['projectActivity', 'projectOpen', 'projectSave', 'projectSaveAs',
  'stepMode', 'stepNext', 'stepContinue', 'resetSimulation']) {
  assert(html.includes('id="' + id + '"'), 'UI element missing: ' + id);
}
assert(html.includes('src="setup.js"'));
assert(html.includes('../blockly_v2/main.js'));
assert(!html.includes('grand_prix_u'));
Promise.all([proveSameFileAcrossHostRoutes(), proveRouteTechnicalDiagnostics()]).then(() => {
  console.log('PASS isolated Grand Prix variable profile: stable .wbb world, generic blocks, unfinished same-file Save/Open across host routes');
}).catch(error => { console.error(error); process.exitCode = 1; });
