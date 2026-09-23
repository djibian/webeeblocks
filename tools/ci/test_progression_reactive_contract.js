'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));

const profile = Profiles.resolveById(Activities.DOCUMENT, 'progression-reactive-v1', Activities.BLOCK_CATALOG);
const runtimeProfile = Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG);
assert.strictEqual(profile.world, runtimeProfile.world);
assert.strictEqual(profile.brief.title, '5 — Traverser les rangées');
assert.strictEqual(profile.brief.mission,
  'Le drone doit traverser plusieurs rangées de l’entrepôt pour rejoindre la zone de livraison. Des colis peuvent bloquer certaines rangées. Fais-le avancer jusqu’à la zone d’arrivée et terminer posé sans toucher de colis, même si les blocages ne sont pas les mêmes d’une rangée à l’autre.');
assert.strictEqual(profile.brief.goal, profile.brief.mission);
assert.match(profile.brief.mission, /traverser plusieurs rangées/,
  'the student mission must make crossing the visible warehouse rows part of success');
assert.strictEqual(profile.pedagogy.objective,
  'Répéter un cycle de mesure, décision et déplacement afin de réobserver la situation avant chaque rangée, en réutilisant les acquis des activités précédentes.');
assert.notStrictEqual(profile.brief.mission, profile.pedagogy.objective);
assert.doesNotMatch(profile.brief.mission, /répète|mesure|capteur|condition|si alors|boucle|algorithme/i,
  'student mission must describe the problem rather than prescribe the solution');
assert.deepStrictEqual(profile.evaluation, {type:'mission-state-v1', oracle:'progression-reactive-v1'});
assert.deepStrictEqual(profile.toolbox, [
  'webeeblocks_v2_takeoff','webeeblocks_v2_move','controls_repeat_ext','math_number',
  'webeeblocks_v2_range','controls_if','logic_compare','webeeblocks_v2_land'
]);
assert.deepStrictEqual(profile.fieldOptions.webeeblocks_v2_range.DIRECTION, ['front']);
assert.deepStrictEqual(profile.fieldOptions.webeeblocks_v2_move.DIRECTION, ['forward','left']);
assert.deepStrictEqual(profile.runtime.allowedStatementKinds, ['takeoff','move','repeat','if','land']);
assert.deepStrictEqual(profile.runtime.rangeDirections, ['front']);
assert.deepStrictEqual(profile.runtime.moveDirections, ['forward','left']);
assert.deepStrictEqual(profile.runtime.astBounds['repeat.count'], {min:1,max:10});

const project = JSON.parse(fs.readFileSync(path.join(ROOT, 'activities/progression/05-reactive.wbb'), 'utf8'));
assert.strictEqual(project.activity.id, 'progression-reactive-v1');
assert.deepStrictEqual(project.workspace.blocks.blocks, []);

const world = fs.readFileSync(path.join(ROOT, 'worlds/crazyflie_runtime_v2.wbt'), 'utf8');
const floorMatch = world.match(/Floor\s*\{\s*size\s+([0-9.]+)\s+([0-9.]+)\s*\}/);
assert.ok(floorMatch, 'the shared Runtime v2 world must declare an explicit rectangular floor');
const floorWidth = Number(floorMatch[1]);
const floorHeight = Number(floorMatch[2]);
assert.deepStrictEqual([floorWidth, floorHeight], [4, 4],
  'the shared source floor literal must stay compatible with the existing offline classroom and physical localizers');
const floorHalfX = floorWidth / 2;
const floorHalfY = floorHeight / 2;
const activity5LandingBodyMargin = 0.08;
const activity5LandingHalfExtent = 0.12;
const activity5LandingX = 1.80;
const activity5LandingY = 2.20;
const activity5LandingMinX = activity5LandingX - activity5LandingHalfExtent - activity5LandingBodyMargin;
const activity5LandingMaxX = activity5LandingX + activity5LandingHalfExtent + activity5LandingBodyMargin;
const activity5LandingMinY = activity5LandingY - activity5LandingHalfExtent - activity5LandingBodyMargin;
const activity5LandingMaxY = activity5LandingY + activity5LandingHalfExtent + activity5LandingBodyMargin;
assert.ok(activity5LandingMaxX <= floorHalfX,
  'the complete Activity 5 landing footprint plus craft margin must remain inside the canonical floor on X');
assert.ok(activity5LandingMinY >= floorHalfY - 1e-9,
  'the overflow landing footprint must begin at the canonical floor boundary rather than leaving a physical gap');
assert.match(world,
  /WEBEEBLOCKS_REACTIVE_FLOOR_EXTENSION_V1_BEGIN[\s\S]*DEF ACTIVITY5_FLOOR_EXTENSION Solid \{[\s\S]*translation 1\.25 2\.25 -0\.025[\s\S]*geometry Box \{ size 1\.5 0\.5 0\.05 \}[\s\S]*boundingObject Box \{ size 1\.5 0\.5 0\.05 \}[\s\S]*WEBEEBLOCKS_REACTIVE_FLOOR_EXTENSION_V1_END/,
  'Activity 5 must explicitly materialize the bounded physical floor extension required by its retained upper landing state');
const extensionCenterX = 1.25;
const extensionCenterY = 2.25;
const extensionHalfX = 1.5 / 2;
const extensionHalfY = 0.5 / 2;
assert.ok(activity5LandingMinX >= extensionCenterX - extensionHalfX &&
          activity5LandingMaxX <= extensionCenterX + extensionHalfX,
  'the Activity 5 floor extension must support the complete landing footprint plus craft margin on X');
assert.ok(activity5LandingMinY >= extensionCenterY - extensionHalfY - 1e-9 &&
          activity5LandingMaxY <= extensionCenterY + extensionHalfY + 1e-9,
  'the Activity 5 floor extension must support the complete landing footprint plus craft margin on Y');
assert.match(world, /WEBEEBLOCKS_REACTIVE_MISSION_V1_BEGIN/);
assert.match(world, /WEBEEBLOCKS_REACTIVE_ROW_CHECKPOINTS_V1_BEGIN[\s\S]*WEBEEBLOCKS_REACTIVE_ROW_CHECKPOINTS_V1_END/);
assert.match(world, /translation 1\.20 1\.75 0\.002[\s\S]*translation 1\.50 1\.90 0\.002[\s\S]*translation 1\.80 2\.05 0\.002/,
  'all evaluator row checkpoints must be represented by visible warehouse-row mission objects');
assert.match(world, /DEF ACTIVITY5_BARRIER_1 Solid/);
assert.match(world, /DEF ACTIVITY5_BARRIER_2 Solid/);
assert.match(world, /DEF ACTIVITY5_BARRIER_3 Solid/);
assert.match(world, /translation 1\.80 1\.90 0\.002[\s\S]*translation 1\.80 2\.20 0\.002/,
  'both deterministic arrival zones must be visible mission objects');
assert.match(world, /name "Progression reactive evaluator"[\s\S]*"reactive-evaluator-v1"/);

const evaluator = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/progression_reactive_evaluator.c'), 'utf8');
assert.match(evaluator, /#define REACTIVE_ORACLE "progression-reactive-v1"/);
assert.match(evaluator, /#define REACTIVE_PATTERN_COUNT 4/);
assert.match(evaluator, /#define REACTIVE_OPEN_BARRIER_Z -1\.00/,
  'open Activity 5 rows must park their physical parcel below the shared navigable world');
assert.match(evaluator, /\{1, 0, 1\}, \/\* B-O-B \*\//);
assert.match(evaluator, /\{0, 1, 0\}, \/\* O-B-O \*\//);
assert.match(evaluator, /\{1, 1, 0\}, \/\* B-B-O: same first row as B-O-B, different later row \*\//);
assert.match(evaluator, /\{0, 0, 1\}  \/\* O-O-B: same first row as O-B-O, different later row \*\//,
  'retained deterministic patterns must include same-first-observation variants so the first row cannot identify later blockages');
assert.match(evaluator, /normalized % REACTIVE_PATTERN_COUNT/);
assert.match(evaluator,
  /barrier_positions\[row\]\[1\] = y;[\s\S]*barrier_positions\[row\]\[2\] = blocked\[row\] \? REACTIVE_BARRIER_Z : REACTIVE_OPEN_BARRIER_Z;/,
  'open-row parcels must be removed vertically instead of being parked in another XY lane that can interfere with another shared-world activity');
assert.match(evaluator,
  /fabs\(point\[2\] - barrier\[2\]\) <= REACTIVE_BARRIER_HALF_HEIGHT \+ CONTACT_TOLERANCE/,
  'collision attribution must follow the actual barrier Z so below-floor inactive parcels cannot alias ordinary floor contacts');
assert.match(evaluator, /checkpoint_index == REACTIVE_ROWS/);
assert.match(evaluator, /wb_supervisor_node_get_contact_points/);
assert.match(evaluator, /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1/);
assert.match(evaluator,
  /reactive_parse_failure_probe\(data, &failure_attempt\) && failure_attempt == active_attempt && collision_seen/,
  'failure probing must only synthesize not-achieved from irreversible collision evidence');
assert.doesNotMatch(evaluator, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'mission oracle must observe world behavior, never student solution shape');

const entry = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/runtime_entry.c'), 'utf8');
const makefile = fs.readFileSync(path.join(ROOT, 'controllers/crazyflie_runtime_v2/Makefile'), 'utf8');
assert.match(entry, /reactive-evaluator-v1/);
assert.match(makefile, /progression_reactive_evaluator\.c/);

const probe = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/reactive_probe/reactive_probe.js'), 'utf8');
assert.match(probe, /WebeeBlocksInterpreter\.run/);
assert.match(probe, /kind:'repeat', count:3/);
assert.match(probe, /frontBlockedCondition\(\)/);
assert.match(probe,
  /proveFailureProbeUnavailableWithoutCollision[\s\S]*readActivityOutcome\(evaluation\)[\s\S]*sleep\(120\)[\s\S]*probeActivityMissionFailure\(evaluation\)/,
  'the real-Webots no-collision failure probe must first expose the current attempt marker long enough for the evaluator to latch it');
assert.match(probe, /REACTIVE_BOB_ACHIEVED/);
assert.match(probe, /REACTIVE_OBO_ACHIEVED/);
assert.match(probe, /REACTIVE_BBO_ACHIEVED/);
assert.match(probe, /REACTIVE_OOB_ACHIEVED/,
  'the repeated fresh-sensing program must cover every retained deterministic pattern');
assert.match(probe, /singleObservationPatternProgram\(\)/);
assert.match(probe, /REACTIVE_SINGLE_OBSERVATION_BOB_ACHIEVED/);
assert.match(probe, /REACTIVE_SINGLE_OBSERVATION_OBO_ACHIEVED/);
assert.match(probe, /REACTIVE_SINGLE_OBSERVATION_BBO_NOT_ACHIEVED/,
  'one initial observation may solve the two reference patterns but must fail a later-different pattern with the same first observation');
assert.match(probe, /REACTIVE_FIXED_FORWARD_NOT_ACHIEVED/);
assert.match(probe, /REACTIVE_FIXED_LEFT_NOT_ACHIEVED/);
assert.match(probe, /REACTIVE_UNROLLED_OBO_ACHIEVED/,
  'behavior-only evidence must accept an equivalent unrolled program that refreshes sensing at every row');
assert.match(probe, /rowBypassProgram\(\)[\s\S]*REACTIVE_BYPASS_BBO_NOT_ACHIEVED/,
  'real evidence must reject a collision-free route that reaches the arrival without traversing the visible warehouse rows');
assert.match(probe, /OUTCOME_UNAVAILABLE/);

console.log('PASS Activity 5 contract: four deterministic warehouse patterns prevent first-observation pattern inference, repeated fresh sensing succeeds across all patterns, a single-observation route fails when a later row changes, fixed and row-bypass behavior fail, equivalent unrolled fresh sensing succeeds, failure probing stays collision-scoped, inactive open-row parcels are removed below the shared navigable world, the bounded floor extension physically supports the retained upper landing without changing the canonical 4x4 floor localization contract, and the oracle remains behavior-only');
