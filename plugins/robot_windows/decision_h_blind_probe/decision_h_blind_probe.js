'use strict';
/* CI-only physical blind-path counterexamples for pedagogical A4.
 * No Blockly condition or range request: deliberately apply the B-side
 * high path to scene A and A-side low path to scene B.
 * Native C oracle must reject real physics before learner completion.
 */
let blindQueue=Promise.resolve();
function report(event,detail) {
  blindQueue=blindQueue.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw Error('event refused '+event);}));
  return blindQueue;
}
function assert(x,message){if(!x)throw Error(message);}
async function outcome(backend) {
  const stop=Date.now()+25000;
  while(Date.now()<stop) {
    try {
      const result=await backend.readActivityOutcome({
        type:'mission-state-v1',oracle:'progression-decision-h-v1'});
      if(result.status==='not-achieved')return result;
      throw Error('unacceptable blind native verdict '+JSON.stringify(result));
    }catch(e) {
      if(!e||e.code!=='OUTCOME_UNAVAILABLE')throw e;
      await new Promise(r=>setTimeout(r,200));
    }
  }
  throw Error('no independent native refusal on blind route');
}
window.addEventListener('error',e=>report('A4_BLIND_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>report('A4_BLIND_ERROR',{message:String(e.reason)}));
(async()=>{
  try {
    assert(window.WB_A4_BLIND_BOOTSTRAP,'HTML blind witness not loaded');
    assert((await window.WB_A4_BLIND_BOOTSTRAP)?.ok,
      'native browser bootstrap not acknowledged');
    await report('A4_BLIND_JS_STARTED',{kind:'real-school-physics-no-range'});
    const module=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new module.default();
    const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000,
       outcomeSettleMs:25000});
    bridge.receive=s=>backend.handleMessage(String(s));
    await backend.waitUntilReady();
    await report('A4_BLIND_RUNTIME_READY',{native:true});
    for(const variant of ['a','b']) {
      await backend.prepareActivity({runtime:{scene:'decision-h-'+variant+'-v1'}});
      await report('A4_BLIND_SCENE_READY',{variant});
      await backend.setSpeed(0.1);
      await backend.takeoff(0.50);
      await backend.vertical('up',0.25);
      await backend.move('forward',0.20);
      const wrong=variant==='a'?'high-on-H':'low-on-threshold';
      if(variant==='a')await backend.vertical('up',0.10);
      else await backend.vertical('down',0.35);
      // Probe is deliberately not interpreting a .wbb: no sensor is read,
      // and no correct branch can be selected for either physical scene.
      await report('A4_BLIND_WRONG_BRANCH_STARTED',{variant,wrong});
      let movementError=null;
      try{await backend.move('forward',0.75);}
      catch(error){movementError=String(error?.code||error?.message||error);}
      const refused=await outcome(backend);
      assert(refused.status==='not-achieved','blind route was not refused');
      await report('A4_BLIND_NATIVE_REFUSED',{variant,wrong,
        status:refused.status,movementError});
      if(variant==='a') {
        await backend.resetSimulation();
        await report('A4_BLIND_NATIVE_RESET',{between:'a,b'});
      }
    }
    await report('A4_BLIND_TEST_COMPLETE',{variants:['a','b'],
      status:'both-native-not-achieved',rangeReads:0});
  } catch(error) {
    await report('A4_BLIND_ERROR',{message:String(error?.stack||error)});
  }
})();
