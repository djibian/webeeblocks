'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities.js');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js');

const p1 = Profiles.resolveById(Activities.DOCUMENT, 'progression-sequence-v1', Activities.BLOCK_CATALOG);
assert.strictEqual(p1.world, 'worlds/crazyflie_runtime_v2.wbt');
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

const worldSource = fs.readFileSync(path.resolve(__dirname, '../../worlds/crazyflie_runtime_v2.wbt'), 'utf8');
assert.match(worldSource, /WEBEEBLOCKS_SEQUENCE_MISSION_V1_BEGIN/);
assert.match(worldSource, /DEF CRAZYFLIE Crazyflie/);
assert.match(worldSource, /controller "progression_sequence_evaluator"/);
const evaluatorSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/progression_sequence_evaluator/progression_sequence_evaluator.c'), 'utf8');
assert.match(evaluatorSource, /WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1/);
assert.match(evaluatorSource, /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s/);
assert.match(evaluatorSource, /progression-sequence-v1/);
assert.doesNotMatch(evaluatorSource, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'world evaluator must not inspect Blockly or expected solution shape');

console.log('PASS first progression activity separates student mission from pedagogy and binds a world-state mission oracle without accepting later profiles');
