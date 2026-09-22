'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Blockly = require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const SemanticAst = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));
const ActivityContract = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const ProjectFiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/project_files.js'));

const p1 = Profiles.resolveById(Activities.DOCUMENT, 'progression-sequence-v1', Activities.BLOCK_CATALOG);
const initialProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
assert.strictEqual(p1.world, 'worlds/crazyflie_runtime_obstacle.wbt');
assert.strictEqual(p1.world, initialProfile.world,
  'embedded Start activity must preserve the shared project/world compatibility tag');
assert.strictEqual(p1.brief.title, '1 — Rejoindre la zone d’arrivée');
assert.strictEqual(p1.brief.goal,
  'Le drone part de la zone bleue. Sa mission est de terminer posé dans la zone verte, avant l’obstacle rouge.');
assert.strictEqual(p1.pedagogy.objective,
  'Construire et ordonner une première séquence d’actions paramétrées pour atteindre un état final observable.');
assert.notStrictEqual(p1.brief.goal, p1.pedagogy.objective,
  'student mission must remain distinct from the internal pedagogical objective');
assert.deepStrictEqual(p1.evaluation, {type:'mission-state-v1', oracle:'progression-sequence-v1'});
assert.deepStrictEqual(p1.toolbox,
  ['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_land']);
assert.deepStrictEqual(p1.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward']);

const remainingProgression = Activities.DOCUMENT.activities.filter(profile =>
  profile.id.startsWith('progression-') && profile.id !== 'progression-sequence-v1');
assert.strictEqual(remainingProgression.length, 7);
remainingProgression.forEach(profile => {
  assert.strictEqual(profile.evaluation.type, 'training-objective',
    profile.id + ' must remain explicitly unaccepted until redesigned on its own evidence');
});

const missingPedagogy = JSON.parse(JSON.stringify(p1));
delete missingPedagogy.pedagogy;
assert.throws(() => Profiles.validateProfile(missingPedagogy, Activities.BLOCK_CATALOG),
  /mission-state-v1 requires pedagogy/);
const missingOracle = JSON.parse(JSON.stringify(p1));
delete missingOracle.evaluation.oracle;
assert.throws(() => Profiles.validateProfile(missingOracle, Activities.BLOCK_CATALOG),
  /evaluation\.oracle must be a non-empty string/);

const mainSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');
const projectUiSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
assert.doesNotMatch(mainSource, /pedagogy\.objective/,
  'internal pedagogical objective must not be rendered by the student Runtime header');
assert.doesNotMatch(projectUiSource, /pedagogy\.objective/,
  'internal pedagogical objective must not be rendered when applying an activity profile');
assert.match(mainSource, /runtimeProfile\.brief\.goal/);
assert.match(projectUiSource, /profile\.brief\.goal/);
assert.match(projectUiSource,
  /createStarterText\(profile\.id\)[\s\S]*manager\.openTemplateText\(starterName, starterText\)/,
  'Démarrer une activité must use embedded starter bytes rather than the OS project picker');

const worldSource = fs.readFileSync(path.resolve(__dirname, '../../worlds/crazyflie_runtime_v2.wbt'), 'utf8');
assert.match(worldSource, /WEBEEBLOCKS_SEQUENCE_MISSION_V1_BEGIN/);
assert.match(worldSource, /name "Crazyflie WebeeBlocks"/);
assert.match(worldSource, /name "Progression sequence evaluator"[\s\S]*controller "crazyflie_runtime_v2"[\s\S]*"sequence-evaluator-v1"/);
const runtimeEntrySource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'), 'utf8');
assert.match(runtimeEntrySource, /sequence-evaluator-v1/);
assert.match(runtimeEntrySource, /webeeblocks_progression_sequence_evaluator_main/);
const evaluatorSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/progression_sequence_evaluator.c'), 'utf8');
assert.match(evaluatorSource, /WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1/);
assert.match(evaluatorSource, /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s/);
assert.match(evaluatorSource, /progression-sequence-v1/);
assert.doesNotMatch(evaluatorSource, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'world evaluator must not inspect Blockly or expected solution shape');

async function exerciseEmbeddedStartActivityPath() {
  const workspace = new Blockly.Workspace();
  const profileRef = {value: initialProfile};
  const transportState = {opens:0, writes:0, releases:0};
  const transport = {
    nativeFileSystemAccess: true,
    async open() {
      transportState.opens += 1;
      throw new Error('embedded Start activity must not open the OS project picker');
    },
    async saveAs() {
      transportState.writes += 1;
      throw new Error('embedded Start activity must not save implicitly');
    },
    async save() {
      transportState.writes += 1;
      throw new Error('embedded Start activity must not save implicitly');
    },
    async release() { transportState.releases += 1; }
  };
  const manager = ProjectFiles.createManager({
    Blockly,
    profiles: Profiles,
    activitiesDocument: Activities.DOCUMENT,
    blockCatalog: Activities.BLOCK_CATALOG,
    semanticAst: SemanticAst,
    activityContract: ActivityContract,
    workspace,
    getProfile: () => profileRef.value,
    setProfile: profile => { profileRef.value = profile; },
    transport
  });

  try {
    assert.strictEqual(profileRef.value.id, 'reactive-obstacle-v2');
    assert.strictEqual(manager.hasCurrentTarget(), false);
    const starterText = ProjectFiles.createStarterText(p1.id);
    const result = await manager.openTemplateText(p1.id + '.wbb', starterText);
    assert.strictEqual(result.mode, 'embedded');
    assert.strictEqual(profileRef.value.id, p1.id,
      'embedded Activity 1 starter must apply from the initial Runtime profile');
    assert.strictEqual(profileRef.value.world, initialProfile.world);
    assert.strictEqual(manager.hasCurrentTarget(), false,
      'starting an activity must deliberately leave no current save target');
    assert.strictEqual(manager.currentName(), null);
    assert.strictEqual(transportState.opens, 0,
      'embedded Start activity unexpectedly reached the OS project picker');
    assert.strictEqual(transportState.writes, 0,
      'embedded Start activity unexpectedly persisted project bytes');
    assert.strictEqual(workspace.getAllBlocks(false).length, 0,
      'empty embedded starter must remain an empty student workspace');
  } finally {
    workspace.dispose();
  }
}

(async function() {
  await exerciseEmbeddedStartActivityPath();
  console.log('PASS first progression activity keeps the shared Start-activity world binding, executes the embedded project-manager path without an OS picker/save target, separates student mission from pedagogy, and binds a distinct world-state evaluator process without accepting later profiles');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
