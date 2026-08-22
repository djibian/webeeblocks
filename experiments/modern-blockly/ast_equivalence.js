'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Blockly = require('blockly');
require('blockly/blocks');

const productRoot = path.resolve(__dirname, '../..');
const Activities = require(path.join(productRoot, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles = require(path.join(productRoot, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const ActivityContract = require(path.join(productRoot, 'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const SemanticAst = require(path.join(productRoot, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));

const PROFILE_ID = 'reactive-obstacle-v2';
const FIXTURE = path.join(productRoot, 'controllers/Blockly_Programs/CrazyflieReactiveV2.xml');
const EXPECTED_AST = {
  version: 1,
  semantics: 'webeeblocks-ast-v1',
  program: [
    {kind: 'takeoff', height_m: 0.5},
    {
      kind: 'repeat',
      count: 3,
      body: [{
        kind: 'if',
        condition: {
          kind: 'compare',
          op: 'LT',
          left: {kind: 'range', direction: 'front', unit: 'm'},
          right: {kind: 'number', value: 0.5}
        },
        then: [{kind: 'move', direction: 'left', distance_m: 0.3}],
        else: [{kind: 'move', direction: 'forward', distance_m: 0.3}]
      }]
    },
    {kind: 'land'}
  ]
};

function bounds(profile, blockType, fieldName) {
  const value = profile.parameterBounds && profile.parameterBounds[blockType] && profile.parameterBounds[blockType][fieldName];
  if (!value)
    throw new Error(`missing profile bounds for ${blockType}.${fieldName}`);
  return value;
}

function numberField(name, value, constraint) {
  return {
    type: 'field_number',
    name,
    value,
    min: constraint.min,
    max: constraint.max,
    precision: constraint.step
  };
}

function registerRuntimeV2Blocks(profile) {
  const takeoff = bounds(profile, 'webeeblocks_v2_takeoff', 'HEIGHT');
  const move = bounds(profile, 'webeeblocks_v2_move', 'DISTANCE');
  const vertical = bounds(profile, 'webeeblocks_v2_vertical', 'DISTANCE');
  const turn = bounds(profile, 'webeeblocks_v2_turn', 'ANGLE');
  const wait = bounds(profile, 'webeeblocks_v2_wait', 'SECONDS');
  const speed = bounds(profile, 'webeeblocks_v2_speed', 'SPEED');

  Blockly.common.defineBlocksWithJsonArray([
    {
      type: 'webeeblocks_v2_takeoff',
      message0: 'décoller à %1 m',
      args0: [numberField('HEIGHT', 0.5, takeoff)],
      nextStatement: null,
      colour: 20
    },
    {
      type: 'webeeblocks_v2_move',
      message0: '%1 de %2 m',
      args0: [
        {type: 'field_dropdown', name: 'DIRECTION', options: [['avancer', 'forward'], ['reculer', 'back'], ['gauche', 'left'], ['droite', 'right']]},
        numberField('DISTANCE', 0.3, move)
      ],
      previousStatement: null,
      nextStatement: null,
      colour: 20
    },
    {
      type: 'webeeblocks_v2_vertical',
      message0: '%1 de %2 m',
      args0: [
        {type: 'field_dropdown', name: 'DIRECTION', options: [['monter', 'up'], ['descendre', 'down']]},
        numberField('DISTANCE', 0.2, vertical)
      ],
      previousStatement: null,
      nextStatement: null,
      colour: 20
    },
    {
      type: 'webeeblocks_v2_turn',
      message0: 'tourner à %1 de %2 °',
      args0: [
        {type: 'field_dropdown', name: 'DIRECTION', options: [['gauche', 'left'], ['droite', 'right']]},
        numberField('ANGLE', 90, turn)
      ],
      previousStatement: null,
      nextStatement: null,
      colour: 20
    },
    {
      type: 'webeeblocks_v2_wait',
      message0: 'attendre %1 s',
      args0: [numberField('SECONDS', 1, wait)],
      previousStatement: null,
      nextStatement: null,
      colour: 20
    },
    {
      type: 'webeeblocks_v2_speed',
      message0: 'vitesse %1 m/s',
      args0: [numberField('SPEED', 0.3, speed)],
      previousStatement: null,
      nextStatement: null,
      colour: 20
    },
    {
      type: 'webeeblocks_v2_range',
      message0: 'distance %1',
      args0: [{type: 'field_dropdown', name: 'DIRECTION', options: profile.runtime.rangeDirections.map(direction => [direction, direction])}],
      output: 'Number',
      colour: 60
    },
    {
      type: 'webeeblocks_v2_land',
      message0: 'atterrir',
      previousStatement: null,
      colour: 20
    }
  ]);
}

function profileToolbox(profile) {
  return {
    kind: 'flyoutToolbox',
    contents: profile.toolbox.map(type => ({kind: 'block', type}))
  };
}

function assertProfileSurface(profile) {
  const toolbox = profileToolbox(profile);
  assert.deepEqual(toolbox.contents.map(entry => entry.type), profile.toolbox, 'toolbox must come directly from resolved activity profile');
  for (const type of profile.toolbox)
    assert.ok(Blockly.Blocks[type], `modern Blockly missing profile block ${type}`);

  const workspace = new Blockly.Workspace();
  const block = workspace.newBlock('webeeblocks_v2_takeoff');
  ActivityContract.applyFieldBounds(profile, workspace);
  const field = block.getField('HEIGHT');
  field.setValue(99);
  assert.equal(Number(field.getValue()), 1.5, 'profile max bound must clamp modern FieldNumber');
  field.setValue(-99);
  assert.equal(Number(field.getValue()), 0.2, 'profile min bound must clamp modern FieldNumber');
  workspace.dispose();
}

function compileLegacyXml(profile) {
  const xmlText = fs.readFileSync(FIXTURE, 'utf8');
  const workspace = new Blockly.Workspace();
  try {
    const dom = Blockly.utils.xml.textToDom(xmlText);
    Blockly.Xml.domToWorkspace(dom, workspace);
    ActivityContract.preflightWorkspace(profile, workspace);
    ActivityContract.applyFieldBounds(profile, workspace);
    const ast = SemanticAst.compileWorkspace(workspace);
    ActivityContract.preflightAst(profile, ast);
    return {workspace, ast};
  } catch (error) {
    workspace.dispose();
    console.error(`LEGACY_XML_MIGRATION=REJECT reason=${error.message}`);
    throw error;
  }
}

function roundTripJson(profile, sourceWorkspace, expectedAst) {
  const state = Blockly.serialization.workspaces.save(sourceWorkspace);
  const workspace = new Blockly.Workspace();
  Blockly.serialization.workspaces.load(state, workspace);
  ActivityContract.preflightWorkspace(profile, workspace);
  ActivityContract.applyFieldBounds(profile, workspace);
  const ast = SemanticAst.compileWorkspace(workspace);
  ActivityContract.preflightAst(profile, ast);
  assert.deepEqual(ast, expectedAst, 'JSON serialization must preserve Runtime v2 semantic AST exactly');
  workspace.dispose();
  return state;
}

function main() {
  assert.equal(Blockly.VERSION, '13.2.1', 'experiment must run against the pinned Blockly release');
  const profile = Profiles.resolveById(Activities.DOCUMENT, PROFILE_ID, Activities.BLOCK_CATALOG);
  registerRuntimeV2Blocks(profile);
  assertProfileSurface(profile);

  const {workspace, ast} = compileLegacyXml(profile);
  try {
    assert.deepEqual(ast, EXPECTED_AST, 'modern Blockly legacy-XML import must produce the current Runtime v2 AST oracle');
    console.log('LEGACY_XML_MIGRATION=PASS');
    const jsonState = roundTripJson(profile, workspace, EXPECTED_AST);
    console.log(`BLOCKLY_VERSION=${Blockly.VERSION}`);
    console.log(`PROFILE=${profile.id}`);
    console.log(`TOOLBOX_TYPES=${profile.toolbox.length}`);
    console.log(`JSON_SERIALIZATION=PASS bytes=${Buffer.byteLength(JSON.stringify(jsonState))}`);
    console.log(`AST_EQUIVALENCE=PASS ${JSON.stringify(ast)}`);
  } finally {
    workspace.dispose();
  }
}

main();
