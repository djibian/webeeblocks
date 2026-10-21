'use strict';
const fs=require('fs'),assert=require('assert');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const Witness=require('./workspace'),result=Witness.build();
assert.strictEqual(Interpreter.validateExecutionBudget(result.ast,20000),13370);
const blocklyApi=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
const semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const project=JSON.parse(fs.readFileSync(__dirname+'/Grand-Prix-sans-murs-experimental.wbb','utf8'));
const workspace=new blocklyApi.Workspace();blocklyApi.serialization.workspaces.load(project.workspace,workspace);
assert.deepStrictEqual(semantic.compileWorkspace(workspace),result.ast);workspace.dispose();
console.log('PASS persisted .wbb exact AST, round-trip and positive budget 13370');
for(const mode of ['wrong-landing','deadline','low-outside','collision','reverse']){
 process.argv[3]=mode;const negative=require('./negative_workspace').build();
 console.log('PASS negative Blockly preflight',mode,'budget',Interpreter.validateExecutionBudget(negative.ast,20000));
}
