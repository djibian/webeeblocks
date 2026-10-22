'use strict';
// Engineering experiments: real pupil blocks; no scene/oracle input to the program.
const fs=require('fs'),vm=require('vm');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;require('../../plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2');delete global.Blockly;
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
function build(crossH=false){
 const workspace=new Blockly.Workspace(),position=workspace.getVariableMap().createVariable('position','','commanded-position');
 function b(type,fields={}){const block=workspace.newBlock(type);for(const [k,v]of Object.entries(fields))block.setFieldValue(String(v),k);return block;}
 function chain(blocks){blocks.slice(1).forEach((block,i)=>blocks[i].nextConnection.connect(block.previousConnection));return blocks[0];}
 function change(distance){const block=b('math_change',{VAR:position.getId()}),n=b('math_number',{NUM:distance});block.getInput('DELTA').connection.connect(n.outputConnection);return block;}
 const takeoff=b('webeeblocks_v2_takeoff',{HEIGHT:.4}),rise=b('webeeblocks_v2_vertical',{DIRECTION:'up',DISTANCE:.4}),set=b('variables_set',{VAR:position.getId()}),zero=b('math_number',{NUM:0});set.getInput('VALUE').connection.connect(zero.outputConnection);
 const first=b('webeeblocks_v2_guarded_move',{VAR:position.getId()}),second=b('webeeblocks_v2_guarded_move',{VAR:position.getId()}),land=b('webeeblocks_v2_land');
 if(crossH){
  const body=chain([b('webeeblocks_v2_vertical',{DIRECTION:'down',DISTANCE:.4}),b('webeeblocks_v2_move',{DIRECTION:'forward',DISTANCE:.4}),change(.4),b('webeeblocks_v2_move',{DIRECTION:'forward',DISTANCE:.3}),change(.3),b('webeeblocks_v2_vertical',{DIRECTION:'up',DISTANCE:.4})]);
  second.getInput('ON_SENSOR').connection.connect(body.previousConnection);
 }
 chain([takeoff,rise,set,first,second,land]);
 const context={Blockly,WebeeBlocksActivities:Activities,WebeeBlocksRuntimeOutcome:{classify:()=>({})},WebeeBlocksWwiBackend:function(){}};context.window=context;
 vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js','utf8'),context);
 const document=context.WebeeBlocksActivities.DOCUMENT,profile=Profiles.resolveById(document,'progression-grand-prix-u-v1',Activities.BLOCK_CATALOG);
 Contract.preflightWorkspace(profile,workspace);const ast=Semantic.compileWorkspace(workspace);Contract.preflightAst(profile,ast);
 const project={format:'webeeblocks-project',version:1,activity:{id:profile.id,semantics:ast.semantics},workspace:Blockly.serialization.workspaces.save(workspace)};
 return{workspace,profile,document,ast,project,blocks:workspace.getAllBlocks(false).length};
}
module.exports={build};
if(require.main===module){for(const cross of [false,true]){const r=build(cross);fs.writeFileSync('tools/blockly/guarded_'+(cross?'single_h':'approach')+'_demo.wbb',JSON.stringify(r.project,null,2)+'\n');console.log({cross,blocks:r.blocks});r.workspace.dispose();}}
