'use strict';
// Stage-only A5 variant selection. The same pupil .wbb is NOT yet flown.
// This checks the actual WWI nonce parser and profile validator, not native
// A5 admission or any browser/robot performance.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
const Backend=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));
const Profiles=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Activities=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const VARIANTS=['reactive-L-a-v2','reactive-L-b-v2','reactive-L-c-v2'];
async function main() {
  const a5=Activities.DOCUMENT.activities.find(p=>p.id==='progression-reactive-v1');
  assert(a5,'historical A5 profile must remain untouched');
  assert.equal(a5.runtime.scene,'legacy-v1');
  const sent=[];
  const backend=new Backend({send:s=>sent.push(s)},{simulationScenes:true,timeoutMs:1500});
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY HELLO');
  for(let i=0;i<VARIANTS.length;i++){
    const scene=VARIANTS[i];
    const profile=JSON.parse(JSON.stringify(a5));
    profile.runtime.scene=scene;
    assert.equal(Profiles.validateProfile(profile,Activities.BLOCK_CATALOG),true);
    const work=backend.prepareActivity(profile);
    const packet=sent.at(-1);
    const result=packet.match(/^WEBEEBLOCKS_RUNTIME_V2 REQUEST ([0-9]+) SCENE (reactive-L-[abc]-v2) ([0-9a-f]{64})$/);
    assert(result,packet);
    assert.equal(result[2],scene);
    assert.equal(backend.sceneIdentity,null,'no A5 READY before native nonce ACK');
    backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+result[1]+' OK');
    assert.equal(backend.sceneIdentity,null,'legacy OK must never authorize scene');
    backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+result[1]+' SCENE_OK '+result[3]);
    await work;
    assert.equal(backend.sceneIdentity,scene);
  }
  assert.equal(sent.length,3);
  const invalid=['reactive-L-v2','reactive-L-d-v2','reactive-L-a-v1','reactive-L-../../',
                 'nonexistent-v2',''];
  for(const scene of invalid){
    const profile=JSON.parse(JSON.stringify(a5));
    profile.runtime.scene=scene;
    assert.throws(()=>Profiles.validateProfile(profile,Activities.BLOCK_CATALOG),/scene/);
    await assert.rejects(()=>backend.prepareActivity(profile),e=>e&&e.code==='SCENE_UNAVAILABLE');
  }
  assert.equal(sent.length,3,'invalid scene token caused native request');
  const physical=fs.readFileSync(path.join(ROOT,'controllers/crazyflie_runtime_v2/activity_scene.cpp'),'utf8');
  for(const scene of VARIANTS)
    assert(!physical.includes(scene),'a physical runtime was modified to accept staged A5');
  console.log('PASS A5 staged school tokens: 3 nonce-bound scene ACKs; 6 invalid tokens rejected; historical profile and physical runtime unchanged');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
