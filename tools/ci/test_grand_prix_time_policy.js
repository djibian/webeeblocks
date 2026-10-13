'use strict';
const assert=require('assert');
const Policy=require('../grand_prix/reference_policy_time');
const Navigation=require('./fixtures/grand_prix_navigation_e8e3e1a');
const I=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const C=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
function set(name,value){return{kind:'set_variable',variable:{id:'gp-'+name,name},value:{kind:'number',value}};}
function junction(ast){
 let found;
 function body(items){for(let i=0;i<items.length;i++){const node=items[i];
  if(node.kind==='if'&&node.then&&node.then[0]&&node.then[0].kind==='set_variable'&&node.then[0].variable.name==='temps observé')found=items.slice(i,i+2);
  for(const key of ['body','then','else'])if(node[key])body(node[key]);
 }}body(ast.program);assert(found);return found;
}
async function prove(){
 for(const threshold of [180,300,420,480])I.validateExecutionBudget(Policy.build(Navigation,threshold),20000);
 for(const threshold of [true,0,601,NaN,'180'])assert.throws(()=>Policy.build(Navigation,threshold),/invalid public/);
 assert.throws(()=>Policy.build(Navigation,180,-1),/invalid public/);
 const cases=[[180,100,2,1],[480,100,2,0],[480,200,2,1],[480,190,4,1],[480,170,2,1],[480,170,4,0]];
 for(const [threshold,seconds,count,exit] of cases){
  const authored=Policy.build(Navigation,threshold),middle=junction(authored),effects=[];
  const ast={...authored,program:[{kind:'takeoff',height_m:.4},...authored.program.filter(n=>n.kind==='set_variable'),set('coin',3),set('portes',count),...middle,{kind:'land'}]};
  const backend={capabilities:{elapsedSimulationTime:true},takeoff:async()=>effects.push('T'),land:async()=>effects.push('L'),turn:async a=>effects.push(a),readElapsedTime:async()=>seconds};
  const result=await I.run(ast,backend,{maxSteps:20000});
  assert.equal(result.variables.sortie,exit);
  assert.deepStrictEqual(effects,exit?['T','L']:['T',90,'L']);
 }
 const authored=Policy.build(Navigation,180),effects=[];
 await assert.rejects(I.run(authored,{capabilities:{conditionalLoops:true},takeoff:async()=>effects.push('T')},{maxSteps:20000}),/elapsed simulation time unavailable/);
 assert.deepStrictEqual(effects,[]);
 assert.throws(()=>C.preflightAst({runtime:{elapsedSimulationTime:false}},authored),/elapsed simulation time unavailable/);
 const invalid={...authored,program:[{kind:'takeoff',height_m:.4},...authored.program.filter(n=>n.kind==='set_variable'),set('coin',3),set('portes',2),...junction(authored),{kind:'land'}]};
 await assert.rejects(I.run(invalid,{capabilities:{elapsedSimulationTime:true},takeoff:async()=>effects.push('T'),readElapsedTime:async()=>NaN},{maxSteps:20000}),/finite nonnegative/);
 assert.deepStrictEqual(effects,['T']);
 console.log('PASS policy D: exact shared AST/interpreter, public threshold, count and measured-time decisions, original 20000 budget, unsupported clock refusal before takeoff; synthetic decisions only');
}
module.exports=prove;
if(require.main===module)prove().catch(e=>{console.error(e);process.exitCode=1;});
