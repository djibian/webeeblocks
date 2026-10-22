'use strict';
// Engineering candidate, never a pupil starter. No layout/seed/oracle argument.
const fs=require('fs'),vm=require('vm');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;require('../../plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2');delete global.Blockly;
const S=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
S.installConditionalLoopBounds(Blockly);
const C=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const A=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
function build({lateral=true,center=true}={}){
 const workspace=new Blockly.Workspace();
 const variables=Object.fromEntries(['distance commandée','nombre H'].map((name,i)=>[name,workspace.getVariableMap().createVariable(name,'','compact-u-'+i)]));
 function b(type,fields={}){const q=workspace.newBlock(type);for(const [k,v]of Object.entries(fields))q.setFieldValue(String(v),k);return q;}
 function input(q,name,v){q.getInput(name).connection.connect(v.outputConnection||v.previousConnection);return q;}
 function seq(list){list.slice(1).forEach((q,i)=>list[i].nextConnection.connect(q.previousConnection));return list[0];}
 const num=x=>b('math_number',{NUM:x});
 const get=name=>b('variables_get',{VAR:variables[name].getId()});
 const set=(name,x)=>input(b('variables_set',{VAR:variables[name].getId()}),'VALUE',num(x));
 const change=(name,x)=>input(b('math_change',{VAR:variables[name].getId()}),'DELTA',num(x));
 const compare=(op,a,x)=>input(input(b('logic_compare',{OP:op}),'A',a),'B',num(x));
 function until(x,body){return input(input(b('webeeblocks_v2_until'),'BOOL',compare('GTE',get('distance commandée'),x)),'DO',seq(body));}
 function iff(condition,body){return input(input(b('controls_if'),'IF0',condition),'DO0',seq(body));}
 const move=(x,d='forward')=>b('webeeblocks_v2_move',{DISTANCE:x,DIRECTION:d});
 const vertical=d=>b('webeeblocks_v2_vertical',{DIRECTION:d,DISTANCE:.4});
 const guarded=(distance,threshold)=>b('webeeblocks_v2_guarded_move',{DISTANCE:distance,THRESHOLD:threshold,VAR:variables['distance commandée'].getId()});
 const crossing=[vertical('down'),move(.4),change('distance commandée',.4),move(.3),change('distance commandée',.3),vertical('up'),change('nombre H',1)];
 const search=guarded(.1,.35);input(search,'ON_SENSOR',seq(crossing));
 const corner=iff(compare('GT',b('webeeblocks_v2_range',{DIRECTION:'front'}),.9),[
  until(2,[guarded(.1,.35)]),b('webeeblocks_v2_turn',{DIRECTION:'left',ANGLE:90})]);
 const central=(sensor,direction)=>input(input(b('webeeblocks_v2_until'),'BOOL',compare('GTE',b('webeeblocks_v2_range',{DIRECTION:sensor}),.8)),'DO',move(.1,direction));
 const align=direction=>input(input(b('webeeblocks_v2_until'),'BOOL',compare('LTE',b('webeeblocks_v2_range',{DIRECTION:direction}),.4)),'DO',move(.1,direction));
 const loop=input(input(b('controls_repeat_ext'),'TIMES',num(3)),'DO',seq([
  set('distance commandée',0),until(1.2,[search]),corner]));
 seq([b('webeeblocks_v2_takeoff',{HEIGHT:.4}),vertical('up'),set('nombre H',0),loop,
  guarded(.4,.7),...(center?[central('left','right'),central('right','left')]:[]),iff(compare('EQ',get('nombre H'),2),lateral?[align('left')]:[move(.4,'left'),move(.1,'left')]),
  iff(compare('EQ',get('nombre H'),3),lateral?[align('right')]:[move(.4,'right'),move(.1,'right')]),b('webeeblocks_v2_land')]);
 for(const v of workspace.getVariableMap().getAllVariables())if(!workspace.getAllBlocks(false).some(q=>q.getVarModels().some(m=>m.getId()===v.getId())))workspace.getVariableMap().deleteVariable(v);
 const context={Blockly,WebeeBlocksActivities:A,WebeeBlocksRuntimeOutcome:{classify:()=>({})},WebeeBlocksWwiBackend:function(){}};context.window=context;
 vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js','utf8'),context);
 const document=context.WebeeBlocksActivities.DOCUMENT,profile=Profiles.resolveById(document,'progression-grand-prix-u-v1',A.BLOCK_CATALOG);
 C.preflightWorkspace(profile,workspace);const ast=S.compileWorkspace(workspace);C.preflightAst(profile,ast);
 function depth(q){let d=0;for(const i of q.inputList)if(i.connection&&i.type===Blockly.inputs.inputTypes.STATEMENT){let child=i.connection.targetBlock();while(child){d=Math.max(d,1+depth(child));child=child.getNextBlock();}}return Math.max(d,q.getNextBlock()?depth(q.getNextBlock()):0);}
 const metrics={blocks:workspace.getAllBlocks(false).length,variables:workspace.getVariableMap().getAllVariables().length,procedures:0,statementNesting:Math.max(...workspace.getTopBlocks(false).map(depth))};
 const project={format:'webeeblocks-project',version:1,activity:{id:profile.id,semantics:ast.semantics},workspace:Blockly.serialization.workspaces.save(workspace)};
 return{workspace,ast,project,profile,document,metrics};
}
module.exports={build};
if(require.main===module){const r=build();fs.writeFileSync('tools/blockly/compact_u_demo.wbb',JSON.stringify(r.project,null,2)+'\n');console.log(r.metrics);r.workspace.dispose();}
