'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createHash} = require('node:crypto');
const Blockly = require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
const modules = '../../plugins/robot_windows/blockly/webeeblocks/';
global.Blockly = Blockly;
require(modules + 'crazyflie_v2');
delete global.Blockly;
const Activities = require(modules + 'activities');
const Profiles = require(modules + 'activity_profiles');
const Projects = require(modules + 'project_files');
const Compiler = require(modules + 'semantic_ast');
const Contract = require(modules + 'activity_contract');
const Interpreter = require(modules + 'interpreter');

function a5Profile() {
  const context = {
    Blockly: {inject() {}},
    document: {currentScript: {getAttribute: () => '5'}},
    WebeeBlocksActivities: Activities,
    WebeeBlocksGrandPrixProgression: require(modules + 'grand_prix_progression'),
    WebeeBlocksWwiBackend: function() {},
    WebeeBlocksRuntimeOutcome: {classify() {}}
  };
  context.window = context;
  const setup = path.join(__dirname, '../../plugins/robot_windows/grand_prix_route_v2/setup.js');
  vm.runInNewContext(fs.readFileSync(setup, 'utf8'), context, {filename: setup});
  const activitiesDocument = context.WebeeBlocksActivities.DOCUMENT;
  const profile = Profiles.resolveById(activitiesDocument, context.WebeeBlocksInitialActivityId,
    Activities.BLOCK_CATALOG);
  assert.equal(profile.id, 'progression-grand-prix-a5-v1');
  return {profile, profiles: Profiles, activitiesDocument, blockCatalog: Activities.BLOCK_CATALOG,
    Blockly, semanticAst: Compiler, activityContract: Contract};
}

function buildWorkspace(workspace) {
  const memory = workspace.getVariableMap().createVariable('virage', '', 'a5-virage');
  function block(type, fields = {}, inputs = {}) {
    const result = workspace.newBlock(type);
    for (const [name, value] of Object.entries(fields))
      result.setFieldValue(String(value), name);
    for (const [name, child] of Object.entries(inputs))
      result.getInput(name).connection.connect(child.outputConnection || child.previousConnection);
    return result;
  }
  function sequence(...blocks) {
    for (let i = 1; i < blocks.length; i++)
      blocks[i - 1].nextConnection.connect(blocks[i].previousConnection);
    return blocks[0];
  }
  const number = value => block('math_number', {NUM: value});
  const range = direction => block('webeeblocks_v2_range', {DIRECTION: direction});
  const move = (direction, distance) => block('webeeblocks_v2_move',
    {DIRECTION: direction}, {DISTANCE: number(distance)});
  const turn = direction => block('webeeblocks_v2_turn', {DIRECTION: direction, ANGLE: 90});
  const less = (left, value) => block('logic_compare', {OP: 'LT'}, {A: left, B: number(value)});
  const remember = value => block('variables_set', {VAR: memory.getId()}, {VALUE: number(value)});
  function either(condition, yes, no) {
    const result = block('controls_if', {}, {IF0: condition, DO0: yes});
    result.loadExtraState({hasElse: true});
    result.getInput('ELSE').connection.connect(no.previousConnection);
    return result;
  }
  sequence(
    block('webeeblocks_v2_takeoff', {}, {HEIGHT: number(.9)}),
    block('webeeblocks_v2_speed', {SPEED: .2}),
    either(less(range('front'), .98), move('forward', .60),
      either(less(range('front'), 1.38), move('forward', 1), move('forward', 1.4))),
    either(less(range('right'), .45),
      sequence(remember(1), turn('left')), sequence(remember(0), turn('right'))),
    move('forward', 1.85),
    // 2.20 m nominal last-leg target; native convergence not yet qualified.
    move('forward', .35),
    either(less(block('variables_get', {VAR: memory.getId()}), .5),
      move('left', .50), move('right', .50)),
    block('webeeblocks_v2_land')
  );
}

function projectManager(file, workspace, options) {
  const name = path.basename(file);
  let profile = options.profile;
  const write = async (target, text) => {
    fs.writeFileSync(file, text);
    return {name: target, handle: file};
  };
  return Projects.createManager({...options, workspace, getProfile: () => profile,
    setProfile: value => { profile = value; },
    transport: {
      saveAs: write,
      save: async (handle, target, text) => {
        assert.equal(handle, file);
        return write(target, text);
      },
      open: async () => ({name, handle: file, text: fs.readFileSync(file, 'utf8')})
    }});
}

async function save(file) {
  const options = a5Profile();
  const workspace = new Blockly.Workspace();
  try {
    buildWorkspace(workspace);
    const project = projectManager(file, workspace, options);
    await project.saveAs(path.basename(file));
    const first = fs.readFileSync(file);
    await project.save();
    assert.deepEqual(fs.readFileSync(file), first);
    const reopened = new Blockly.Workspace();
    try {
      const openedProject = projectManager(file, reopened, options);
      const {ast} = await openedProject.open();
      assert.equal(openedProject.hasCurrentTarget(), true);
      assert.deepEqual(ast, Compiler.compileWorkspace(workspace));
      assert.deepEqual(ast, Compiler.compileWorkspace(reopened));
    } finally {
      reopened.dispose();
    }
  } finally {
    workspace.dispose();
  }
}

async function run(file, backend) {
  const options = a5Profile();
  const workspace = new Blockly.Workspace();
  const bytes = fs.readFileSync(file);
  const sha256 = createHash('sha256').update(bytes).digest('hex');
  try {
    const {ast} = await projectManager(file, workspace, options).open();
    assert.deepEqual(fs.readFileSync(file), bytes);
    const observations = {};
    const executed = await Contract.execute(options.profile, workspace, Compiler, Interpreter,
      backend, {
        maxSteps: options.profile.runtime.maxSteps,
        onAst: live => assert.deepEqual(live, ast),
        hooks: {
          onVariables: ({values}) => { observations.remembered = values.virage; },
          onNode: ({node, variables}) => {
            if (node.kind === 'variable_get')
              observations.recalled = variables.virage;
          },
          beforeStep: ({node}) => {
            if (node.kind === 'move' && ['left', 'right'].includes(node.direction))
              observations.side = node.direction;
          }
        }
      });
    assert.deepEqual(executed, ast);
    const {remembered, recalled, side} = observations;
    assert([0, 1].includes(remembered));
    assert.equal(recalled, remembered);
    assert.equal(side, recalled === 1 ? 'right' : 'left');
    console.log(JSON.stringify({event: 'A5_WBB', sha256, blockly: Blockly.VERSION,
      ...observations}));
  } finally {
    workspace.dispose();
  }
}

module.exports = {run};
if (require.main === module) {
  assert.equal(process.argv.length, 3, 'Pass the local .wbb output path');
  save(process.argv[2]).catch(error => {
    console.error(error);
    process.exitCode = 1;
  });
}
