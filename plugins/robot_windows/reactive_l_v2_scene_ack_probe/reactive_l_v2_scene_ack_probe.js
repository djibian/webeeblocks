'use strict';
// This is a dedicated *browser CI probe*, never a student algorithm or
// automatically installed activity profile. Does not take off or move.
let a5Events=Promise.resolve();
function a5Report(event,detail) {
  a5Events=a5Events.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw Error('A5 event rejected: '+event);}));
  return a5Events;
}
window.addEventListener('error',e=>a5Report('A5_SCENE_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>a5Report('A5_SCENE_ERROR',{message:String(e.reason)}));
(async function() {
  try {
    const bootstrap=await window.WB_A5_SCENE_BOOTSTRAP;
    if(!bootstrap||!bootstrap.ok)throw Error('missing A5 HTML bootstrap');
    await a5Report('A5_SCENE_JS_STARTED',{mode:'CI-only-no-flight'});
    const mod=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new mod.default();
    const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000});
    bridge.receive=s=>backend.handleMessage(String(s));
    await backend.waitUntilReady();
    await a5Report('A5_SCENE_RUNTIME_READY',{type:'native-school-only'});
    const stages=[
      ['A','reactive-L-a-v2'],
      ['B','reactive-L-b-v2'],
      ['C','reactive-L-c-v2']
    ];
    const profile=scene=>({id:'ci-reactive-L-v2',runtime:{scene}});
    for(const [variant,token] of stages) {
      await backend.prepareActivity(profile(token));
      if(backend.sceneIdentity!==token)throw Error('native scene identity not accepted: '+variant);
      await a5Report('A5_SCENE_'+variant+'_ACK',{scene:token,via:'nonce-bound-SCENE_OK'});
      const measured=await backend.readRange('front');
      if(typeof measured!=='number'||!Number.isFinite(measured))
        throw Error('genuine Crazyflie range invalid '+variant);
      await a5Report('A5_SCENE_'+variant+'_RANGE',{front_m:measured});
    }
    await backend.prepareActivity(profile('legacy-v1'));
    await a5Report('A5_SCENE_LEGACY_RESTORED',{scene:'legacy-v1'});
    await backend.prepareActivity(profile('reactive-L-a-v2'));
    await a5Report('A5_SCENE_A_REATTACHED',{scene:'reactive-L-a-v2'});
    await backend.prepareActivity(profile('legacy-v1'));
    await a5Report('A5_SCENE_FINAL_LEGACY',{scene:'legacy-v1'});
    await a5Report('A5_SCENE_TEST_COMPLETE',{native:true,no_pupil_flight:true});
  }catch(error){
    await a5Report('A5_SCENE_ERROR',{message:String(error&&(error.stack||error.message)||error)});
  }
})();
