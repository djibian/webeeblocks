'use strict';
// Lean 232-guarded-block variant: structural proof + production Blockly/compiler/project round-trip.
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
assert.strictEqual(project.workspace.variables.length, 11);
assert.strictEqual(types.webeeblocks_v2_takeoff, 1);
assert.strictEqual(types.webeeblocks_v2_land, 1);
assert.strictEqual(types.controls_repeat_ext, 1);
assert.strictEqual(types.webeeblocks_v2_guarded_move || 0, 0);
assert.strictEqual(types.procedures_callnoreturn, 4);
assert.strictEqual(types.procedures_defnoreturn, 4);
// The actual interpreter throws when a bounded UNTIL search is exhausted;
// unreachable post-loop guards add cognitive load without changing that.
assert.deepStrictEqual(loops.map(b => b.fields.MAX_ITERATIONS).sort((a, b) => a - b), [6, 25]);
const fault = b => b?.type === 'variables_set' &&
  b.fields?.VAR?.id === 'gp-pupil-v2-3' &&
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
console.log('PASS pure structural reproduction: 232 Blockly blocks, 11 variables, count 0..4 discriminated');
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

// Map real interpreter paths back to actual, editable Blockly IDs. This checks
// the production observability boundary, not browser step-button ergonomics.
const Observer = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/execution_observer'));
const Interpreter = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/interpreter'));
const sourceMap = Observer.buildSourceMap(workspace);
const locations = Object.entries(sourceMap);
const definition = project.workspace.blocks.blocks.find(b => b.type === 'procedures_defnoreturn');
assert(locations.length >= 100, 'too few mapped Blockly locations');
assert(locations.every(([, id]) => ids.has(id)), 'source map must reference loaded block IDs');
assert.strictEqual(sourceMap['program/0'], project.workspace.blocks.blocks[0].id);
assert(locations.some(([, id]) => id === definition.inputs.STACK.block.id),
  'procedure instructions must remain visible under their original block IDs');
assert(locations.some(([p]) => p.endsWith('/condition')),
  'loop / decision conditions must remain visible in step mode');
assert(Interpreter.validateExecutionBudget(ast, profile.runtime.maxSteps) <= profile.runtime.maxSteps);
console.log('PASS actual source-map paths / procedure expansion / interpreter execution budget');

// Product Save As -> Open -> Save, with an injected in-memory file transport.
// Browser/OS file pickers remain a separate, explicitly unproven obligation.
(async function() {
  const stored = {text: null, name: null, writes: 0}, handle = {id: 'gp-project-test'};
  const transport = {
    nativeFileSystemAccess: true,
    async open() {assert(stored.text); return {handle, name: stored.name, text: stored.text, mode: 'test'};},
    async saveAs(name, text) {stored.name = name; stored.text = text; stored.writes++; return {handle, name, mode: 'test'};},
    async save(target, name, text) {
      assert.strictEqual(target, handle); stored.name = name; stored.text = text; stored.writes++;
      return {handle, name, mode: 'test'};
    }
  };
  const selection = {profile};
  const manager = ProjectFiles.createManager({
    Blockly, profiles: Profiles, activitiesDocument: context.WebeeBlocksActivities.DOCUMENT,
    blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Semantic,
    activityContract: Contract, workspace,
    getProfile: () => selection.profile, setProfile: value => {selection.profile = value;},
    transport
  });
  await manager.saveAs('grand-prix-test');
  assert.strictEqual(JSON.parse(stored.text).activity.id, project.activity.id);
  workspace.clear();
  await manager.open();
  assert.deepStrictEqual(Semantic.compileWorkspace(workspace), ast, 'Save/Open changed the candidate AST');
  assert.deepStrictEqual(Observer.buildSourceMap(workspace), sourceMap, 'Save/Open changed debug mapping');
  await manager.save();
  assert.strictEqual(stored.writes, 2);
  assert.deepStrictEqual(Semantic.compileWorkspace(workspace), ast, 'Save changed the candidate AST');
  console.log('PASS production project manager Save As / Open / Save (memory transport)');

  // Sensor-independent negative, not a physical or native qualification.
  // With no H echoes (front=2m), the pupil algorithm must NOT record an H.
  const actions = [], highlighted = [];
  const backend = {
    capabilities: {conditionalLoops: true, procedures: true},
    async takeoff(height) {actions.push(['takeoff',height]);},
    async move(direction, distance) {actions.push(['move',direction,distance]);},
    async vertical(direction, distance) {actions.push(['vertical',direction,distance]);},
    async turn(degrees) {actions.push(['turn',degrees]);},
    async land() {actions.push(['land']);},
    async readRange() {return 2;}
  };
  const observer = Observer.create(workspace, {
    onActive: detail => {if (detail.node?.kind === 'turn') highlighted.push(detail.blockId);}
  });
  const hooks = observer.begin(true);
  observer.continueRun();
  const simulated = await Interpreter.run(ast, backend, {maxSteps: profile.runtime.maxSteps, hooks});
  observer.finish();
  assert.strictEqual(simulated.variables['portes'], 0, 'phantom H crossing on empty synthetic course');
  assert.strictEqual(simulated.variables['état'], 2, 'empty synthetic course must be rejected');
  assert.strictEqual(actions.filter(x => x[0] === 'turn').length, 2);
  assert.strictEqual(actions.filter(x => x[0] === 'land').length, 1);
  assert(highlighted.length > 0 && highlighted.every(id => ids.has(id)),
    'interpreter turn events must trace to real Blockly blocks');
  console.log('PASS production interpreter / no-H negative / two turns / traceable blocks');

  // A loop that exhausts its bound is an error, never an implicit successful
  // exit that could reach the subsequent LAND statement.
  const bounded = {version: 1, semantics: 'webeeblocks-ast-v1', program: [
    {kind: 'takeoff', height_m: 0.4},
    {kind: 'while', mode: 'UNTIL', max_iterations: 2,
      condition: {kind: 'number', value: 0},
      body: [{kind: 'move', direction: 'forward', distance_m: 0.1}]},
    {kind: 'land'}
  ]};
  const faultActions = [], boundedBackend = {
    capabilities: {conditionalLoops: true},
    async takeoff() {faultActions.push('takeoff');},
    async move() {faultActions.push('move');},
    async land() {faultActions.push('land');}
  };
  await assert.rejects(
    Interpreter.run(bounded, boundedBackend, {maxSteps: 50}),
    /conditional loop iteration limit exceeded/
  );
  assert(!faultActions.includes('land'), 'exhausted loop incorrectly fell through to LAND');
  console.log('PASS production interpreter exhausted-loop negative (no fall-through)');
  console.log('UNPROVEN native Webots + GUI + OS picker + 210 s authority + teaching');
  workspace.dispose();
  reopened.dispose();
})().catch(error => {console.error(error);process.exitCode = 1;});
