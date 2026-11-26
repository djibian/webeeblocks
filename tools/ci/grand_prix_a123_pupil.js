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
function profileContext(activity) {
assert([1, 2, 3].includes(activity));
const context = {
  WebeeBlocksActivities: Activities,
  WebeeBlocksGrandPrixProgression: Progression,
  WebeeBlocksRuntimeOutcome: {classify() {}},
  WebeeBlocksWwiBackend: function() {},
  Blockly: {inject() {}},
  document: {currentScript: {getAttribute: name => name === 'data-progression-activity' ? String(activity) : null}}
};
context.window = context;
const setup = path.join(__dirname, '../../plugins/robot_windows/grand_prix_route_v2/setup.js');
vm.runInNewContext(fs.readFileSync(setup, 'utf8'), context, {filename: setup});
const activitiesDocument = context.WebeeBlocksActivities.DOCUMENT;
const profile = Profiles.resolveById(activitiesDocument, context.WebeeBlocksInitialActivityId,
  Activities.BLOCK_CATALOG);
assert.equal(profile.id, 'progression-grand-prix-a' + activity + '-v1');
return {profile, activitiesDocument};
}

function manager(file, workspace, activity) {
  const {profile, activitiesDocument} = profileContext(activity);
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

async function save(file, activity) {
  const {profile} = profileContext(activity);
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
    const move = distance => attach(block('webeeblocks_v2_move', {DIRECTION: 'forward'}),
      'DISTANCE', number(distance));
    const vertical = (direction, distance) => attach(block('webeeblocks_v2_vertical',
      {DIRECTION: direction}), 'DISTANCE', number(distance));
    const turn = direction => block('webeeblocks_v2_turn', {DIRECTION: direction, ANGLE: 90});
    const chain = items => {
      for (let i = 1; i < items.length; i++) items[i-1].nextConnection.connect(items[i].previousConnection);
      return items[0];
    };
    const program = [attach(block('webeeblocks_v2_takeoff'), 'HEIGHT', number(activity === 1 ? .9 : .88)),
      block('webeeblocks_v2_speed', {SPEED: .2})];
    if (activity === 1) {
      program.push(move(1.4), turn('left'), move(1.8), turn('right'), move(1.30));
    } else if (activity === 2) {
      program.push(move(.46), vertical('down', .41), move(.68), vertical('up', .41), move(1.06));
    } else {
      const repeat = attach(block('controls_repeat_ext'), 'TIMES', number(3));
      attach(repeat, 'DO', chain([turn('left'), move(.91), vertical('down', .41),
        move(.68), vertical('up', .41), move(.91)]));
      program.push(repeat);
    }
    program.push(block('webeeblocks_v2_land'));
    for (let index = 1; index < program.length; index++)
      program[index - 1].nextConnection.connect(program[index].previousConnection);
    const original = Compiler.compileWorkspace(workspace);
    Contract.preflightWorkspace(profile, workspace);
    Contract.preflightAst(profile, original);
    if (activity === 3) {
      assert.equal(original.program[2].kind, 'repeat');
      assert.equal(original.program[2].count, 3);
    }
    await manager(file, workspace, activity).saveAs(path.basename(file));
    assert.deepEqual((await reopen(file, activity)).ast, original);
  } finally {
    workspace.dispose();
  }
}

async function reopen(file, activity) {
  const {profile} = profileContext(activity);
  const workspace = new Blockly.Workspace();
  try {
    const bytes = fs.readFileSync(file);
    const projects = manager(file, workspace, activity);
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

module.exports = {reopen, save};
if (require.main === module) {
  assert.equal(process.argv.length, 4, 'Pass activity 1–3 and a saved pupil project path');
  save(process.argv[3], Number(process.argv[2])).catch(error => { console.error(error); process.exitCode = 1; });
}
