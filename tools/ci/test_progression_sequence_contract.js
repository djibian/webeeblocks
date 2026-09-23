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
const p2 = Profiles.resolveById(Activities.DOCUMENT, 'progression-precise-movement-v1', Activities.BLOCK_CATALOG);
const initialProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
assert.strictEqual(p1.world, initialProfile.world);
assert.strictEqual(p2.world, initialProfile.world);
assert.strictEqual(p1.brief.title, '1 — Livrer le colis');
assert.strictEqual(p2.brief.title, '2 — Livrer le colis fragile');
assert.strictEqual(p2.brief.mission,
  'Un colis fragile doit être déposé sur la petite zone de livraison située à gauche du couloir. Fais terminer le drone posé et immobile entièrement dans cette zone, sans toucher l’obstacle rouge.');
assert.strictEqual(p2.brief.goal, p2.brief.mission,
  'legacy presentation compatibility must derive from the authoritative student mission');
assert.strictEqual(p2.pedagogy.objective,
  'Choisir et ajuster les paramètres de déplacement pour obtenir un déplacement précis en réutilisant une séquence ordonnée.');
assert.notStrictEqual(p2.brief.mission, p2.pedagogy.objective);
assert.deepStrictEqual(p2.evaluation, {type:'mission-state-v1', oracle:'progression-precise-movement-v1'});
assert.deepStrictEqual(p2.toolbox, ['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_land']);
assert.deepStrictEqual(p2.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
assert.deepStrictEqual(p2.parameterBounds.webeeblocks_v2_takeoff.HEIGHT, {min:0.5,max:0.5,step:0.1});
assert.deepStrictEqual(p2.parameterBounds.webeeblocks_v2_move.DISTANCE, {min:0.1,max:0.6,step:0.1});
assert.deepStrictEqual(p2.runtime.astBounds['takeoff.height_m'], {min:0.5,max:0.5});
assert.deepStrictEqual(p2.runtime.astBounds['move.distance_m'], {min:0.1,max:0.6});

const remainingProgression = Activities.DOCUMENT.activities.filter(profile =>
  profile.id.startsWith('progression-') &&
  profile.id !== 'progression-sequence-v1' &&
  profile.id !== 'progression-precise-movement-v1' &&
  profile.id !== 'progression-repeat-v1' &&
  profile.id !== 'progression-simple-decision-v1');
assert.strictEqual(remainingProgression.length, 4);
remainingProgression.forEach(profile => {
  assert.strictEqual(profile.evaluation.type, 'training-objective');
  assert.strictEqual(profile.brief.mission, undefined);
});

for (const missionProfile of [p1, p2]) {
  const missingMission = JSON.parse(JSON.stringify(missionProfile));
  delete missingMission.brief.mission;
  assert.throws(() => Profiles.validateProfile(missingMission, Activities.BLOCK_CATALOG), /brief\.mission must be a non-empty string/);
  const missingPedagogy = JSON.parse(JSON.stringify(missionProfile));
  delete missingPedagogy.pedagogy;
  assert.throws(() => Profiles.validateProfile(missingPedagogy, Activities.BLOCK_CATALOG), /mission-state-v1 requires pedagogy/);
  const missingOracle = JSON.parse(JSON.stringify(missionProfile));
  delete missingOracle.evaluation.oracle;
  assert.throws(() => Profiles.validateProfile(missingOracle, Activities.BLOCK_CATALOG), /evaluation\.oracle must be a non-empty string/);
}

const mainSource = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/blockly_v2/main.js'), 'utf8');
const projectUiSource = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
assert.doesNotMatch(mainSource, /pedagogy\.objective/);
assert.doesNotMatch(projectUiSource, /pedagogy\.objective/);
assert.match(projectUiSource, /profile\.brief\.mission\s*\|\|\s*profile\.brief\.goal/);
assert.match(projectUiSource, /createStarterText\(profile\.id\)[\s\S]*manager\.openTemplateText\(starterName, starterText\)/);

const worldSource = fs.readFileSync(path.join(ROOT, 'worlds/crazyflie_runtime_v2.wbt'), 'utf8');
assert.match(worldSource, /WEBEEBLOCKS_SEQUENCE_MISSION_V1_BEGIN/);
assert.match(worldSource, /WEBEEBLOCKS_PRECISE_MOVEMENT_MISSION_V1_BEGIN/);
assert.match(worldSource, /name "Progression sequence evaluator"[\s\S]*"sequence-evaluator-v1"/);
assert.match(worldSource, /name "Progression precise movement evaluator"[\s\S]*"precise-evaluator-v1"/);

const preciseEvaluatorSource = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/progression_precise_evaluator.c'), 'utf8');
assert.match(preciseEvaluatorSource, /progression-precise-movement-v1/);
assert.match(preciseEvaluatorSource, /wb_supervisor_node_get_contact_points/);
assert.match(preciseEvaluatorSource, /WEBEEBLOCKS_PRECISE_COLLISION/);
assert.match(preciseEvaluatorSource, /collision_seen[\s\S]*precise_publish_outcome\(custom_data, active_attempt, "not-achieved"\)/,
  'red-obstacle contact must remain an observable terminal mission failure even if Runtime fail-safe interrupts normal completion');
assert.doesNotMatch(preciseEvaluatorSource, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/);

const sequencePad = worldSource.match(
  /translation (0\.25) 0 0\.002[\s\S]*?baseColor 0\.10 0\.72 0\.28[\s\S]*?geometry Box \{ size ([0-9.]+) ([0-9.]+) 0\.004 \}/);
assert.ok(sequencePad, 'Activity 1 visible receiving pad must remain explicit');
const sequencePadX = Number(sequencePad[1]);
const sequencePadW = Number(sequencePad[2]);
const sequencePadD = Number(sequencePad[3]);

const precisePad = worldSource.match(
  /WEBEEBLOCKS_PRECISE_MOVEMENT_MISSION_V1_BEGIN[\s\S]*?translation (0\.30) (0\.40) 0\.002[\s\S]*?baseColor 0\.92 0\.72 0\.10[\s\S]*?geometry Box \{ size ([0-9.]+) ([0-9.]+) 0\.004 \}/);
assert.ok(precisePad, 'Activity 2 small visible delivery zone must remain explicit');
const precisePadX = Number(precisePad[1]);
const precisePadY = Number(precisePad[2]);
const precisePadW = Number(precisePad[3]);
const precisePadD = Number(precisePad[4]);
assert.ok(precisePadW < sequencePadW && precisePadD < sequencePadD,
  'Activity 2 target must be materially smaller than Activity 1 target');
const sequenceYMax = sequencePadD / 2;
const preciseYMin = precisePadY - precisePadD / 2;
assert.ok(preciseYMin > sequenceYMax,
  'Activity 2 visible target must be disjoint from the Activity 1 receiving pad');

function numberDefine(source, name) {
  const match = source.match(new RegExp('#define ' + name + ' ([0-9.]+)'));
  assert.ok(match, 'missing evaluator constant ' + name);
  return Number(match[1]);
}
const preciseX = numberDefine(preciseEvaluatorSource, 'PRECISE_TARGET_X');
const preciseY = numberDefine(preciseEvaluatorSource, 'PRECISE_TARGET_Y');
const preciseXTol = numberDefine(preciseEvaluatorSource, 'PRECISE_TARGET_X_TOLERANCE');
const preciseYTol = numberDefine(preciseEvaluatorSource, 'PRECISE_TARGET_Y_TOLERANCE');
const visibleHalf = numberDefine(preciseEvaluatorSource, 'PRECISE_VISIBLE_TARGET_HALF_EXTENT');
const bodyClearance = numberDefine(preciseEvaluatorSource, 'PRECISE_BODY_CLEARANCE');
assert.strictEqual(preciseX, precisePadX);
assert.strictEqual(preciseY, precisePadY);
assert.strictEqual(visibleHalf, precisePadW / 2);
assert.strictEqual(precisePadW, precisePadD);
assert.ok(Math.abs(preciseXTol - (visibleHalf - bodyClearance)) < 1e-12,
  'Activity 2 X acceptance must equal visible half-extent minus body clearance');
assert.ok(Math.abs(preciseYTol - (visibleHalf - bodyClearance)) < 1e-12,
  'Activity 2 Y acceptance must equal visible half-extent minus body clearance');
assert.ok(bodyClearance >= 0.046,
  'whole-craft success must reserve at least the approximate Crazyflie half-span inside the visible zone');
assert.ok(preciseXTol >= 0.06 && preciseYTol >= 0.06,
  'precision target must retain comfortable deterministic landing margin rather than become a simulator-noise lesson');

const sequenceProbeSource = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/sequence_probe/sequence_probe.js'), 'utf8');
assert.match(sequenceProbeSource, /PRECISE_UNDERSHOOT_NOT_ACHIEVED/);
assert.match(sequenceProbeSource, /PRECISE_OVERSHOOT_NOT_ACHIEVED/);
assert.match(sequenceProbeSource, /PRECISE_LATERAL_NOT_ACHIEVED/);
assert.match(sequenceProbeSource, /PRECISE_COLLISION_NOT_ACHIEVED/);
assert.match(sequenceProbeSource, /PRECISE_ALTERNATIVE_ACHIEVED/);
assert.match(sequenceProbeSource, /collisionError\.code !== 'UNSAFE_OR_TIMEOUT'/,
  'real collision proof must preserve Runtime fail-safe semantics while still observing mission failure');
assert.match(sequenceProbeSource,
  /move\('left', 0\.4\)[\s\S]*move\('forward', 0\.5\)[\s\S]*PRECISE_OVERSHOOT_NOT_ACHIEVED/,
  'overshoot proof must avoid the red obstacle first and then land beyond the precise target');

const runtimeEntrySource = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/runtime_entry.c'), 'utf8');
const runtimeMakefileSource = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/Makefile'), 'utf8');
assert.match(runtimeEntrySource, /precise-evaluator-v1/);
assert.match(runtimeMakefileSource, /progression_precise_evaluator\.c/);

async function exerciseEmbeddedStartActivityPath(profile) {
  const workspace = new Blockly.Workspace();
  const profileRef = {value: initialProfile};
  const transportState = {opens:0, writes:0};
  const transport = {
    nativeFileSystemAccess: true,
    async open() { transportState.opens += 1; throw new Error('embedded Start activity must not open OS picker'); },
    async saveAs() { transportState.writes += 1; throw new Error('embedded Start activity must not save implicitly'); },
    async save() { transportState.writes += 1; throw new Error('embedded Start activity must not save implicitly'); },
    async release() {}
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
    setProfile: next => { profileRef.value = next; },
    transport
  });
  try {
    const starterText = ProjectFiles.createStarterText(profile.id);
    const result = await manager.openTemplateText(profile.id + '.wbb', starterText);
    assert.strictEqual(result.mode, 'embedded');
    assert.strictEqual(profileRef.value.id, profile.id);
    assert.strictEqual(profileRef.value.world, initialProfile.world);
    assert.strictEqual(manager.hasCurrentTarget(), false);
    assert.strictEqual(transportState.opens, 0);
    assert.strictEqual(transportState.writes, 0);
  } finally {
    workspace.dispose();
  }
}

(async function() {
  await exerciseEmbeddedStartActivityPath(p1);
  await exerciseEmbeddedStartActivityPath(p2);
  console.log('PASS progression Activities 1 and 2 preserve embedded start, mission/pedagogy separation, whole-craft visible precision, disjoint targets, solution-shape independence and complete Activity-2 evidence contract');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
