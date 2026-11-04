'use strict';
const assert=require('assert'),vm=require('vm'),fs=require('fs');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const source=fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js','utf8');
// Cross-profile guard: the variable Linux route keeps the same motion contract.
require('./test_grand_prix_route_profile.js');
function compose(loops){
 const catalog=Object.assign({},Activities.BLOCK_CATALOG);
 if(loops)catalog.controls_whileUntil={category:'control'};else delete catalog.controls_whileUntil;
 const context={WebeeBlocksActivities:{BLOCK_CATALOG:catalog,DOCUMENT:Activities.DOCUMENT},WebeeBlocksActivityProfiles:Profiles,
  WebeeBlocksRuntimeOutcome:{classify:()=>({})},Blockly:{inject:(a,o)=>o},
  WebeeBlocksWwiBackend:function(r,o){this.capabilities={simulationScenes:o.simulationScenes};}};
 context.window=context;vm.runInNewContext(source,context);
 const profile=Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,context.WebeeBlocksInitialActivityId,catalog);
 assert.strictEqual(profile.id,'progression-grand-prix-u-v1');
 assert.strictEqual(profile.runtime.maxSteps,20000);
 for(const type of ['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_vertical'])
  assert.strictEqual(profile.toolbox.filter(entry=>entry===type).length,1,'one block per movement');
 assert.strictEqual(profile.parameterBounds.math_number.NUM.step,0.01);
 assert.strictEqual(profile.parameterBounds.math_number.NUM.min,-1000);
 assert.strictEqual(profile.toolbox.includes('controls_whileUntil'),loops);
 assert.strictEqual(profile.toolbox.includes('webeeblocks_v2_until'),true);
 assert.strictEqual(profile.runtime.astBounds['while.max_iterations'].max,100);
 assert.strictEqual(profile.runtime.allowedStatementKinds.includes('while'),true);
 assert.throws(()=>Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,'reactive-obstacle-v2',catalog),/exactly once/);
 for(const key of ['seed','gateCount','lap','position'])assert(!Object.hasOwn(profile,key));
 assert.strictEqual(new context.WebeeBlocksWwiBackend({},{}).capabilities.simulationScenes,false);
 for(const maxSteps of [0,20001,Infinity,1.5])assert.throws(()=>Profiles.validateProfile(Object.assign({},profile,{runtime:Object.assign({},profile.runtime,{maxSteps})}),catalog),/maxSteps/);
 assert.strictEqual(context.WebeeBlocksRuntimeOutcome.classify({code:'TIME_LIMIT'}).state,'MISSION ÉCHOUÉE');
 return profile;
}
// Exercise the actual shared startup code up to the first Blockly-injection
// dependency: a mission-only profile must display its instructions immediately,
// not only after opening the activity chooser.
async function checkStartupBrief(profile, expected) {
 const main=fs.readFileSync('plugins/robot_windows/blockly_v2/main.js','utf8');
 const elements={activityTitle:{},activityGoal:{},submit:{}};
 const context={
  document:{currentScript:{src:'http://localhost/blockly_v2/main.js'},
   getElementById:id=>elements[id]||(elements[id]={})},
  Blockly:{Theme:{defineTheme:()=>({})},Themes:{Classic:{}}},
  WebeeBlocksActivityProfiles:{
   createFieldOptionController:()=>({setProfile:()=>{}}),
   resolveById:()=>profile
  },
  WebeeBlocksActivities:{DOCUMENT:{activities:[profile]},BLOCK_CATALOG:Activities.BLOCK_CATALOG},
  WebeeBlocksInitialActivityId:profile.id
 };
 context.window=context;
 vm.runInNewContext(main,context,{filename:'blockly_v2/main.js'});
 context.applySemanticBuiltinStyles=()=>{throw new Error('BRIEF_STARTUP_PROBE_STOP');};
 await assert.rejects(context.onload(),/BRIEF_STARTUP_PROBE_STOP/);
 assert.strictEqual(elements.activityTitle.textContent,profile.brief.title);
 assert.strictEqual(elements.activityGoal.textContent,expected);
}
const grandPrix=compose(false);compose(true);
assert(source.includes('210 secondes'));assert(source.includes('0,60 m'));assert(!source.includes('5 points'));
const legacy=Activities.DOCUMENT.activities.find(p=>p.brief && p.brief.goal && !p.brief.mission);
assert(legacy,'existing goal-only activity must remain covered');
const both=Object.assign({},grandPrix,{brief:Object.assign({},grandPrix.brief,{goal:'Incorrect fallback'})});
Promise.all([
 checkStartupBrief(grandPrix,grandPrix.brief.mission),
 checkStartupBrief(both,grandPrix.brief.mission),
 checkStartupBrief(legacy,legacy.brief.goal)
]).then(()=>console.log('PASS U mission visible at startup; mission priority and existing goal profiles preserved'))
 .catch(error=>{console.error(error);process.exitCode=1;});
