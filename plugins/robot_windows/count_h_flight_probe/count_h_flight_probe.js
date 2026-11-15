'use strict';
// CI physical-feasibility probe only: no Blockly, no pupil .wbb,
// no product A6 SCENE registry or real-Crazyflie capability assertion.
// Standard WebeeBlocks runtime-v2 commands drive actual PID/motors.
let chain=Promise.resolve();
function report(event,detail) {
  chain=chain.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw new Error('observer rejected '+event);}));
  return chain;
}
window.addEventListener('error', e=>report('A6_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>report('A6_ERROR',{message:String(e.reason)}));
(async()=>{
  try {
    const response=await window.WB_A6_BOOTSTRAP;
    if(!response||!response.ok)throw new Error('HTML bootstrap not acknowledged');
    const configResponse=await fetch('http://127.0.0.1:8765/a6-variant');
    if(!configResponse.ok)throw new Error('A6 CI variant unavailable');
    const config=await configResponse.json();
    const variant=config&&config.variant;
    if(!Number.isInteger(variant)||variant<1||variant>3)
      throw new Error('invalid A6 CI native variant');
    await report('A6_JS_STARTED',{mode:'native-motor-no-Blockly',variant});
    const module=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new module.default();
    const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
      {simulationScenes:true,timeoutMs:60000});
    bridge.receive=s=>backend.handleMessage(String(s));
    await backend.waitUntilReady();
    await report('A6_RUNTIME_READY',{native:true});
    // Private test request: the product backend intentionally does NOT list
    // A6 among admitted activity profiles. This does NOT qualify that missing
    // product scene integration; only our isolated CI adapter accepts it.
    await backend._request(['SCENE','count-h-'+variant+'-v1']);
    await report('A6_SCENE_ACK',{diagnosticOnly:true,variant});
    await backend.setSpeed(0.20);
    await backend.takeoff(0.40);
    await report('A6_TAKEOFF',{height_m:.40});
    // A native pilot MOVE returns when it is within 0.03 m of its target.
    // After six 0.48 m relative moves the measured touchdown was x=1.359920,
    // outside the untouched target x=1.480 +/- 0.060. Correct the program,
    // never the real contact/mission oracle or runtime tolerances.
    for(let i=0;i<6;i++)await backend.move('forward',0.48);
    await backend.move('forward',0.12);
    await report('A6_CORRIDOR_DONE',{moves:7,distance_m:3.00,variant});
    // Diagnostic reference trajectory, NOT a pupil algorithm. After the
    // terminal screen has been passed at y=0, land on the scene's own pad.
    if(variant===2)await backend.move('left',0.55);
    if(variant===3)await backend.move('right',0.55);
    await report('A6_PAD_SELECTED',{variant,side:variant===1?'center':variant===2?'left':'right'});
    await backend.land();
    await report('A6_LANDED',{nativeReply:true});
    await report('A6_TEST_COMPLETE',{testOnly:true});
  }catch(error){
    await report('A6_ERROR',{message:String(error&&(error.stack||error.message)||error)});
  }
})();
