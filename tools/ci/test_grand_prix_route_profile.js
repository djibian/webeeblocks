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

run(false);
run(true);
for (const id of ['projectActivity', 'projectOpen', 'projectSave', 'projectSaveAs',
  'stepMode', 'stepNext', 'stepContinue', 'resetSimulation']) {
  assert(html.includes('id="' + id + '"'), 'UI element missing: ' + id);
}
assert(html.includes('src="setup.js"'));
assert(html.includes('../blockly_v2/main.js'));
assert(!html.includes('grand_prix_u'));
console.log('PASS isolated Grand Prix variable profile: stable .wbb world, generic blocks, safe incomplete starter');
