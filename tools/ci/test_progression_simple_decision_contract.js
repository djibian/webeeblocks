'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));

const profile = Profiles.resolveById(Activities.DOCUMENT, 'progression-simple-decision-v1', Activities.BLOCK_CATALOG);
const runtimeProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
assert.strictEqual(profile.world, runtimeProfile.world);
assert.strictEqual(profile.brief.title, '4 — Franchir une porte mobile');
assert.strictEqual(profile.brief.mission,
  'Une porte mobile protège l’accès à la zone de livraison. Après la zone bleue de contrôle, deux passages sont balisés et la porte en ferme un au départ. Fais franchir au drone le passage resté ouvert puis rejoindre la zone d’arrivée et terminer posé, sans toucher la porte ni les obstacles, quelle que soit la position de la porte.');
assert.strictEqual(profile.brief.goal, profile.brief.mission);
assert.strictEqual(profile.pedagogy.objective,
  'Mesurer la distance devant le drone au point de décision, la comparer à un seuil et choisir un itinéraire avec une condition simple en réutilisant les paramètres de déplacement.');
assert.notStrictEqual(profile.brief.mission, profile.pedagogy.objective);
assert.doesNotMatch(profile.brief.mission, /utilise|mesure|compare|condition|bloc|algorithme/i,
  'student mission must describe the problem rather than prescribe the solution');
assert.match(profile.brief.mission, /deux passages sont balisés[\s\S]*passage resté ouvert/,
  'student mission must make the evaluator route gates explicit observable mission objects');
assert.deepStrictEqual(profile.evaluation, {type:'mission-state-v1', oracle:'progression-simple-decision-v1'});
assert.deepStrictEqual(profile.toolbox, [
  'webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_range',
  'controls_if','logic_compare','math_number','webeeblocks_v2_land'
]);
assert.deepStrictEqual(profile.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front']);
assert.deepStrictEqual(profile.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
assert.deepStrictEqual(profile.parameterBounds.webeeblocks_v2_takeoff.HEIGHT, {min:0.5,max:1.0,step:0.1});
assert.deepStrictEqual(profile.parameterBounds.webeeblocks_v2_move.DISTANCE, {min:0.1,max:1.2,step:0.1});
assert.deepStrictEqual(profile.parameterBounds.math_number.NUM, {min:1,max:2,step:1});
assert.deepStrictEqual(profile.runtime.allowedStatementKinds, ['takeoff','move','if','land']);
assert.deepStrictEqual(profile.runtime.rangeDirections, ['front']);

const world = fs.readFileSync(path.join(ROOT, 'worlds/crazyflie_runtime_v2.wbt'), 'utf8');
assert.match(world, /WEBEEBLOCKS_SIMPLE_DECISION_MISSION_V1_BEGIN/);
assert.match(world, /WEBEEBLOCKS_SIMPLE_DECISION_PASSAGES_V1_BEGIN[\s\S]*WEBEEBLOCKS_SIMPLE_DECISION_PASSAGES_V1_END/);
assert.match(world, /translation 1\.30 0\.80 0\.002[\s\S]*geometry Box \{ size 0\.18 0\.18 0\.004 \}/,
  'forward passage gate must be visibly materialized at the evaluator route coordinate');
assert.match(world, /translation 1\.00 1\.10 0\.002[\s\S]*geometry Box \{ size 0\.18 0\.18 0\.004 \}/,
  'left passage gate must be visibly materialized at the evaluator route coordinate');
assert.match(world, /DEF ACTIVITY4_BARRIER Solid \{[\s\S]*name "Activity 4 mobile barrier"/);
assert.match(world, /translation 1\.40 1\.20 0\.002[\s\S]*baseColor 0\.10 0\.72 0\.28/,
  'Activity 4 destination must remain visibly materialized');
assert.match(world, /name "Progression simple decision evaluator"[\s\S]*"simple-decision-evaluator-v1"/);

const evaluator = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/progression_simple_decision_evaluator.c'), 'utf8');
assert.match(evaluator, /#define DECISION_ORACLE "progression-simple-decision-v1"/);
assert.match(evaluator, /#define DECISION_ROUTE_TOLERANCE 0\.09/);
assert.match(evaluator, /#define DECISION_FORWARD_ROUTE_X 1\.30/);
assert.match(evaluator, /#define DECISION_FORWARD_ROUTE_Y 0\.80/);
assert.match(evaluator, /#define DECISION_LEFT_ROUTE_X 1\.00/);
assert.match(evaluator, /#define DECISION_LEFT_ROUTE_Y 1\.10/);
assert.match(evaluator, /DECISION_FORWARD_BLOCKED\[3\] = \{1\.20, 0\.80/);
assert.match(evaluator, /DECISION_LEFT_BLOCKED\[3\] = \{1\.00, 1\.00/);
assert.match(evaluator, /active_attempt % 2ULL/,
  'the proof pair must deterministically alternate forward-blocked and forward-open attempts');
assert.match(evaluator, /wb_supervisor_field_set_sf_vec3f\(barrier_translation, barrier_position\)/);
assert.match(evaluator, /wb_supervisor_node_get_contact_points/);
assert.match(evaluator, /valid_route_seen/);
assert.match(evaluator, /wrong_route_seen/);
assert.match(evaluator, /DECISION_ORACLE[\s\S]*WEBEEBLOCKS_ACTIVITY_OUTCOME_V1/);
assert.doesNotMatch(evaluator, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'mission oracle must observe world behavior, never student solution shape');

const entry = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/runtime_entry.c'), 'utf8');
const makefile = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/Makefile'), 'utf8');
assert.match(entry, /simple-decision-evaluator-v1/);
assert.match(makefile, /progression_simple_decision_evaluator\.c/);

const probe = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/simple_decision_probe/simple_decision_probe.js'), 'utf8');
assert.match(probe, /WebeeBlocksInterpreter\.run/,
  'positive proof must exercise the shared interpreter rather than a task-specific executor');
assert.match(probe, /DECISION_BLOCKED_ACHIEVED/);
assert.match(probe, /DECISION_OPEN_ACHIEVED/);
assert.match(probe, /DECISION_HARDCODED_FORWARD_NOT_ACHIEVED/);
assert.match(probe, /DECISION_HARDCODED_LEFT_NOT_ACHIEVED/);
assert.match(probe, /DECISION_ALTERNATIVE_BLOCKED_ACHIEVED/);
assert.match(probe, /DECISION_ALTERNATIVE_OPEN_ACHIEVED/);
assert.match(probe, /DECISION_WRONG_DECISION_NOT_ACHIEVED/);
assert.match(probe, /DECISION_BYPASS_NOT_ACHIEVED/,
  'real-R2025a evidence must reject a collision-free destination bypass that skips the explicit passage gates');
assert.match(probe, /probeActivityMissionFailure/);
assert.match(probe, /OUTCOME_UNAVAILABLE/);

console.log('PASS Activity 4 contract: the two route gates are explicit world/mission objects, the mobile door creates one front-sensing binary decision, the oracle stays behavior-only, and deterministic cross-configuration plus bypass evidence is wired');
