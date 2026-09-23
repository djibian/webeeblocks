'use strict';

const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const activities = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const profiles = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));

function fail(message) {
  console.error('FAIL progression repeat contract: ' + message);
  process.exit(1);
}
function assert(condition, message) {
  if (!condition) fail(message);
}

const profile = profiles.resolveById(activities.DOCUMENT, 'progression-repeat-v1', activities.BLOCK_CATALOG);
assert(profile.brief.title === '3 — Inspecter trois balises', 'student title drifted');
assert(typeof profile.brief.mission === 'string' && profile.brief.mission.includes('trois zones d\'inspection'), 'mission is not the settled three-beacon scenario');
assert(!/(boucle|répét|repeat|fois)/i.test(profile.brief.mission), 'mission prescribes repetition instead of the world creating it');
assert(profile.pedagogy && /répétition/i.test(profile.pedagogy.objective), 'internal repetition objective missing');
assert(profile.evaluation.type === 'mission-state-v1' && profile.evaluation.oracle === 'progression-repeat-v1', 'repeat mission-state oracle missing');
assert(profile.toolbox.includes('controls_repeat_ext'), 'repeat block not exposed');
assert(profile.toolbox.includes('webeeblocks_v2_takeoff') && profile.toolbox.includes('webeeblocks_v2_move') && profile.toolbox.includes('webeeblocks_v2_land'), 'Activities 1–2 prerequisites not reused');
assert(profile.parameterBounds.webeeblocks_v2_takeoff.HEIGHT.min === 0.5 && profile.parameterBounds.webeeblocks_v2_takeoff.HEIGHT.max === 0.5, 'takeoff height is not fixed');
assert(profile.fieldOptions.webeeblocks_v2_move.DIRECTION.join(',') === 'forward,left', 'unexpected movement directions');
assert(profile.runtime.allowedStatementKinds.includes('repeat'), 'repeat statement is not runtime-authorized');

const world = fs.readFileSync(path.join(root, 'worlds/crazyflie_runtime_v2.wbt'), 'utf8');
for (const marker of [
  'WEBEEBLOCKS_REPEAT_MISSION_V1_BEGIN',
  'WEBEEBLOCKS_REPEAT_EVALUATOR_V1_BEGIN',
  'Progression repeat beacon 1',
  'Progression repeat beacon 2',
  'Progression repeat beacon 3',
  'Progression repeat arrival',
  '"repeat-evaluator-v1"',
]) assert(world.includes(marker), 'missing world marker: ' + marker);
for (const coordinate of ['translation 0.20 0.60', 'translation 0.40 1.20', 'translation 0.60 1.80', 'translation 0.80 1.80'])
  assert(world.includes(coordinate), 'missing settled repeated-motif coordinate: ' + coordinate);

const evaluator = fs.readFileSync(path.join(root, 'controllers/crazyflie_runtime_v2/progression_repeat_evaluator.c'), 'utf8');
for (const token of [
  '#define REPEAT_ORACLE "progression-repeat-v1"',
  'REPEAT_BEACON_X[3] = {0.20, 0.40, 0.60}',
  'REPEAT_BEACON_Y[3] = {0.60, 1.20, 1.80}',
  '#define REPEAT_ARRIVAL_X 0.80',
  '#define REPEAT_ARRIVAL_Y 1.80',
  'WEBEEBLOCKS_REPEAT_ORDER_FAILURE',
  'repeat_publish_outcome(custom_data, active_attempt, "not-achieved")',
  'next_beacon == 3',
]) assert(evaluator.includes(token), 'evaluator contract drifted: ' + token);
assert(!/(Blockly|controls_repeat_ext|workspace|AST)/.test(evaluator), 'world oracle inspects solution representation');

const entry = fs.readFileSync(path.join(root, 'controllers/crazyflie_runtime_v2/runtime_entry.c'), 'utf8');
const makefile = fs.readFileSync(path.join(root, 'controllers/crazyflie_runtime_v2/Makefile'), 'utf8');
assert(entry.includes('repeat-evaluator-v1') && entry.includes('webeeblocks_progression_repeat_evaluator_main'), 'runtime entry does not dispatch repeat evaluator');
assert(makefile.includes('progression_repeat_evaluator.c'), 'repeat evaluator absent from Runtime build');

console.log('PASS progression repeat contract: mission/objective separation, cumulative toolbox, repeated world geometry, behavior-only oracle and Runtime dispatch');
