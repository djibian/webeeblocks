'use strict';
// Technical witness only. Its project and profile contain no world variant.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Blockly = require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
const dir = '../../plugins/robot_windows/blockly/webeeblocks/';
global.Blockly = Blockly;
require(dir + 'crazyflie_v2');
delete global.Blockly;
const Compiler = require(dir + 'semantic_ast');
const Activities = require(dir + 'activities');
const Profiles = require(dir + 'activity_profiles');
const Contract = require(dir + 'activity_contract');
const Projects = require(dir + 'project_files');
const Progression = require(dir + 'grand_prix_progression');

assert.equal(Blockly.VERSION, '13.2.1');
const context = {
  WebeeBlocksActivities: Activities,
  WebeeBlocksGrandPrixProgression: Progression,
  WebeeBlocksRuntimeOutcome: {classify() {}},
  WebeeBlocksWwiBackend: function() {},
  Blockly: {inject() {}},
  document: {currentScript: {getAttribute: name => name === 'data-progression-activity' ? '4' : null}}
};
context.window = context;
const setup = path.join(__dirname, '../../plugins/robot_windows/grand_prix_route_v2/setup.js');
vm.runInNewContext(fs.readFileSync(setup, 'utf8'), context, {filename: setup});
const activitiesDocument = context.WebeeBlocksActivities.DOCUMENT;
const profile = Profiles.resolveById(activitiesDocument, context.WebeeBlocksInitialActivityId,
  Activities.BLOCK_CATALOG);
assert.equal(profile.id, 'progression-grand-prix-a4-v1');

function manager(file, workspace) {
  const name = path.basename(file);
  let currentProfile = profile;
  return Projects.createManager({workspace, Blockly, profiles: Profiles, activitiesDocument,
    blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Compiler, activityContract: Contract,
    getProfile: () => currentProfile, setProfile: value => { currentProfile = value; },
    transport: {
      saveAs(proposal, text) {
        assert.equal(proposal, name);
        fs.writeFileSync(file, text);
        return {name, handle: file};
      },
      open() {
        return {name, handle: file, text: fs.readFileSync(file, 'utf8')};
      }
    }
  });
}

async function save(file) {
  const workspace = new Blockly.Workspace();
  try {
    function block(type, fields = {}) {
      const entry = workspace.newBlock(type);
      for (const [name, value] of Object.entries(fields)) entry.setFieldValue(String(value), name);
      return entry;
    }
    function attach(parent, input, child) {
      parent.getInput(input).connection.connect(child.outputConnection || child.previousConnection);
      return parent;
    }
    const number = value => block('math_number', {NUM: value});
    const move = (direction, distance) => attach(block('webeeblocks_v2_move', {DIRECTION: direction}),
      'DISTANCE', number(distance));
    function decide(threshold, then, otherwise) {
      const comparison = block('logic_compare', {OP: 'LT'});
      attach(comparison, 'A', block('webeeblocks_v2_range', {DIRECTION: 'front'}));
      attach(comparison, 'B', number(threshold));
      const conditional = block('controls_if');
      conditional.loadExtraState({hasElse: true});
      attach(conditional, 'IF0', comparison);
      attach(conditional, 'DO0', then);
      return attach(conditional, 'ELSE', otherwise);
    }
    const program = [attach(block('webeeblocks_v2_takeoff'), 'HEIGHT', number(.9)),
      block('webeeblocks_v2_speed', {SPEED: .2}),
      decide(1.16, move('forward', .30), decide(1.56, move('forward', .70), move('forward', 1.10))),
      move('left', .50), block('webeeblocks_v2_land')];
    for (let index = 1; index < program.length; index++)
      program[index - 1].nextConnection.connect(program[index].previousConnection);
    const original = Compiler.compileWorkspace(workspace);
    Contract.preflightAst(profile, original);
    await manager(file, workspace).saveAs(path.basename(file));
    assert.deepEqual((await reopen(file)).ast, original);
  } finally {
    workspace.dispose();
  }
}

async function reopen(file) {
  const workspace = new Blockly.Workspace();
  try {
    const bytes = fs.readFileSync(file);
    const projects = manager(file, workspace);
    const opened = await projects.open();
    assert(projects.hasCurrentTarget());
    const ast = Compiler.compileWorkspace(workspace);
    Contract.preflightAst(profile, ast);
    assert.deepEqual(ast, opened.ast);
    return {ast, sha256: createHash('sha256').update(bytes).digest('hex'), maxSteps: profile.runtime.maxSteps};
  } finally {
    workspace.dispose();
  }
}

module.exports = {reopen};
if (require.main === module) {
  assert.equal(process.argv.length, 3, 'Pass one path for the saved pupil project');
  save(process.argv[2]).catch(error => { console.error(error); process.exitCode = 1; });
}
