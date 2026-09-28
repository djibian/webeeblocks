'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));

const p7 = Profiles.resolveById(Activities.DOCUMENT, 'progression-memory-v1', Activities.BLOCK_CATALOG);
const p8 = Profiles.resolveById(Activities.DOCUMENT, 'progression-autonomous-strategy-v1', Activities.BLOCK_CATALOG);

assert.strictEqual(p8.brief.title, '8 — Assurer une livraison autonome complète');
assert.strictEqual(p8.brief.mission,
  'Prends en charge le colis au quai de départ, puis fais rejoindre au drone la bonne zone de livraison en autonomie. Le trajet peut comporter des passages occupés et plusieurs choix de route. Les informations disponibles au départ et pendant le trajet doivent lui permettre de choisir une stratégie adaptée. Termine posé dans la zone correspondant au colis, sans toucher d’obstacle.');
assert.strictEqual(p8.pedagogy.objective,
  'Concevoir, tester et affiner une stratégie autonome en sélectionnant et combinant les mécanismes acquis dans les activités précédentes selon leur utilité.');
assert.notStrictEqual(p8.brief.mission, p8.pedagogy.objective);
assert.deepStrictEqual(p8.evaluation, {type:'mission-state-v1', oracle:'progression-autonomous-strategy-v1'});
assert.deepStrictEqual(p8.toolbox, p7.toolbox, 'Activity 8 must synthesize the cumulative Activity 7 toolbox without introducing a new primitive');
assert.deepStrictEqual(p8.parameterBounds, p7.parameterBounds, 'Activity 8 must not introduce new parameter surfaces');
assert.deepStrictEqual(p8.fieldOptions, p7.fieldOptions, 'Activity 8 must preserve the learned movement/sensing directions');
assert.deepStrictEqual(p8.hardware, p7.hardware, 'Activity 8 must require no new hardware capability');
assert.deepStrictEqual(p8.runtime.allowedStatementKinds, p7.runtime.allowedStatementKinds, 'Activity 8 must not introduce a new runtime statement kind');
assert.deepStrictEqual(p8.runtime.rangeDirections, p7.runtime.rangeDirections, 'Activity 8 must not introduce a new sensing direction');
assert.deepStrictEqual(p8.runtime.moveDirections, p7.runtime.moveDirections, 'Activity 8 must not introduce a new movement direction');
assert.deepStrictEqual(p8.runtime.verticalDirections, p7.runtime.verticalDirections, 'Activity 8 must not introduce vertical movement');
assert.deepStrictEqual(p8.runtime.astBounds, p7.runtime.astBounds, 'Activity 8 must preserve learned runtime bounds');
for (const type of ['controls_repeat_ext','webeeblocks_v2_range','controls_if','logic_compare','logic_operation','variables_set','variables_get'])
  assert.ok(p8.toolbox.includes(type), 'Activity 8 missing learned strategy surface: ' + type);

const project = JSON.parse(fs.readFileSync(path.join(ROOT, 'activities/progression/08-autonomous-strategy.wbb'), 'utf8'));
assert.strictEqual(project.activity.id, 'progression-autonomous-strategy-v1');
assert.deepStrictEqual(project.workspace.blocks.blocks, []);

const evaluator = fs.readFileSync(
  path.join(ROOT, 'controllers/crazyflie_runtime_v2/progression_autonomous_evaluator.c'), 'utf8');
assert.match(evaluator, /#define AUTONOMOUS_ORACLE "progression-autonomous-strategy-v1"/);
assert.match(evaluator, /AUTONOMOUS_PATTERN_COUNT 4/);
assert.match(evaluator, /small-BE-forward/);
assert.match(evaluator, /large-EB-left/);
assert.match(evaluator, /small-BB-right/);
assert.match(evaluator, /large-EE-forward/);
assert.match(evaluator, /#define AUTONOMOUS_CENTER_Y -2\.50/);
assert.match(evaluator, /#define AUTONOMOUS_LEFT_Y -2\.15/);
assert.match(evaluator, /#define AUTONOMOUS_RIGHT_Y -2\.85/);
assert.match(evaluator, /ACTIVITY8_ROW1_DETOUR_PAD Pose \{ translation 0\.50 -2\.15/);
assert.match(evaluator, /ACTIVITY8_ROW2_DETOUR_PAD Pose \{ translation 0\.80 -2\.15/);
assert.match(evaluator, /ACTIVITY8_LEFT_ROUTE_PAD Pose \{ translation 1\.10 -2\.15/);
assert.match(evaluator, /ACTIVITY8_RIGHT_ROUTE_PAD Pose \{ translation 1\.10 -2\.85/);
assert.match(evaluator, /ACTIVITY8_SMALL_DELIVERY_PAD Pose \{ translation 1\.40 -2\.15/);
assert.match(evaluator, /ACTIVITY8_LARGE_DELIVERY_PAD Pose \{ translation 1\.40 -2\.85/);
assert.match(evaluator, /ACTIVITY8_FLOOR_EXTENSION/);
assert.match(evaluator, /ACTIVITY8_PARCEL_REFERENCE/);
assert.match(evaluator, /ACTIVITY8_REFERENCE_MASK/);
assert.match(evaluator, /#define AUTONOMOUS_REFERENCE_SMALL_X 1\.15/);
assert.match(evaluator, /#define AUTONOMOUS_REFERENCE_LARGE_X 0\.25/);
assert.match(evaluator, /#define AUTONOMOUS_REFERENCE_HIDE_X 0\.40/);
assert.match(evaluator, /reference_x = pattern->small_parcel \? AUTONOMOUS_REFERENCE_SMALL_X : AUTONOMOUS_REFERENCE_LARGE_X/);
assert.match(evaluator, /wb_supervisor_field_set_sf_vec3f\(reference_translation, hidden_reference\)/);
assert.match(evaluator, /wb_supervisor_field_set_sf_vec3f\(reference_mask_translation, visible_mask\)/);
assert.doesNotMatch(evaluator, /ACTIVITY7_REFERENCE_PANEL|MEMORY_PATTERN/,
  'Activity 8 parcel evidence must be owned by Activity 8 rather than coupled to Activity 7');
assert.match(evaluator, /ACTIVITY8_ROW1_CENTER_BARRIER/);
assert.match(evaluator, /ACTIVITY8_ROW2_CENTER_BARRIER/);
assert.match(evaluator, /ACTIVITY8_JUNCTION_FRONT_BARRIER/);
assert.match(evaluator, /ACTIVITY8_JUNCTION_LEFT_BARRIER/);
assert.match(evaluator, /ACTIVITY8_JUNCTION_RIGHT_BARRIER/);
assert.match(evaluator, /ACTIVITY8_SMALL_DELIVERY_PAD/);
assert.match(evaluator, /ACTIVITY8_LARGE_DELIVERY_PAD/);
assert.match(evaluator, /reference_unavailable/);
assert.match(evaluator, /row_progress == 2/);
assert.match(evaluator, /junction_valid_route_seen/);
assert.match(evaluator, /in_final_bay/);
assert.match(evaluator, /wb_supervisor_node_get_contact_points/);
assert.match(evaluator, /WEBEEBLOCKS_AUTONOMOUS_COLLISION/);
assert.match(evaluator, /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1/);
assert.doesNotMatch(evaluator, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'Activity 8 oracle must inspect only observable world behavior, never student solution shape');

const world = fs.readFileSync(path.join(ROOT, 'worlds/crazyflie_runtime_v2.wbt'), 'utf8');
assert.match(world,
  /WEBEEBLOCKS_AUTONOMOUS_EVALUATOR_V1_BEGIN[\s\S]*name "Progression autonomous strategy evaluator"[\s\S]*"autonomous-evaluator-v1"[\s\S]*WEBEEBLOCKS_AUTONOMOUS_EVALUATOR_V1_END/);

const entry = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/runtime_entry.c'), 'utf8');
const makefile = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/Makefile'), 'utf8');
assert.match(entry, /webeeblocks_progression_autonomous_evaluator_main/);
assert.match(entry, /"autonomous-evaluator-v1"/);
assert.match(makefile, /progression_autonomous_evaluator\.c/);

const visualPrep = fs.readFileSync(path.join(ROOT, 'tools/ci/prepare_color_led_visual_render.py'), 'utf8');
assert.match(visualPrep, /WEBEEBLOCKS_AUTONOMOUS_EVALUATOR_V1_BEGIN/);
assert.match(visualPrep, /Progression autonomous strategy evaluator/);
assert.match(visualPrep, /autonomous-evaluator-v1/);

const probe = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/autonomous_probe/autonomous_probe.js'), 'utf8');
assert.match(probe, /function integratedStrategy\(\)/);
assert.match(probe, /kind:'repeat', count:2/);
assert.match(probe, /kind:'set_variable'/);
assert.match(probe, /range\('front'\)/);
assert.match(probe, /clear\('left'\)/);
assert.match(probe, /function alternativeStrategy\(\)/);
assert.match(probe, /kind:'arithmetic'/);
assert.match(probe, /rightFirstJunctionDecision/);
assert.match(probe, /function fixedRouteShortcut\(\)/);
assert.match(probe, /function noMemoryShortcut\(\)/);
assert.match(probe, /function reachRowsWithoutMemory\(\)/);
assert.match(probe, /function noMemoryShortcut\(\)[\s\S]*?reachRowsWithoutMemory\(\)/,
  'no-memory counterexample must genuinely omit departure storage');
assert.match(probe, /function frontOnlyShortcut\(\)/);
assert.match(probe, /function incompleteProgram\(\)/);
assert.match(probe, /AUTONOMOUS_DEPARTURE_SMALL_RANGE/);
assert.match(probe, /AUTONOMOUS_DEPARTURE_LARGE_RANGE/);
assert.match(probe, /departureEvidence\.parcel === 'small'[\s\S]*departureRange > 1\.0/);
assert.match(probe, /departureEvidence\.parcel === 'large'[\s\S]*departureRange < 1\.0/);

const reactiveRowSource = probe.slice(
  probe.indexOf('function reactiveRow()'), probe.indexOf('function forwardJunctionRoute()'));
const leftJunctionSource = probe.slice(
  probe.indexOf('function leftJunctionRoute()'), probe.indexOf('function rightJunctionRoute()'));
const rightJunctionSource = probe.slice(
  probe.indexOf('function rightJunctionRoute()'), probe.indexOf('function frontLeftJunctionDecision()'));
const deliverySource = probe.slice(
  probe.indexOf('function rememberedDelivery(condition)'), probe.indexOf('function completeProgram('));
assert.match(reactiveRowSource, /direction:'left', distance_m:0\.35[\s\S]*direction:'right', distance_m:0\.35/,
  'Activity 8 row detour witness must stay aligned with the widened 0.35 m side lane');
assert.match(leftJunctionSource, /direction:'left', distance_m:0\.35[\s\S]*direction:'right', distance_m:0\.35/,
  'Activity 8 left-route witness must stay aligned with the widened 0.35 m side lane');
assert.match(rightJunctionSource, /direction:'right', distance_m:0\.35[\s\S]*direction:'left', distance_m:0\.35/,
  'Activity 8 right-route witness must stay aligned with the widened 0.35 m side lane');
assert.match(deliverySource, /direction:'left', distance_m:0\.35[\s\S]*direction:'right', distance_m:0\.35/,
  'Activity 8 delivery witness must stay aligned with the widened 0.35 m final bays');

assert.match(probe, /AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_FIXED_ROUTE_NOT_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_NO_MEMORY_LARGE_NOT_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_FRONT_ONLY_RIGHT_NOT_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_INCOMPLETE_NOT_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_ALT_SMALL_BE_FORWARD_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_ALT_LARGE_EB_LEFT_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_ALT_SMALL_BB_RIGHT_ACHIEVED/);
assert.match(probe, /AUTONOMOUS_ALT_LARGE_EE_FORWARD_ACHIEVED/);

const runner = fs.readFileSync(path.join(ROOT, 'tools/ci/run_progression_autonomous_mission.py'), 'utf8');
assert.match(runner, /AUTONOMOUS_MISSION_TEST_COMPLETE/);
assert.match(runner, /AUTONOMOUS_DEPARTURE_SMALL_RANGE/);
assert.match(runner, /AUTONOMOUS_DEPARTURE_LARGE_RANGE/);
assert.match(runner, /small_range > 1\.0/);
assert.match(runner, /large_range < 1\.0/);
assert.match(runner, /reference_x=1\.150/);
assert.match(runner, /reference_x=0\.250/);
assert.match(runner, /reference_hidden=1 mask_x=0\.250/);
assert.match(runner, /WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=1 pattern=small-BE-forward/);
assert.match(runner, /WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=2 pattern=large-EB-left/);
assert.match(runner, /WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=3 pattern=small-BB-right/);
assert.match(runner, /WEBEEBLOCKS_AUTONOMOUS_ROUTE attempt=3 route=right valid=1/);
assert.match(runner, /WEBEEBLOCKS_AUTONOMOUS_TIMEOUT attempt=8/);
assert.match(runner, /fixed_route.*not-achieved/);
assert.match(runner, /no_memory.*not-achieved/);
assert.match(runner, /front_only.*not-achieved/);
assert.match(runner, /incomplete.*not-achieved/);

console.log('PASS Activity 8 contract: an explicit warehouse delivery mission owns its parcel signal and removes it after departure, synthesizes only previously learned mechanisms, accepts only observable world success, rejects fixed/no-memory/front-only/incomplete shortcuts, and admits a distinct valid stored-value strategy');