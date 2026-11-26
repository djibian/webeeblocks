'use strict';
// A7 Draft-only real Blockly 13.2.1 .wbb witness; NOT a pupil starter.
// No variant number, world metadata, or evaluator oracle enters this program.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require('../../plugins/robot_windows/blockly/webeeblocks/crazyflie_v2');
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
Semantic.installConditionalLoopBounds(Blockly);delete global.Blockly;
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Progression=require('../../plugins/robot_windows/blockly/webeeblocks/grand_prix_progression');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const Files=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');

function school(){
 const host={WebeeBlocksActivities:Activities,WebeeBlocksGrandPrixProgression:Progression,
   WebeeBlocksRuntimeOutcome:{classify(){}},WebeeBlocksWwiBackend:function(){},
   Blockly:{inject(){}},document:{currentScript:{getAttribute(key){
     assert.equal(key,'data-progression-activity');return '7';
   }}}};
 host.window=host;
 vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/setup.js','utf8'),host);
 const activitiesDocument=host.WebeeBlocksActivities.DOCUMENT;
 const profile=Profiles.resolveById(activitiesDocument,host.WebeeBlocksInitialActivityId,Activities.BLOCK_CATALOG);
 assert.equal(profile.id,'progression-grand-prix-a7-v1');
 return {profile,options:{Blockly,profiles:Profiles,activitiesDocument,
   blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Semantic,activityContract:Contract}};
}
const variables={front:{id:'a7-front',name:'avant'},left:{id:'a7-left',name:'gauche'},
 right:{id:'a7-right',name:'droite'},need:{id:'a7-need',name:'affiner'}};
const n=value=>({kind:'number',value}),range=direction=>({kind:'range',direction,unit:'m'});
const v=name=>({kind:'variable_get',variable:variables[name]});
const cmp=(op,left,right)=>({kind:'compare',op,left,right});
const gt=(a,b)=>cmp('GT',a,b),lt=(a,b)=>cmp('LT',a,b);
const and=(a,b)=>({kind:'logic',op:'AND',left:a,right:b});
const motion=(direction,distance_m)=>({kind:'move',direction,distance_m});
const set=(name,value)=>({kind:'set_variable',variable:variables[name],value});
const loop=(max_iterations,condition,body)=>({kind:'while',mode:'WHILE',max_iterations,condition,body});
const iff=(condition,then,otherwise=[])=>Object.assign({kind:'if',condition,then},
 otherwise.length?{else:otherwise}:{});

function reference(){
 const definitions={};
 const call=name=>({kind:'call',name,body:structuredClone(definitions[name])});
 // The A7 profile permits AND, not OR. These two IFs implement the same
 // logical disjunction as a 0/1 flag, without adding a pupil block.
 definitions.scan=[set('front',range('front')),set('left',range('left')),
   set('right',range('right')),set('need',n(0)),
   iff(gt(v('left'),n(.45)),[set('need',n(1))]),
   iff(gt(v('right'),n(.45)),[set('need',n(1))])];
 definitions.reach=[
   loop(14,gt(range('front'),n(.46)),[motion('forward',.24)]),call('scan'),
   loop(14,and(and(gt(v('front'),n(.16)),gt(v('left'),n(.45))),gt(v('right'),n(.45))),
     [motion('forward',.05),call('scan')]),
   loop(4,and(and(gt(v('front'),n(.16)),lt(v('front'),n(.25))),gt(v('need'),n(0))),
     [motion('forward',.04),call('scan')])];
 definitions.leg=[call('reach'),iff(and(lt(v('left'),n(.45)),lt(v('right'),n(.45))),[
   loop(12,gt(range('front'),n(.16)),[motion('forward',.04)]),
   {kind:'vertical',direction:'down',distance_m:.42},motion('forward',.60),
   {kind:'vertical',direction:'up',distance_m:.42},call('reach')])];
 return {definitions,ast:{version:1,semantics:'webeeblocks-ast-v1',program:[
   {kind:'takeoff',height_m:.9},{kind:'set_speed',speed_m_s:.2},call('leg'),
   loop(10,gt(range('front'),n(.30)),[motion('forward',.06)]),
   loop(8,lt(range('front'),n(.27)),[motion('back',.04)]),
   iff(lt(v('right'),n(.45)),[{kind:'turn',angle_deg:90}],[{kind:'turn',angle_deg:-90}]),
   call('leg'),loop(8,lt(range('front'),n(.65)),[motion('back',.13)]),
   loop(8,gt(range('front'),n(.71)),[motion('forward',.05)]),{kind:'land'}]}};
}
function normalizeIds(project){
 const ids=new Set(Object.values(variables).map(x=>x.id));let index=0;
 function visit(obj){
   if(Array.isArray(obj)){obj.forEach(visit);return;}
   if(!obj||typeof obj!=='object')return;
   for(const [key,value] of Object.entries(obj)){
     if(key==='id'&&typeof value==='string'&&!ids.has(value))obj[key]='a7-block-'+(++index);
     else visit(value);
   }
 }
 visit(project.workspace);
}
function build(){
 const {profile,options}=school(),expected=reference();
 const ws=new Blockly.Workspace();let index=0;
 const block=(type,fields={})=>{
   const b=ws.newBlock(type,'a7-builder-'+(++index));
   for(const [key,value] of Object.entries(fields))b.setFieldValue(String(value),key);
   return b;
 };
 const input=(b,name,child)=>{
   const socket=b.getInput(name);
   assert(socket&&socket.connection,b.type+'.'+name+' missing');
   socket.connection.connect(child.outputConnection||child.previousConnection);
 };
 const variable=ref=>ws.getVariableMap().getVariableById(ref.id)||
   ws.getVariableMap().createVariable(ref.name,'',ref.id);
 function expr(e){
   if(e.kind==='number')return block('math_number',{NUM:e.value});
   if(e.kind==='range')return block('webeeblocks_v2_range',{DIRECTION:e.direction});
   if(e.kind==='variable_get')return block('variables_get',{VAR:variable(e.variable).getId()});
   const types={compare:'logic_compare',logic:'logic_operation'};
   assert(types[e.kind],'unsupported expression '+e.kind);
   const b=block(types[e.kind],{OP:e.op});input(b,'A',expr(e.left));input(b,'B',expr(e.right));return b;
 }
 function sequence(items){
   let first,last;
   for(const s of items){let b;
     switch(s.kind){
       case 'takeoff':b=block('webeeblocks_v2_takeoff');input(b,'HEIGHT',expr(n(s.height_m)));break;
       case 'land':b=block('webeeblocks_v2_land');break;
       case 'set_speed':b=block('webeeblocks_v2_speed',{SPEED:s.speed_m_s});break;
       case 'move':b=block('webeeblocks_v2_move',{DIRECTION:s.direction});
         input(b,'DISTANCE',expr(n(s.distance_m)));break;
       case 'vertical':b=block('webeeblocks_v2_vertical',{DIRECTION:s.direction});
         input(b,'DISTANCE',expr(n(s.distance_m)));break;
       case 'turn':b=block('webeeblocks_v2_turn',
         {DIRECTION:s.angle_deg<0?'right':'left',ANGLE:Math.abs(s.angle_deg)});break;
       case 'set_variable':b=block('variables_set',{VAR:variable(s.variable).getId()});
         input(b,'VALUE',expr(s.value));break;
       case 'while':b=block('controls_whileUntil',{MODE:s.mode,MAX_ITERATIONS:s.max_iterations});
         input(b,'BOOL',expr(s.condition));input(b,'DO',sequence(s.body));break;
       case 'if':b=block('controls_if');if(s.else&&s.else.length)b.loadExtraState({hasElse:true});
         input(b,'IF0',expr(s.condition));if(s.then.length)input(b,'DO0',sequence(s.then));
         if(s.else&&s.else.length)input(b,'ELSE',sequence(s.else));break;
       case 'call':b=block('procedures_callnoreturn');b.loadExtraState({name:s.name});break;
       default:throw Error('unsupported A7 Blockly statement '+s.kind);
     }
     if(last)last.nextConnection.connect(b.previousConnection);else first=b;
     last=b;
   }
   assert(first,'empty witness statement sequence');return first;
 }
 try{
   const definitions=Object.keys(expected.definitions).map(name=>{
     const b=block('procedures_defnoreturn');b.setFieldValue(name,'NAME');return {name,b};
   });
   for(const {name,b} of definitions)input(b,'STACK',sequence(expected.definitions[name]));
   sequence(expected.ast.program);
   Contract.preflightWorkspace(profile,ws);
   const ast=Semantic.compileWorkspace(ws);
   Contract.preflightAst(profile,ast);
   assert.deepStrictEqual(ast,expected.ast,'A7 real Blockly program AST mismatch');
   const project=Files.createProject(profile,ws,options);
   normalizeIds(project);
   const content=JSON.stringify(project,null,2)+'\n';
   const opened=Files.validateProjectText(content,profile,options);
   assert.deepStrictEqual(opened.ast,ast,'A7 Save/Open changes AST');
   const reread=new Blockly.Workspace();
   try{
     Blockly.serialization.workspaces.load(opened.project.workspace,reread);
     Contract.preflightWorkspace(profile,reread);
     assert.deepStrictEqual(Semantic.compileWorkspace(reread),ast);
   }finally{reread.dispose();}
   return {content,sha256:crypto.createHash('sha256').update(content).digest('hex'),ast};
 }finally{ws.dispose();}
}
async function runSaved(content,backend){
 const {profile,options}=school();
 const opened=Files.validateProjectText(content,profile,options);
 assert(opened.ast,'A7 saved program has no executable AST');
 assert(opened.ast.program.some(s=>s.kind==='while'),'missing A7 bounded loop');
 assert(opened.ast.program.some(s=>s.kind==='call'),'missing A7 procedure');
 const ws=new Blockly.Workspace();
 try{
   Blockly.serialization.workspaces.load(opened.project.workspace,ws);
   assert.deepStrictEqual(Semantic.compileWorkspace(ws),opened.ast);
   const executed=await Contract.execute(profile,ws,Semantic,Interpreter,backend,{maxSteps:20000});
   assert.deepStrictEqual(executed,opened.ast,'product interpreter executed a different AST');
   return {sha256:crypto.createHash('sha256').update(content).digest('hex'),
     astSha256:crypto.createHash('sha256').update(JSON.stringify(executed)).digest('hex')};
 }finally{ws.dispose();}
}
module.exports={build,runSaved,reference,school};
if(require.main===module){
 const first=build(),again=build();
 assert.equal(first.sha256,again.sha256,'A7 witness not byte reproducible');
 if(process.argv[2])fs.writeFileSync(process.argv[2],first.content);
 console.log('A7_WBB_PREFLIGHT '+JSON.stringify({sha256:first.sha256,bytes:Buffer.byteLength(first.content),blockly:'13.2.1',roundtrip:true}));
}
