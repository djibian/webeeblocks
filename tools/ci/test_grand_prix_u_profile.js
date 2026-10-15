'use strict';
const assert=require('assert'),vm=require('vm'),fs=require('fs');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const source=fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js','utf8');
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
 assert.strictEqual(profile.toolbox.includes('controls_whileUntil'),loops);
 assert.strictEqual(profile.runtime.allowedStatementKinds.includes('while'),loops);
 assert.throws(()=>Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,'reactive-obstacle-v2',catalog),/exactly once/);
 for(const key of ['seed','gateCount','lap','position'])assert(!Object.hasOwn(profile,key));
 assert.strictEqual(new context.WebeeBlocksWwiBackend({},{}).capabilities.simulationScenes,false);
 for(const maxSteps of [0,20001,Infinity,1.5])assert.throws(()=>Profiles.validateProfile(Object.assign({},profile,{runtime:Object.assign({},profile.runtime,{maxSteps})}),catalog),/maxSteps/);
 assert.strictEqual(context.WebeeBlocksRuntimeOutcome.classify({code:'TIME_LIMIT'}).state,'MISSION ÉCHOUÉE');
}
compose(false);compose(true);
assert(source.includes('210 secondes'));assert(source.includes('0,60 m'));assert(!source.includes('5 points'));
console.log('PASS U profile, French timeout outcome, generic context and unchanged intermediate catalog');
