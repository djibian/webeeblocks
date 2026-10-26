'use strict';
// Structural proof + real production Blockly/compiler/project round-trip.
// NOT a native Webots, browser GUI, safety, or pedagogical acceptance test.
const assert = require('assert'), fs = require('fs'), path = require('path'), vm = require('vm');
const {build} = require('./build');
const file = path.join(__dirname, 'Grand-Prix-sans-murs-algorithme-candidat.wbb');
const project = JSON.parse(fs.readFileSync(file, 'utf8'));
assert.deepStrictEqual(project, build(), 'file must match generated generic-block algorithm');
const ids = new Set(), types = {}, loops = [];
function visit(b) {
  assert(b && typeof b.type === 'string' && !ids.has(b.id), 'distinct Blockly block IDs');
  ids.add(b.id); types[b.type] = (types[b.type] || 0) + 1;
  if (b.type === 'controls_whileUntil') loops.push(b);
  for (const e of Object.values(b.inputs || {})) if (e.block) visit(e.block);
  if (b.next?.block) visit(b.next.block);
}
project.workspace.blocks.blocks.forEach(visit);
assert.strictEqual(ids.size, 232);
assert.strictEqual(project.workspace.variables.length, 10);
assert.strictEqual(types.webeeblocks_v2_takeoff, 1);
assert.strictEqual(types.webeeblocks_v2_land, 1);
assert.strictEqual(types.controls_repeat_ext, 1);
assert.strictEqual(types.webeeblocks_v2_guarded_move || 0, 0);
assert.strictEqual(types.procedures_callnoreturn, 1);
// The actual interpreter throws when a bounded UNTIL search is exhausted;
// unreachable post-loop guards add cognitive load without changing that.
assert.deepStrictEqual(loops.map(b => b.fields.MAX_ITERATIONS).sort((a, b) => a - b), [6, 25]);
const fault = b => b?.type === 'variables_set' &&
  b.fields?.VAR?.id === 'gp-pupil-v2-4' &&
  b.inputs?.VALUE?.block?.fields?.NUM === 2;
const terminal = loops.find(b => fault(b.next?.block?.inputs?.ELSE?.block));
assert(terminal, 'a completed terminal approach must validate the H count');
const guard = terminal.next.block.inputs.IF0.block;
function evaluatePupilCount(b, count) {
  if (b.type === 'math_number') return Number(b.fields.NUM);
  if (b.type === 'variables_get') {
    assert.strictEqual(b.fields.VAR.id, 'gp-pupil-v2-1');
    return count;
  }
  const a = evaluatePupilCount(b.inputs.A.block, count);
  const c = evaluatePupilCount(b.inputs.B.block, count);
  if (b.type === 'logic_operation' && b.fields.OP === 'AND') return Boolean(a && c);
  if (b.type === 'logic_compare' && b.fields.OP === 'GTE') return a >= c;
  if (b.type === 'logic_compare' && b.fields.OP === 'LTE') return a <= c;
  assert.fail('unexpected count-guard operation: ' + b.type);
}
for (const count of [0, 1, 2, 3, 4])
  assert.strictEqual(evaluatePupilCount(guard, count), count >= 1 && count <= 3);
console.log('PASS pure structural reproduction: 232 Blockly blocks, 10 variables, count 0..4 discriminated');
if (process.argv.includes('--structural-only')) process.exit(0);
const root = path.join(__dirname, '../..');
const Blockly = require(path.join(root, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
require(path.join(root, 'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
global.Blockly = Blockly;
require(path.join(root, 'plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js'));
delete global.Blockly;
const Semantic = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast'));
Semantic.installConditionalLoopBounds(Blockly);
const Contract = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activity_contract'));
const Activities = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activities'));
const Profiles = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles'));
const ProjectFiles = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/project_files'));
const context = {Blockly, WebeeBlocksActivities: Activities, WebeeBlocksActivityProfiles: Profiles,
  WebeeBlocksRuntimeOutcome: {classify: () => ({})}, WebeeBlocksWwiBackend: function() {}};
context.window = context;
vm.runInNewContext(fs.readFileSync(path.join(root, 'plugins/robot_windows/grand_prix_u/setup.js'), 'utf8'), context);
const profile = Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,
  'progression-grand-prix-u-v1', Activities.BLOCK_CATALOG);
const workspace = new Blockly.Workspace();
Blockly.serialization.workspaces.load(project.workspace, workspace);
Contract.preflightWorkspace(profile, workspace);
const ast = Semantic.compileWorkspace(workspace);
Contract.preflightAst(profile, ast);
assert.strictEqual(workspace.getAllBlocks(false).length, 232);
const result = ProjectFiles.validateProjectText(JSON.stringify(project), profile,
  {Blockly, profiles: Profiles, activitiesDocument: context.WebeeBlocksActivities.DOCUMENT,
    blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Semantic, activityContract: Contract});
assert.deepStrictEqual(result.ast, ast);
const reopened = new Blockly.Workspace();
Blockly.serialization.workspaces.load(project.workspace, reopened);
Contract.preflightWorkspace(profile, reopened);
const reopenedAst = Semantic.compileWorkspace(reopened);
Contract.preflightAst(profile, reopenedAst);
assert.deepStrictEqual(reopenedAst, ast);
console.log('PASS real Blockly load / preflight U / AST / validation / reopen');
console.log('UNPROVEN native Webots + browser GUI + teaching');
workspace.dispose(); reopened.dispose();
