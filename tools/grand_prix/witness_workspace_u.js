'use strict';
// Developer witness only. The pupil starter remains empty.
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require('../../plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js');
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
Semantic.installConditionalLoopBounds(Blockly);
delete global.Blockly;
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Witness=require('./reference_program_u');
function build(){
 const expected=Witness.build(),workspace=new Blockly.Workspace();
 function block(type,fields={}){const b=workspace.newBlock(type);for(const [k,v] of Object.entries(fields))b.setFieldValue(String(v),k);return b;}
 function input(b,name,child){b.getInput(name).connection.connect(child.outputConnection||child.previousConnection);}
 function variable(v){return workspace.getVariableMap().getVariableById(v.id)||workspace.getVariableMap().createVariable(v.name,'',v.id);}
 function expr(e){let b;
  if(e.kind==='number')return block('math_number',{NUM:e.value});
  if(e.kind==='range')return block('webeeblocks_v2_range',{DIRECTION:e.direction});
  if(e.kind==='variable_get')return block('variables_get',{VAR:variable(e.variable).getId()});
  const types={arithmetic:'math_arithmetic',compare:'logic_compare',logic:'logic_operation'};
  b=block(types[e.kind],{OP:e.op});input(b,'A',expr(e.left));input(b,'B',expr(e.right));return b;
 }
 function sequence(list){let first,last;for(const e of list){let b;
  switch(e.kind){
   case 'takeoff':b=block('webeeblocks_v2_takeoff',{HEIGHT:e.height_m});break;
   case 'land':b=block('webeeblocks_v2_land');break;
   case 'move':b=block('webeeblocks_v2_move',{DIRECTION:e.direction,DISTANCE:e.distance_m});break;
   case 'vertical':b=block('webeeblocks_v2_vertical',{DIRECTION:e.direction,DISTANCE:e.distance_m});break;
   case 'turn':b=block('webeeblocks_v2_turn',{DIRECTION:e.angle_deg<0?'right':'left',ANGLE:Math.abs(e.angle_deg)});break;
   case 'set_variable':b=block('variables_set',{VAR:variable(e.variable).getId()});input(b,'VALUE',expr(e.value));break;
   case 'repeat':b=block('controls_repeat_ext');input(b,'TIMES',expr({kind:'number',value:e.count}));input(b,'DO',sequence(e.body));break;
   case 'while':b=block('controls_whileUntil',{MODE:e.mode,MAX_ITERATIONS:e.max_iterations});input(b,'BOOL',expr(e.condition));input(b,'DO',sequence(e.body));break;
   case 'if':
    b=block('controls_if');if(e.else&&e.else.length)b.loadExtraState({hasElse:true});
    input(b,'IF0',expr(e.condition));if(e.then.length)input(b,'DO0',sequence(e.then));if(e.else&&e.else.length)input(b,'ELSE',sequence(e.else));break;
   default:throw Error('unsupported witness statement '+e.kind);
  }
  if(last)last.nextConnection.connect(b.previousConnection);else first=b;last=b;
 }return first;}
 sequence(expected.program);
 const context={Blockly,WebeeBlocksActivities:Activities,WebeeBlocksActivityProfiles:Profiles,
  WebeeBlocksRuntimeOutcome:{classify:()=>({})},WebeeBlocksWwiBackend:function(){}};
 context.window=context;vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js','utf8'),context);
 const profile=Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,'progression-grand-prix-u-v1',Activities.BLOCK_CATALOG);
 Contract.preflightWorkspace(profile,workspace);
 const ast=Semantic.compileWorkspace(workspace);Contract.preflightAst(profile,ast);assert.deepStrictEqual(ast,expected);
 const project={format:'webeeblocks-project',version:1,activity:{id:profile.id,semantics:ast.semantics},workspace:Blockly.serialization.workspaces.save(workspace)};
 const ProjectFiles=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
 const validated=ProjectFiles.validateProjectText(JSON.stringify(project),profile,{Blockly,profiles:Profiles,activitiesDocument:context.WebeeBlocksActivities.DOCUMENT,blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Semantic,activityContract:Contract});
 assert.deepStrictEqual(validated.ast,ast);
 const reopened=new Blockly.Workspace();Blockly.serialization.workspaces.load(project.workspace,reopened);
 Contract.preflightWorkspace(profile,reopened);const roundtrip=Semantic.compileWorkspace(reopened);Contract.preflightAst(profile,roundtrip);
 assert.deepStrictEqual(roundtrip,ast);workspace.dispose();reopened.dispose();return{ast,project};
}
module.exports={build};
if(require.main===module){const result=build();if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(result.project,null,2)+'\n');console.log('PASS real Blockly 13.2.1 -> U preflight -> exact witness AST -> .wbb round-trip');}
