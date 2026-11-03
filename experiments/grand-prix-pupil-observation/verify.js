'use strict';
// Classroom starter only: prove that a real, deliberately incomplete .wbb
// can be opened, edited and serialized. No flight, oracle or pedagogical PASS.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '../..');
const Blockly = require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
global.Blockly = Blockly;
try {
  require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js'));
} finally { delete global.Blockly; }
const Semantic = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast'));
Semantic.installConditionalLoopBounds(Blockly);
const Contract = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_contract'));
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles'));
const Projects = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/project_files'));
const file = path.join(__dirname, 'Grand-Prix-U-demarrage-incomplet.wbb');
const source = fs.readFileSync(file, 'utf8');
const context = {
  Blockly, WebeeBlocksActivities: Activities, WebeeBlocksActivityProfiles: Profiles,
  WebeeBlocksRuntimeOutcome: {classify: () => ({})},
  WebeeBlocksWwiBackend: function() {}
};
context.window = context;
vm.runInNewContext(fs.readFileSync(
  path.join(ROOT, 'plugins/robot_windows/grand_prix_u/setup.js'), 'utf8'), context);
const profile = Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,
  'progression-grand-prix-u-v1', Activities.BLOCK_CATALOG);
// The Start-activity button must load precisely the same intentionally
// incomplete pupil artifact as manual Open, without a network fetch.
assert.strictEqual(typeof context.WebeeBlocksStarterForProfile, 'function');
assert.strictEqual(context.WebeeBlocksStarterForProfile(profile.id), source);
assert.strictEqual(context.WebeeBlocksStarterForProfile('progression-01'), null);
const deps = {
  Blockly, profiles: Profiles, activitiesDocument: context.WebeeBlocksActivities.DOCUMENT,
  blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Semantic, activityContract: Contract
};
const workspace = new Blockly.Workspace();
const reopened = new Blockly.Workspace();
try {
  const initial = JSON.parse(source);
  assert.deepStrictEqual(Object.keys(initial), ['format','version','activity','workspace']);
  assert.strictEqual(initial.activity.id, profile.id);
  assert.strictEqual(initial.workspace.blocks.blocks.length, 1);
  assert.deepStrictEqual(initial.workspace.blocks.blocks.map(b => b.type), ['webeeblocks_v2_takeoff']);
  assert.deepStrictEqual(initial.workspace.variables || [], []);
  const loaded = Projects.validateProjectText(source, profile, deps);
  assert.strictEqual(loaded.ast, null, 'a partial student starter is not an executable GP solution');
  Blockly.serialization.workspaces.load(initial.workspace, workspace);
  Contract.preflightWorkspace(profile, workspace);
  assert.strictEqual(workspace.getAllBlocks(false).length, 1);
  assert.throws(() => Semantic.compileWorkspace(workspace), /program must start with takeoff and end with land/);
  // The learner can attach an ordinary block; this is a format/round-trip
  // probe only, NOT a flight strategy and NOT an oracle success.
  const start = workspace.getTopBlocks(false)[0];
  const land = workspace.newBlock('webeeblocks_v2_land');
  start.nextConnection.connect(land.previousConnection);
  const ast = Semantic.compileWorkspace(workspace);
  Contract.preflightAst(profile, ast);
  assert.deepStrictEqual(ast.program.map(statement => statement.kind), ['takeoff','land']);
  const saved = Projects.encodeProject(profile, workspace, deps);
  const validated = Projects.validateProjectText(saved, profile, deps);
  assert.deepStrictEqual(validated.ast, ast);
  Blockly.serialization.workspaces.load(validated.project.workspace, reopened);
  const roundtrip = Semantic.compileWorkspace(reopened);
  assert.deepStrictEqual(roundtrip, ast);
  console.log('PASS incomplete U starter: real Blockly 13.2.1, no solution, load, edit, logical Save/Open');
} finally {
  workspace.dispose();
  reopened.dispose();
}
