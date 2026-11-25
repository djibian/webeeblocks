'use strict';
// A8 experimental autonomous sensor-only Blockly witness; never a pupil starter.
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
     assert.equal(key,'data-progression-activity');return null;
   }}}};
 host.window=host;
 vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/setup.js','utf8'),host);
 const activitiesDocument=host.WebeeBlocksActivities.DOCUMENT;
 const profile=Profiles.resolveById(activitiesDocument,host.WebeeBlocksInitialActivityId,Activities.BLOCK_CATALOG);
 assert.equal(profile.id,'progression-grand-prix-route-v2');
 return {profile,options:{Blockly,profiles:Profiles,activitiesDocument,
   blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Semantic,activityContract:Contract}};
}
const variables=Object.fromEntries(['front','left','right','count'].map(name=>
 [name,{id:'a8-'+name,name:({front:'avant',left:'gauche',right:'droite',count:'portes'})[name]}]));
const n=value=>({kind:'number',value}),range=direction=>({kind:'range',direction,unit:'m'});
const v=name=>({kind:'variable_get',variable:variables[name]});
const binary=(kind,op,left,right)=>({kind,op,left,right});
const gt=(a,b)=>binary('compare','GT',a,b),lt=(a,b)=>binary('compare','LT',a,b),
 eq=(a,b)=>binary('compare','EQ',a,b);
const and=(a,b)=>binary('logic','AND',a,b);
const sub=(a,b)=>binary('arithmetic','MINUS',a,b),add=(a,b)=>binary('arithmetic','ADD',a,b);
const motion=(direction,distance_m)=>({kind:'move',direction,distance_m});
const set=(name,value)=>({kind:'set_variable',variable:variables[name],value});
const loop=(max_iterations,condition,body)=>({kind:'while',mode:'WHILE',max_iterations,condition,body});
const iff=(condition,then,otherwise=[])=>Object.assign({kind:'if',condition,then},
 otherwise.length?{else:otherwise}:{});

// One program for 12 routes; no index, length, seed, or oracle input.
// At 0.18 m from a physical face, an open H has both side posts; a corner
// has one side wall. Move back to 0.32 m from H face (0.34 m to centre),
// traverse 0.68 m at low altitude, then climb. Refine corner to 0.28 m
// from its front face and terminal to 0.68 m (0.70 m from panel centre).
// This separate witness is for the pre-revision main geometry only.
// These are unqualified sensor-based hypotheses, not safety overrides.
function reference(wrongLanding=false){
 const definitions={};
 const call=name=>({kind:'call',name,body:structuredClone(definitions[name])});
 const scan=[set('left',range('left')),set('right',range('right'))];
 const align=distance=>[set('front',range('front')),
   iff(gt(v('front'),n(Number((distance+.01).toFixed(2)))),[motion('forward',sub(v('front'),n(distance)))],
     [iff(lt(v('front'),n(Number((distance-.01).toFixed(2)))),[motion('back',sub(n(distance),v('front')))])])];
 definitions.approach=[set('front',range('front')),
   loop(4,gt(v('front'),n(1.7)),[motion('forward',1),set('front',range('front'))]),
   ...align(.18),...scan];
 definitions.leg=[call('approach'),
   iff(and(lt(v('left'),n(.45)),lt(v('right'),n(.45))),[
     ...align(.32),{kind:'vertical',direction:'down',distance_m:.41},motion('forward',.68),
     {kind:'vertical',direction:'up',distance_m:.41},set('count',add(v('count'),n(1))),call('approach')])];
 definitions.corner=[...align(.28),...scan,
   iff(and(lt(v('right'),n(.45)),gt(v('left'),n(.45))),[{kind:'turn',angle_deg:90}],
    [iff(and(lt(v('left'),n(.45)),gt(v('right'),n(.45))),[{kind:'turn',angle_deg:-90}])])];
 const landing=wrongLanding
   ? [iff(eq(v('count'),n(1)),[motion('left',.50)],
       [iff(eq(v('count'),n(2)),[motion('right',.50)])])]
   : [iff(eq(v('count'),n(2)),[motion('left',.50)],
       [iff(eq(v('count'),n(3)),[motion('right',.50)])])];
 return {definitions,ast:{version:1,semantics:'webeeblocks-ast-v1',program:[
   {kind:'takeoff',height_m:.88},{kind:'set_speed',speed_m_s:.2},
   ...Object.keys(variables).map(name=>set(name,n(0))),
   call('leg'),call('corner'),call('leg'),call('corner'),call('leg'),
   ...align(.68),...landing,{kind:'land'}]}};
}
function normalizeIds(project){
 const ids=new Set(Object.values(variables).map(x=>x.id));let index=0;
 function visit(obj){
   if(Array.isArray(obj)){obj.forEach(visit);return;}
   if(!obj||typeof obj!=='object')return;
   for(const [key,value] of Object.entries(obj)){
     if(key==='id'&&typeof value==='string'&&!ids.has(value))obj[key]='a8-block-'+(++index);
     else visit(value);
   }
 }
 visit(project.workspace);
}
function build(wrongLanding=false){
 const {profile,options}=school(),expected=reference(wrongLanding);
 const ws=new Blockly.Workspace();let index=0;
 const block=(type,fields={})=>{
   const b=ws.newBlock(type,'a8-builder-'+(++index));
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
   const types={compare:'logic_compare',logic:'logic_operation',arithmetic:'math_arithmetic'};
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
         input(b,'DISTANCE',expr(typeof s.distance_m==='number'?n(s.distance_m):s.distance_m));break;
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
       default:throw Error('unsupported A8 Blockly statement '+s.kind);
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
   assert.deepStrictEqual(ast,expected.ast,'A8 real Blockly program AST mismatch');
   const project=Files.createProject(profile,ws,options);
   normalizeIds(project);
   const content=JSON.stringify(project,null,2)+'\n';
   const opened=Files.validateProjectText(content,profile,options);
   assert.deepStrictEqual(opened.ast,ast,'A8 Save/Open changes AST');
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
 assert(opened.ast,'A8 saved program has no executable AST');
 assert(opened.ast.program.some(s=>s.kind==='call'),'missing A8 procedure');
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
module.exports={build,runSaved,reference};
if(require.main===module){
 const args=process.argv.slice(2),wrongLanding=args.includes('--wrong-landing');
 const files=args.filter(arg=>arg!=='--wrong-landing');
 assert(files.length<=1 && files.every(file=>!file.startsWith('--')),'A8 invalid witness arguments');
 const first=build(wrongLanding),again=build(wrongLanding);
 assert.equal(first.sha256,again.sha256,'A8 witness not byte reproducible');
 if(files[0])fs.writeFileSync(files[0],first.content);
 console.log('A8_WBB_PREFLIGHT '+JSON.stringify({sha256:first.sha256,bytes:Buffer.byteLength(first.content),blockly:'13.2.1',roundtrip:true,wrongLanding}));
}
