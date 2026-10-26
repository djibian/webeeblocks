'use strict';
// Isolated experimental 222-block pupil .wbb. Original #647 adapter unchanged.
// Never read seed, layout, oracle, or mission-state information from Blockly.
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '../..');
const file = path.join(ROOT, 'experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb');
function build() {
  const content = fs.readFileSync(file, 'utf8');
  assert.deepStrictEqual(JSON.parse(content),
    require(path.join(ROOT, 'experiments/grand-prix-pupil-algorithm/build.js')).build(),
    'exact generated 222-block WBB identity before admission');
  const project = JSON.parse(content);
  const Blockly = require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
  require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
  global.Blockly = Blockly;
  try {
    require(path.join(ROOT, 'plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js'));
  } finally { delete global.Blockly; }
  const Semantic = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast'));
  Semantic.installConditionalLoopBounds(Blockly);
  const Contract = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_contract'));
  const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities'));
  const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles'));
  const ProjectFiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/project_files'));
  const context = {Blockly, WebeeBlocksActivities: Activities, WebeeBlocksActivityProfiles: Profiles,
    WebeeBlocksRuntimeOutcome: {classify: () => ({})}, WebeeBlocksWwiBackend: function() {}};
  context.window = context;
  vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/grand_prix_u/setup.js'), 'utf8'), context);
  const profile = Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,
    'progression-grand-prix-u-v1', Activities.BLOCK_CATALOG);
  const workspace = new Blockly.Workspace(), reopened = new Blockly.Workspace();
  try {
    Blockly.serialization.workspaces.load(project.workspace, workspace);
    Contract.preflightWorkspace(profile, workspace);
    const ast = Semantic.compileWorkspace(workspace);
    Contract.preflightAst(profile, ast);
    const validated = ProjectFiles.validateProjectText(content, profile,
      {Blockly, profiles: Profiles, activitiesDocument: context.WebeeBlocksActivities.DOCUMENT,
        blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Semantic, activityContract: Contract});
    assert.deepStrictEqual(validated.ast, ast, 'project .wbb must match compiled AST');
    Blockly.serialization.workspaces.load(project.workspace, reopened);
    Contract.preflightWorkspace(profile, reopened);
    const reopenedAst = Semantic.compileWorkspace(reopened);
    Contract.preflightAst(profile, reopenedAst);
    assert.deepStrictEqual(reopenedAst, ast, 'same AST on reopen');
    assert.strictEqual(workspace.getAllBlocks(false).length, 222);
    return {ast, project_sha256: crypto.createHash('sha256').update(content).digest('hex'),
      ast_sha256: crypto.createHash('sha256').update(JSON.stringify(ast)).digest('hex')};
  } finally {workspace.dispose(); reopened.dispose();}
}
module.exports = {build};
if (require.main === module) {
  const witness = build();
  console.log('GP_U_PUPIL_PREFLIGHT ' + JSON.stringify({
    source_pr: 703, source_head: '0d82c03e16f1e62044e79ef55ac5e9c6c7b67c81',
    derived_from: '2e563fc38e05b7f4f9025a1766a9cc58ea892ef1', project_sha256: witness.project_sha256,
    ast_sha256: witness.ast_sha256, blocks: 222,
    claim: 'real-Blockly-13.2.1-preflight-AST-roundtrip-only'}));
}
