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
assert.strictEqual(p1.brief.title, '1 — Livrer le colis');
assert.strictEqual(p1.brief.mission,
  'Un petit colis doit être transféré de la base de départ vers la zone d’arrivée. Fais terminer le drone posé et immobile dans la zone d’arrivée.');
assert.strictEqual(p1.brief.goal, p1.brief.mission,
  'legacy goal compatibility must preserve the redesigned student mission');
assert.strictEqual(p1.pedagogy.objective,
  'Construire et comprendre une séquence ordonnée d’actions.');
assert.notStrictEqual(p1.brief.mission, p1.pedagogy.objective,
  'student mission must remain distinct from the internal pedagogical objective');
assert.deepStrictEqual(p1.evaluation, {type:'mission-state-v1', oracle:'progression-sequence-v1'});
assert.deepStrictEqual(p1.toolbox,
  ['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_land']);
assert.deepStrictEqual(p1.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward']);
assert.deepStrictEqual(p1.parameterBounds.webeeblocks_v2_takeoff.HEIGHT,
  {min:0.5,max:0.5,step:0.1},
  'Activity 1 takeoff parameter must be non-discriminating so sequencing remains the new concept');
assert.deepStrictEqual(p1.parameterBounds.webeeblocks_v2_move.DISTANCE,
  {min:0.1,max:0.1,step:0.1},
  'Activity 1 movement parameter must be fixed; precision belongs to Activity 2');
assert.deepStrictEqual(p1.runtime.astBounds['takeoff.height_m'], {min:0.5,max:0.5});
assert.deepStrictEqual(p1.runtime.astBounds['move.distance_m'], {min:0.1,max:0.1});

const remainingProgression = Activities.DOCUMENT.activities.filter(profile =>
  profile.id.startsWith('progression-') && profile.id !== 'progression-sequence-v1');
assert.strictEqual(remainingProgression.length, 7);
remainingProgression.forEach(profile => {
  assert.strictEqual(profile.evaluation.type, 'training-objective',
    profile.id + ' must remain explicitly unaccepted until redesigned on its own evidence');
  assert.strictEqual(profile.brief.mission, undefined,
    profile.id + ' must remain on the legacy goal-only representation until redesigned');
});

const missingMission = JSON.parse(JSON.stringify(p1));
delete missingMission.brief.mission;
assert.throws(() => Profiles.validateProfile(missingMission, Activities.BLOCK_CATALOG),
  /brief\.mission must be a non-empty string/);
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
assert.match(projectUiSource, /profile\.brief\.mission\s*\|\|\s*profile\.brief\.goal/,
  'redesigned activity mission must be rendered with legacy goal fallback');
assert.match(projectUiSource,
  /createStarterText\(profile\.id\)[\s\S]*manager\.openTemplateText\(starterName, starterText\)/,
  'Démarrer une activité must use embedded starter bytes rather than the OS project picker');

const worldSource = fs.readFileSync(path.resolve(__dirname, '../../worlds/crazyflie_runtime_v2.wbt'), 'utf8');
assert.match(worldSource, /WEBEEBLOCKS_SEQUENCE_MISSION_V1_BEGIN/);
assert.match(worldSource, /name "Crazyflie WebeeBlocks"/);
assert.match(worldSource, /name "Progression sequence evaluator"[\s\S]*controller "crazyflie_runtime_v2"[\s\S]*"sequence-evaluator-v1"/);
const runtimeEntrySource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/runtime_entry.c'), 'utf8');
assert.match(runtimeEntrySource, /sequence-evaluator-v1/);
assert.match(runtimeEntrySource, /webeeblocks_progression_sequence_evaluator_main/);
const runtimeMakefileSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/Makefile'), 'utf8');
assert.match(runtimeMakefileSource, /-Dmain=webeeblocks_runtime_flight_main/,
  'mission dispatcher must preserve the canonical Runtime-v2 source file while renaming its native entry point at compile time');
const evaluatorSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/progression_sequence_evaluator.c'), 'utf8');
assert.match(evaluatorSource, /WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1/);
assert.match(evaluatorSource, /WEBEEBLOCKS_ACTIVITY_COMPLETION_V1/,
  'world evaluator must bind terminal judgement to the exact mission completion marker');
assert.match(evaluatorSource, /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s/);
assert.match(evaluatorSource, /progression-sequence-v1/);
assert.match(evaluatorSource, /WEBEEBLOCKS_SEQUENCE_TIMEOUT/,
  'a rejected completed attempt must preserve enough world-state evidence to diagnose the bounded oracle');
assert.doesNotMatch(evaluatorSource, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'world evaluator must not inspect Blockly or expected solution shape');
const receivingPad = worldSource.match(
  /translation (0\.25) 0 0\.002[\s\S]*?baseColor 0\.10 0\.72 0\.28[\s\S]*?geometry Box \{ size ([0-9.]+) ([0-9.]+) 0\.004 \}/);
assert.ok(receivingPad, 'Activity 1 visible green receiving pad geometry must remain explicit');
const targetX = evaluatorSource.match(/#define SEQUENCE_TARGET_X ([0-9.]+)/);
const targetXTolerance = evaluatorSource.match(/#define SEQUENCE_TARGET_X_TOLERANCE ([0-9.]+)/);
const targetYTolerance = evaluatorSource.match(/#define SEQUENCE_TARGET_Y_TOLERANCE ([0-9.]+)/);
assert.ok(targetX && targetXTolerance && targetYTolerance,
  'Activity 1 evaluator target geometry must remain explicit');
const padCenterX = Number(receivingPad[1]);
const padWidth = Number(receivingPad[2]);
const padDepth = Number(receivingPad[3]);
assert.strictEqual(Number(targetX[1]), padCenterX,
  'Activity 1 X target must match the visible receiving-pad center');
assert.strictEqual(Number(targetXTolerance[1]), padWidth / 2,
  'Activity 1 X acceptance must match the visible receiving-pad half-width');
assert.strictEqual(Number(targetYTolerance[1]), padDepth / 2,
  'Activity 1 Y acceptance must match the visible receiving-pad half-depth');

const flightRuntimeSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'), 'utf8');
const positionTolerance = flightRuntimeSource.match(/#define POSITION_TOL ([0-9.]+)/);
assert.ok(positionTolerance, 'Runtime movement completion tolerance must remain explicit');
const moveDistance = p1.parameterBounds.webeeblocks_v2_move.DISTANCE.min;
const moveTolerance = Number(positionTolerance[1]);
const targetMinX = padCenterX - padWidth / 2;
const targetMaxX = padCenterX + padWidth / 2;
const twoMoveConservativeLower = 2 * (moveDistance - moveTolerance);
const twoMoveConservativeUpper = 2 * (moveDistance + moveTolerance);
assert.ok(targetMinX <= twoMoveConservativeLower - 0.01 + Number.EPSILON,
  'visible arrival zone must leave margin below a valid two-move sequence despite cumulative Runtime movement completion tolerance');
assert.ok(targetMaxX >= twoMoveConservativeUpper + 0.01 - Number.EPSILON,
  'visible arrival zone must leave margin above a valid two-move sequence despite cumulative Runtime movement completion tolerance');

const sequenceProbeSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/sequence_probe/sequence_probe.js'), 'utf8');
assert.match(sequenceProbeSource, /completeActivityMission\(evaluation\)/,
  'real-Webots sequence probe must cross the integrated execution-completion boundary');
assert.match(sequenceProbeSource, /SEQUENCE_REPEAT_ACHIEVED/,
  'real-Webots proof must repeat the canonical valid sequence to expose completion/landing races');
assert.match(sequenceProbeSource, /SEQUENCE_ALTERNATIVE_ACHIEVED/,
  'real-Webots proof must accept a second valid sequence shape with the same observable outcome');
assert.match(sequenceProbeSource,
  /await backend\.move\('forward', 0\.1\);\n    await backend\.land\(\);\n    await backend\.takeoff\(0\.5\);\n    await backend\.move\('forward', 0\.1\);\n    await backend\.land\(\);\n    await backend\.completeActivityMission\(evaluation\);/,
  'alternative real-Webots proof must change the valid action sequence without adding a third cumulative move tolerance');
assert.match(sequenceProbeSource, /move\('forward', 0\.1\)/,
  'real-Webots proof must exercise the fixed movement parameter exposed by Activity 1');

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
    assert.strictEqual(profileRef.value.brief.mission, p1.brief.mission,
      'embedded Activity 1 starter must apply the explicit student mission field');
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
  console.log('PASS first progression activity preserves Start-activity compatibility, explicit student mission/pedagogy separation, fixed non-discriminating parameters, tolerance-aware visible-pad-aligned world-state evaluation, reset freshness, repeated valid execution, and multiple valid sequence shapes without accepting later profiles');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
