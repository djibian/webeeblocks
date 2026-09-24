'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));

const profile = Profiles.resolveById(Activities.DOCUMENT, 'progression-combined-decisions-v1', Activities.BLOCK_CATALOG);
const runtimeProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
assert.strictEqual(profile.world, runtimeProfile.world);
assert.strictEqual(profile.brief.title, '6 — Choisir une sortie sûre au carrefour');
assert.strictEqual(profile.brief.mission,
  'À chaque carrefour de l’entrepôt, plusieurs passages peuvent être libres ou occupés. Fais rejoindre au drone la zone de sortie puis termine posé, sans entrer dans un passage bloqué ni toucher un obstacle.');
assert.strictEqual(profile.pedagogy.objective,
  'Acquérir plusieurs distances directionnelles et combiner des comparaisons et conditions afin que le déplacement choisi dépende de plusieurs observations de l’environnement.');
assert.notStrictEqual(profile.brief.mission, profile.pedagogy.objective);
assert.doesNotMatch(profile.brief.mission, /capteur|mesure|compare|condition|si alors|imbri|boolé|algorithme/i,
  'student mission must describe the warehouse problem rather than prescribe decision logic');
assert.deepStrictEqual(profile.evaluation, {type:'mission-state-v1', oracle:'progression-combined-decisions-v1'});
assert.deepStrictEqual(profile.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front','left','right']);
assert.deepStrictEqual(profile.runtime.rangeDirections, ['front','left','right']);
assert.ok(profile.toolbox.includes('logic_operation'), 'Activity 6 must retain the cumulative Boolean composition surface');
assert.ok(profile.toolbox.includes('controls_repeat_ext'), 'Activity 6 must preserve earlier repetition capability');
assert.deepStrictEqual(profile.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left','right'],
  'the three visible junction corridors must all be authorable with the already-generic movement primitive');
assert.deepStrictEqual(profile.runtime.moveDirections, ['forward','left','right']);

const project = JSON.parse(fs.readFileSync(path.join(ROOT, 'activities/progression/06-multi-perception.wbb'), 'utf8'));
assert.strictEqual(project.activity.id, 'progression-combined-decisions-v1');
assert.deepStrictEqual(project.workspace.blocks.blocks, []);

const world = fs.readFileSync(path.join(ROOT, 'worlds/crazyflie_runtime_v2.wbt'), 'utf8');
assert.match(world, /WEBEEBLOCKS_COMBINED_DECISIONS_MISSION_V1_BEGIN[\s\S]*WEBEEBLOCKS_COMBINED_DECISIONS_MISSION_V1_END/);
assert.match(world, /DEF ACTIVITY6_FRONT_BARRIER Solid/);
assert.match(world, /DEF ACTIVITY6_LEFT_BARRIER Solid/);
assert.match(world, /DEF ACTIVITY6_RIGHT_BARRIER Solid/);
const routeMarkers = world.match(/WEBEEBLOCKS_COMBINED_DECISIONS_ROUTES_V1_BEGIN([\s\S]*?)WEBEEBLOCKS_COMBINED_DECISIONS_ROUTES_V1_END/);
assert.ok(routeMarkers, 'Activity 6 must materialize its visible route-marker group');
assert.match(routeMarkers[1], /translation 1\.70 -0\.60 0\.002/,
  'the evaluator forward checkpoint must have a visible route marker in the isolated junction');
assert.match(routeMarkers[1], /translation 1\.40 -0\.30 0\.002/,
  'the evaluator left checkpoint must have a visible route marker in the isolated junction');
assert.match(routeMarkers[1], /translation 1\.40 -0\.90 0\.002/,
  'the evaluator right checkpoint must have a visible route marker in the isolated junction');
assert.match(world, /name "Progression combined decisions evaluator"[\s\S]*"combined-decisions-evaluator-v1"/);

const evaluator = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/progression_combined_decisions_evaluator.c'), 'utf8');
assert.match(evaluator, /#define COMBINED_ORACLE "progression-combined-decisions-v1"/);
assert.match(evaluator, /#define COMBINED_FORWARD_ROUTE_X 1\.70\s*\n#define COMBINED_FORWARD_ROUTE_Y -0\.60/,
  'forward evaluator checkpoint must stay bound to the visible forward route marker');
assert.match(evaluator, /#define COMBINED_LEFT_ROUTE_X 1\.40\s*\n#define COMBINED_LEFT_ROUTE_Y -0\.30/,
  'left evaluator checkpoint must stay bound to the visible left route marker');
assert.match(evaluator, /#define COMBINED_RIGHT_ROUTE_X 1\.40\s*\n#define COMBINED_RIGHT_ROUTE_Y -0\.90/,
  'right evaluator checkpoint must stay bound to the visible right route marker');
assert.match(evaluator, /COMBINED_ROUTE_FORWARD/);
assert.match(evaluator, /COMBINED_ROUTE_LEFT/);
assert.match(evaluator, /COMBINED_ROUTE_RIGHT/,
  'at least one deterministic configuration must make the visible right corridor the valid continuation');
assert.match(evaluator, /right_blocked/);
assert.match(evaluator, /wb_supervisor_node_get_contact_points/);
assert.match(evaluator, /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1/);
assert.doesNotMatch(evaluator, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'Activity 6 mission oracle must observe world behavior, never student solution shape');

const entry = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/runtime_entry.c'), 'utf8');
const makefile = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/Makefile'), 'utf8');
assert.match(entry, /combined-decisions-evaluator-v1/);
assert.match(makefile, /progression_combined_decisions_evaluator\.c/);

console.log('PASS Activity 6 contract: the student sees a behavior-only warehouse junction mission with three authorable directional perceptions and three movement corridors, while the evaluator remains independent of Blockly solution shape');
