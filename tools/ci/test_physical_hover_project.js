'use strict';
// Load the exact delivered project through native Blockly and existing profile
// validation. A handwritten AST alone cannot prove the browser's actual binding.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Blockly = require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
global.Blockly = Blockly;
require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
require(path.join(ROOT, 'plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js'));
const base = path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks');
const Profiles = require(path.join(base, 'activity_profiles.js'));
const Activities = require(path.join(base, 'activities.js'));
const SemanticAst = require(path.join(base, 'semantic_ast.js'));
const Contract = require(path.join(base, 'activity_contract.js'));
const Project = require(path.join(base, 'project_files.js'));
const physical = path.join(ROOT, 'tools/physical');
const project = Project.parseProject(fs.readFileSync(path.join(physical, 'hover_range_comparison.wbb'), 'utf8'));
const profile = Profiles.resolveById(Activities.DOCUMENT, project.activity.id, Activities.BLOCK_CATALOG);
const workspace = new Blockly.Workspace();
try {
  Blockly.serialization.workspaces.load(project.workspace, workspace);
  Contract.preflightWorkspace(profile, workspace);
  const ast = SemanticAst.compileWorkspace(workspace);
  Contract.preflightAst(profile, ast);
  assert.deepStrictEqual(ast, JSON.parse(fs.readFileSync(path.join(physical, 'hover_range_comparison_ast.json'), 'utf8')));
  assert.deepStrictEqual(ast.program.map(node => node.kind), ['takeoff', 'wait', 'set_variable', 'land']);
  assert.strictEqual(ast.program[0].height_m, 0.5);
  assert.strictEqual(ast.program[1].seconds, 1);
  assert.deepStrictEqual(ast.program[2].value, {kind: 'range', direction: 'front', unit: 'm'});
  assert.strictEqual(workspace.getAllBlocks(false).filter(block => block.type === 'webeeblocks_v2_range').length, 1);
} finally { workspace.dispose(); }
console.log('PASS exact hover .wbb -> native Blockly/profile -> unchanged AST; one front read, no horizontal/yaw/vertical/light effect');
