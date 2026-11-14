'use strict';
// CI-only native flight: actual classroom Webots dynamics and independent C
// orientation oracle. This deliberately DOES NOT claim a student Blockly/.wbb
// profile; that separate product integration must be qualified later.
const ORIENT_PROFILE = {id:'ci-orientation-native',runtime:{scene:'orientation-v1'}};
const ORIENT_ORACLE = {type:'mission-state-v1',oracle:'progression-orientation-3d-v1'};
let orientChain=Promise.resolve();
function orientReport(event,detail) {
  orientChain=orientChain.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw new Error('observer rejected '+event);}));
  return orientChain;
}
async function orientOutcome(backend) {
  const until=Date.now()+80000;
  while(Date.now()<until) {
    try {
      const actual=await backend.readActivityOutcome(ORIENT_ORACLE);
      if(actual.status!=='achieved')
        throw new Error('native orientation refused '+JSON.stringify(actual));
      return actual;
    }catch(error) {
      if(!error || error.code!=='OUTCOME_UNAVAILABLE')throw error;
      await new Promise(r=>setTimeout(r,200));
    }
  }
  throw new Error('no native orientation outcome');
}
window.addEventListener('error',e=>orientReport('ORIENT_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>orientReport('ORIENT_ERROR',{message:String(e.reason)}));
(async()=>{
  try {
    if(!window.WB_ORIENT_BOOTSTRAP)throw new Error('missing HTML bootstrap');
    const first=await window.WB_ORIENT_BOOTSTRAP;
    if(!first||!first.ok)throw new Error('HTML bootstrap not acknowledged');
    await orientReport('ORIENT_JS_STARTED',{kind:'native-R2025a-no-Blockly'});
    const module=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new module.default();
    const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000});
    bridge.receive=s=>backend.handleMessage(String(s));
    await backend.waitUntilReady();
    await orientReport('ORIENT_RUNTIME_READY',{native:true});
    await backend.prepareActivity(ORIENT_PROFILE);
    await orientReport('ORIENT_SCENE_ACK',{scene:'orientation-v1'});

    // First leg: +X towards A, rotate right so heading is global -Y.
    await backend.setSpeed(0.12);
    await backend.takeoff(0.63);
    await backend.move('forward',0.45);
    await backend.turn(-90);
    await orientReport('ORIENT_A_TURNED',{heading_deg:-90});
    // Second leg: ascend 0.16 m, move along -Y, rotate left for global +X.
    await backend.vertical('up',0.16);
    await backend.move('forward',0.45);
    await backend.turn(90);
    await orientReport('ORIENT_B_TURNED',{heading_deg:0});
    // Third leg: descend 0.16 m, move +X, rotate right for final -Y leg.
    await backend.vertical('down',0.16);
    await backend.move('forward',0.45);
    await backend.turn(-90);
    await orientReport('ORIENT_C_TURNED',{heading_deg:-90});
    await backend.move('forward',0.45);
    await backend.land();
    await orientReport('ORIENT_LANDED',{native:true});
    await backend.completeActivityMission(ORIENT_ORACLE);
    await orientOutcome(backend);
    await orientReport('ORIENT_NATIVE_ACHIEVED',{status:'achieved'});
    await orientReport('ORIENT_TEST_COMPLETE',{checkpoints:3,status:'achieved'});
  }catch(error) {
    await orientReport('ORIENT_ERROR',{message:String(error&&(error.stack||error.message)||error)});
  }
})();
