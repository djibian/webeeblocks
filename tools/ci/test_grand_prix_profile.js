'use strict';
const assert=require('assert'),vm=require('vm'),fs=require('fs');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const source=fs.readFileSync('plugins/robot_windows/grand_prix/setup.js','utf8');
function compose(loops){
 const catalog=Object.assign({},Activities.BLOCK_CATALOG);
 if(loops)catalog.controls_whileUntil={category:'control'};else delete catalog.controls_whileUntil;
 const context={WebeeBlocksActivities:{BLOCK_CATALOG:catalog,DOCUMENT:Activities.DOCUMENT},WebeeBlocksActivityProfiles:Profiles,Blockly:{inject:(a,o)=>o},WebeeBlocksWwiBackend:function(r,o){this.capabilities={simulationScenes:o.simulationScenes};this.takeoff=async()=>{};this._request=async()=>{};}};
 context.window=context;vm.runInNewContext(source,context);
 const profile=Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,context.WebeeBlocksInitialActivityId,catalog);
 assert.strictEqual(profile.id,'progression-grand-prix-v1');assert.strictEqual(profile.runtime.maxSteps,20000);
 assert.strictEqual(profile.toolbox.includes('controls_whileUntil'),loops);
 assert.strictEqual(profile.runtime.allowedStatementKinds.includes('while'),loops);
 assert.throws(()=>Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,'reactive-obstacle-v2',catalog),/exactly once/,'legacy project must not be silently remapped');
 assert.throws(()=>context.WebeeBlocksActivities.getProfile('unknown'),/unknown/);
 for(const key of ['seed','gateCount','lap','position'])assert(!Object.hasOwn(profile,key));
 const backend=new context.WebeeBlocksWwiBackend({},{});assert.strictEqual(backend.capabilities.simulationScenes,false);
 for(const maxSteps of [0,20001,Infinity,1.5])assert.throws(()=>Profiles.validateProfile(Object.assign({},profile,{runtime:Object.assign({},profile.runtime,{maxSteps})}),catalog),/maxSteps/);
}
compose(false);compose(true);
console.log('PASS Grand Prix profile: explicit startup context, compatible .wbb identity, bounded budget, no injected layout facts and independent-loop capability composition');
