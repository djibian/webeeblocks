'use strict';
// Draft-only private motor/PID feasibility experiment, NOT a pupil .wbb.
// The same script runs in both gate worlds; no hidden variant determines the
// route. Physical G is read with the authentic Multi-ranger at the approach.
let queue=Promise.resolve();
function report(event,detail){
  queue=queue.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw Error('A5 test event rejected: '+event);}));
  return queue;
}
window.addEventListener('error',e=>
  report('A5_FACTOR_MOTOR_ERROR',{reason:String(e.message)}));
window.addEventListener('unhandledrejection',e=>
  report('A5_FACTOR_MOTOR_ERROR',{reason:String(e.reason)}));
(async()=>{
 try{
  const boot=await window.WB_A5_FACTOR_BOOTSTRAP;
  if(!boot||!boot.ok)throw Error('A5 browser bootstrap incomplete');
  const response=await fetch('http://127.0.0.1:8765/variant');
  if(!response.ok)throw Error('native private variant endpoint unavailable');
  const config=await response.json();
  if(!config||!['A','B'].includes(config.variant))
    throw Error('unexpected A5 gate experiment variant');
  if(config.mode!=='positive'&&config.mode!=='blind')
    throw Error('unexpected A5 test mode');
  await report('A5_FACTOR_MOTOR_JS_STARTED',{testOnly:true});
  const mod=await import('../blockly_v2/webots/RobotWindow.js');
  const bridge=new mod.default();
  const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
    {simulationScenes:true,simulationReset:true,timeoutMs:90000});
  bridge.receive=s=>backend.handleMessage(String(s));
  await backend.waitUntilReady();
  await report('A5_FACTOR_MOTOR_READY',{testOnly:true});
  // Scene admission is conditional on the seven native physical Solids,
  // never on an active published student profile or script metadata.
  await backend._request(['SCENE','a5-factor-g-'+(config.variant==='A'?'left':'right')+'-proto']);
  await report('A5_FACTOR_MOTOR_SCENE_ACK',{testOnly:true});
  await backend.setSpeed(.16);
  await backend.takeoff(.50);
  await report('A5_FACTOR_MOTOR_TAKEOFF',{height_m:.50,testOnly:true});
  // Move in the shared corridor BEFORE observing the gate G.
  await backend.move('forward',1.20);
  await backend.move('forward',1.20);
  await backend.move('forward',.10);
  await report('A5_FACTOR_MOTOR_APPROACH',{moves:3,earlyGRead:false,testOnly:true});
  const left=await backend.readRange('left');
  if(!Number.isFinite(left)||left<0||left>2.001)
    throw Error('missing native late left range');
  const chooseLeft=config.mode==='blind'?true:left>1.0;
  await report('A5_FACTOR_MOTOR_G_OBSERVATION',{
    left_m:left,route:chooseLeft?'left':'right',
    decision_source:config.mode==='blind'?'blind_fixed_left':'late_left_only',
    testOnly:true
  });
  await backend.turn(chooseLeft?90:-90);
  await backend.move('forward',.60);
  await backend.turn(chooseLeft?-90:90);
  await backend.move('forward',.85);
  await backend.move('forward',.80);
  await report('A5_FACTOR_MOTOR_GATE_PASSED',{
    route:chooseLeft?'left':'right',testOnly:true
  });
  // H is fixed in this experiment: BOTH G variants must land on left pad.
  // The final shift after G-right demonstrates independent G vs destination.
  if(!chooseLeft){
    await backend.turn(90);
    await backend.move('forward',1.24);
  }
  await report('A5_FACTOR_MOTOR_PAD_SELECTED',{
    side:'left',decision_source:'fixed_H_experimental',testOnly:true
  });
  await backend.land();
  await report('A5_FACTOR_MOTOR_LAND_ACK',{nativeReply:true});
  await report('A5_FACTOR_MOTOR_TEST_COMPLETE',{
    nativeReply:true,pupilWbb:false,missionOracle:false,testOnly:true
  });
 }catch(error){
  await report('A5_FACTOR_MOTOR_ERROR',{
    reason:String(error&&(error.stack||error.message)||error)
  });
 }
})();
