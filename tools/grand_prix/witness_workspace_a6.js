'use strict';
// Draft-only genuine Blockly 13.2.1 witness. No course ID enters this pupil file.
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require('../../plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js');
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast.js');
Semantic.installConditionalLoopBounds(Blockly);delete global.Blockly;
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities.js');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract.js');
const Files=require('../../plugins/robot_windows/blockly/webeeblocks/project_files.js');
const ID='grand-prix-a6-native-experimental-v1';
const l={id:'a6-l',name:'gauche'},r={id:'a6-r',name:'droite'};
const n=value=>({kind:'number',value});
const range=direction=>({kind:'range',direction,unit:'m'});
const minus=(left,right)=>({kind:'arithmetic',op:'MINUS',left,right});
const less=(left,right)=>({kind:'compare',op:'LT',left,right});
const v=variable=>({kind:'variable_get',variable});
function reference(){
 return {version:1,semantics:'webeeblocks-ast-v1',program:[
   {kind:'takeoff',height_m:.9},
   {kind:'set_speed',speed_m_s:.2},
   {kind:'move',direction:'forward',distance_m:minus(range('front'),n(.14))},
   {kind:'set_variable',variable:l,value:range('left')},
   {kind:'set_variable',variable:r,value:range('right')},
   {kind:'if',condition:{kind:'logic',op:'AND',
     left:less(v(l),n(.45)),right:less(v(r),n(.45))},
     then:[{kind:'vertical',direction:'down',distance_m:.42},
       {kind:'move',direction:'forward',distance_m:.60},
       {kind:'vertical',direction:'up',distance_m:.42},
       {kind:'move',direction:'forward',distance_m:minus(range('front'),n(.66))}],
     else:[{kind:'move',direction:'back',distance_m:.54}]},
   {kind:'land'}
 ]};
}
function build(){
 const profile=Profiles.resolveById(Activities.DOCUMENT,ID,Activities.BLOCK_CATALOG);
 const expected=reference();
 const ws=new Blockly.Workspace(),reopened=new Blockly.Workspace();let serial=0;
 function block(type,fields={}){
   const b=ws.newBlock(type,'a6-b-'+(++serial));
   Object.entries(fields).forEach(([name,value])=>b.setFieldValue(String(value),name));
   return b;
 }
 function attach(b,input,child){
   const target=b.getInput(input).connection;
   assert(target&&child,'Blockly socket absent: '+input);
   target.connect(child.outputConnection||child.previousConnection);
 }
 function variable(ref){
   const map=ws.getVariableMap();
   return map.getVariableById(ref.id)||map.createVariable(ref.name,'',ref.id);
 }
 function expr(e){
   if(e.kind==='number')return block('math_number',{NUM:e.value});
   if(e.kind==='range')return block('webeeblocks_v2_range',{DIRECTION:e.direction});
   if(e.kind==='variable_get')return block('variables_get',{VAR:variable(e.variable).getId()});
   const types={arithmetic:'math_arithmetic',compare:'logic_compare',logic:'logic_operation'};
   assert(types[e.kind],'unknown expression kind '+e.kind);
   const b=block(types[e.kind],{OP:e.op});
   attach(b,'A',expr(e.left));attach(b,'B',expr(e.right));return b;
 }
 function sequence(seq){
   let head=null,tail=null;
   for(const s of seq){
     let b;
     switch(s.kind){
       case 'takeoff':
         b=block('webeeblocks_v2_takeoff');attach(b,'HEIGHT',expr(n(s.height_m)));break;
       case 'set_speed':b=block('webeeblocks_v2_speed',{SPEED:s.speed_m_s});break;
       case 'move':
         b=block('webeeblocks_v2_move',{DIRECTION:s.direction});
         attach(b,'DISTANCE',expr(typeof s.distance_m==='number'?n(s.distance_m):s.distance_m));break;
       case 'vertical':
         b=block('webeeblocks_v2_vertical',{DIRECTION:s.direction});
         attach(b,'DISTANCE',expr(n(s.distance_m)));break;
       case 'set_variable':
         b=block('variables_set',{VAR:variable(s.variable).getId()});
         attach(b,'VALUE',expr(s.value));break;
       case 'if':
         b=block('controls_if');b.loadExtraState({hasElse:true});
         attach(b,'IF0',expr(s.condition));attach(b,'DO0',sequence(s.then));attach(b,'ELSE',sequence(s.else));break;
       case 'land':b=block('webeeblocks_v2_land');break;
       default:throw Error('unknown statement '+s.kind);
     }
     if(tail)tail.nextConnection.connect(b.previousConnection);else head=b;
     tail=b;
   }
   return head;
 }
 try{
   sequence(expected.program);
   Contract.preflightWorkspace(profile,ws);
   const ast=Semantic.compileWorkspace(ws);
   Contract.preflightAst(profile,ast);
   assert.deepStrictEqual(ast,expected,'Blockly AST mismatch');
   const project={format:'webeeblocks-project',version:1,
     activity:{id:profile.id,semantics:ast.semantics},
     workspace:Blockly.serialization.workspaces.save(ws)};
   let next=0;
   // Untyped Blockly shadow/mutation state can also own randomly generated IDs.
   // Never rewrite pupil variable IDs: their identities belong to the AST.
   function stableIds(node){
     if(Array.isArray(node)){node.forEach(stableIds);return;}
     if(!node||typeof node!=='object')return;
     for(const [key,value] of Object.entries(node)){
       if(key==='id'&&typeof value==='string'&&value!==l.id&&value!==r.id)
         node[key]='a6-block-'+(++next);
       else stableIds(value);
     }
   }
   stableIds(project.workspace);
   const content=JSON.stringify(project)+'\n';
   const result=Files.validateProjectText(content,profile,{Blockly,
     profiles:Profiles,activitiesDocument:Activities.DOCUMENT,
     blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Semantic,activityContract:Contract});
   assert.deepStrictEqual(result.ast,ast);
   Blockly.serialization.workspaces.load(project.workspace,reopened);
   Contract.preflightWorkspace(profile,reopened);
   const roundtrip=Semantic.compileWorkspace(reopened);
   Contract.preflightAst(profile,roundtrip);
   assert.deepStrictEqual(roundtrip,ast,'WBB reopen changed the program');
   return {ast,content,sha256:crypto.createHash('sha256').update(content).digest('hex')};
 }finally{reopened.dispose();ws.dispose();}
}
module.exports={build,reference};
if(require.main===module){
 const a=build(),b=build();
 if(a.sha256!==b.sha256){
   const x=JSON.parse(a.content),y=JSON.parse(b.content);
   function difference(u,v,path){
     if(JSON.stringify(u)===JSON.stringify(v))return null;
     if(!u||!v||typeof u!=='object'||typeof v!=='object')
       return {path,first:u,second:v};
     for(const key of new Set([...Object.keys(u),...Object.keys(v)])){
       const result=difference(u[key],v[key],path.concat(key));
       if(result)return result;
     }
     return {path,kind:'object-shape'};
   }
   console.error('A6_WBB_BYTE_DIFFERENCE '+JSON.stringify(difference(x,y,[])));
 }
 assert.equal(a.sha256,b.sha256,'WBB bytes vary between builds');
 if(process.argv[2])fs.writeFileSync(process.argv[2],a.content);
 console.log('A6_WBB_PREFLIGHT '+JSON.stringify({sha256:a.sha256,roundtrip:true,blockly:'13.2.1'}));
}
