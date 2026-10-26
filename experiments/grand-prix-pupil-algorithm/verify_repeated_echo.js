'use strict';
// Adversarial MODEL, not a Webots or physical sensor recording.
// Evaluates BOTH real Blockly WBBs through the production AST interpreter.
// Repeated plausible-looking local H echoes are deliberate, not hidden mission input.
const assert = require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..');
const original=path.join(__dirname,'GP232_reference_main17671.wbb');
const candidate=path.join(__dirname,'Grand-Prix-sans-murs-algorithme-candidat.wbb');
const Blockly=require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly'));
require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
global.Blockly=Blockly;
require(path.join(ROOT,'plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js'));
delete global.Blockly;
const Semantic=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/semantic_ast'));
Semantic.installConditionalLoopBounds(Blockly);
const Contract=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_contract'));
const Activities=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activities'));
const Profiles=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_profiles'));
const Interpreter=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/interpreter'));
const context={Blockly,WebeeBlocksActivities:Activities,WebeeBlocksActivityProfiles:Profiles,
  WebeeBlocksRuntimeOutcome:{classify:()=>({})},WebeeBlocksWwiBackend:function(){}};
context.window=context;
vm.runInNewContext(fs.readFileSync(path.join(ROOT,'plugins/robot_windows/grand_prix_u/setup.js'),'utf8'),context);
const profile=Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,'progression-grand-prix-u-v1',Activities.BLOCK_CATALOG);
function prepare(file,expected){
 const buf=fs.readFileSync(file);
 const sha=crypto.createHash('sha256').update(buf).digest('hex');
 const project=JSON.parse(buf);
 const space=new Blockly.Workspace();
 try {
   Blockly.serialization.workspaces.load(project.workspace,space);
   Contract.preflightWorkspace(profile,space);
   const ast=Semantic.compileWorkspace(space);
   Contract.preflightAst(profile,ast);
   const blocks=space.getAllBlocks(false).length;
   assert.equal(blocks,expected);
   return {ast,sha,blocks};
 }finally{space.dispose();}
}
async function attempt(one){
 let low=false,lastVars={},readCount=0,turns=[],movements=0,landings=0;
 const backend={
   capabilities:{conditionalLoops:true,procedures:true},
   async takeoff(){},async vertical(d){low=(d==='down');},
   async move(){movements++;},async turn(deg){turns.push({deg,portes:lastVars.portes,etat:lastVars['état'],distance:lastVars.distance});},
   async land(){landings++;},
   async readRange(d){
     readCount++;
     if(d==='front')return low?0.70:0.35;
     if(d==='left'||d==='right')return 0.30;
     if(d==='back')return 0.40;
     throw Error('Unexpected sensor '+d);
   }
 };
 let output=null,error=null;
 try {
   output=await Interpreter.run(one.ast,backend,{maxSteps:profile.runtime.maxSteps,
     hooks:{onVariables:e=>{lastVars={...e.values};}}});
 } catch(e){error=String(e?.message||e);}
 return {blocks:one.blocks,sha256:one.sha,turns,readCount,movements,landings,
   finalPortes:output?.variables?.portes??lastVars.portes,firstTurnPortes:turns[0]?.portes??null,error};
}
(async()=>{
 const ref=prepare(original,232),current=prepare(candidate,222);
 const a=await attempt(ref),b=await attempt(current);
 console.log('REPEATED_H_ECHO_SYNTHETIC_TRACE '+JSON.stringify({reference232:a,candidate222:b}));
 assert(a.turns.length>0 && b.turns.length>0,'no first corner was reached in the synthetic scenario');
 if(b.firstTurnPortes>a.firstTurnPortes){
   console.log('REFUTATION: same repeated H echo produces more counted crossings before first turn in 222 than in original 232');
 }else{
   console.log('UNPROVEN: no differential double count for this model; no general safety claim');
 }
 console.log('BOUNDARY: fake sensors cannot establish Webots double detection, physical failure, or classroom comprehension');
})().catch(e=>{console.error('FAIL_SYNTHETIC_REPLAY',e);process.exitCode=1;});
