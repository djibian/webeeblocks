'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));

const p6 = Profiles.resolveById(Activities.DOCUMENT, 'progression-combined-decisions-v1', Activities.BLOCK_CATALOG);
const p7 = Profiles.resolveById(Activities.DOCUMENT, 'progression-memory-v1', Activities.BLOCK_CATALOG);

assert.strictEqual(p7.brief.title, '7 — Acheminer le colis selon son gabarit');
assert.strictEqual(p7.brief.mission,
  'Au quai de départ, le drone peut mesurer le gabarit du colis grâce au panneau de référence placé devant lui. Une fois parti, ce panneau ne sera plus visible. Plus loin, deux zones de tri doivent être franchies en choisissant à chaque fois le passage adapté au colis, puis le drone doit terminer posé dans la bonne zone de livraison.');
assert.strictEqual(p7.brief.cue, 'Une variable sera utile pour mémoriser la mesure faite au quai de départ.');
assert.strictEqual(p7.pedagogy.objective,
  'Capturer une mesure à un instant identifiable, la mémoriser puis réutiliser la valeur mémorisée dans au moins deux décisions ultérieures lorsque l’information d’origine n’est plus directement observable.');
assert.notStrictEqual(p7.brief.mission, p7.pedagogy.objective);
assert.deepStrictEqual(p7.evaluation, {type:'mission-state-v1', oracle:'progression-memory-v1'});
assert.ok(p6.toolbox.every(type => p7.toolbox.includes(type)), 'Activity 7 must preserve the cumulative Activity 6 toolbox');
for (const type of ['variables_set','variables_get','math_change','math_arithmetic'])
  assert.ok(p7.toolbox.includes(type), 'Activity 7 missing generic memory/arithmetic surface: ' + type);
assert.ok(p7.runtime.allowedStatementKinds.includes('set_variable'));
assert.deepStrictEqual(p7.runtime.rangeDirections, ['front','left','right']);
assert.deepStrictEqual(p7.runtime.moveDirections, ['forward','left','right']);

const project = JSON.parse(fs.readFileSync(path.join(ROOT, 'activities/progression/07-memory.wbb'), 'utf8'));
assert.strictEqual(project.activity.id, 'progression-memory-v1');
assert.deepStrictEqual(project.workspace.blocks.blocks, []);

const evaluator = fs.readFileSync(
  path.join(ROOT, 'controllers/crazyflie_runtime_v2/progression_combined_decisions_evaluator.c'), 'utf8');
assert.match(evaluator, /#define MEMORY_ORACLE "progression-memory-v1"/);
assert.match(evaluator, /MEMORY_PATTERNS[\s\S]*1\.25[\s\S]*small-far[\s\S]*0\.35[\s\S]*large-near/);
assert.match(evaluator, /ACTIVITY7_MEASUREMENT_PAD/);
assert.match(evaluator, /ACTIVITY7_REFERENCE_PANEL Solid/);
assert.match(evaluator, /ACTIVITY7_FIRST_SMALL_ROUTE/);
assert.match(evaluator, /ACTIVITY7_FIRST_LARGE_ROUTE/);
assert.match(evaluator, /ACTIVITY7_SECOND_SMALL_ROUTE/);
assert.match(evaluator, /ACTIVITY7_SECOND_LARGE_ROUTE/);
assert.match(evaluator, /ACTIVITY7_ARRIVAL_PAD/);
assert.match(evaluator, /wb_supervisor_field_import_mf_node_from_string/);
assert.match(evaluator, /MEMORY_PANEL_HIDDEN_Z/);
assert.match(evaluator, /memory_first_valid_route_seen/);
assert.match(evaluator, /memory_second_valid_route_seen/);
assert.match(evaluator, /WEBEEBLOCKS_MEMORY_REFERENCE_UNAVAILABLE/);
assert.match(evaluator, /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1/);
assert.doesNotMatch(evaluator, /Blockly|workspace|allowedStatementKinds|webeeblocks_v2_/,
  'Activity 7 mission oracle must observe world behavior, never student solution shape');

const probe = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/memory_probe/memory_probe.js'), 'utf8');
assert.match(probe, /kind:'set_variable'/);
assert.match(probe, /kind:'variable_get'/);
assert.match(probe, /smallFromFreshRange/);
assert.match(probe, /MEMORY_STORED_SMALL_ACHIEVED/);
assert.match(probe, /MEMORY_STORED_LARGE_ACHIEVED/);
assert.match(probe, /MEMORY_REREAD_LARGE_NOT_ACHIEVED/);
assert.match(probe, /MEMORY_ALT_SMALL_ACHIEVED/);
assert.match(probe, /MEMORY_ALT_LARGE_ACHIEVED/);

console.log('PASS Activity 7 contract: the student gets a complete parcel-gauge mission whose reference disappears before two observable sorting choices, while the oracle remains behavior-only and the generic variable surface stays cumulative');
