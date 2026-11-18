'use strict';
// Draft-only private motor/PID 2x2 H/G experiment, NOT a pupil .wbb.
// A single identical script reads the initial H from the real left range,
// observes G later, and chooses its physical route and pad from those readings.
// The CI-only variant selects a world, never a solution branch.
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
  if(!config||!['A','B','C','D'].includes(config.variant))
    throw Error('unexpected A5 gate experiment variant');
  if(config.mode!=='positive'&&config.mode!=='blind'&&
     config.mode!=='blind_h'&&config.mode!=='blockly'&&
     config.mode!=='blockly_fixed')
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
  const gateLeft=['A','C'].includes(config.variant);
  const farH=['C','D'].includes(config.variant);
  const scene=(farH?'a5-factor-hfar-g-':'a5-factor-g-')+
    (gateLeft?'left':'right')+'-proto';
  await backend._request(['SCENE',scene]);
  await report('A5_FACTOR_MOTOR_SCENE_ACK',{testOnly:true});
  if(config.mode==='blockly'||config.mode==='blockly_fixed'){
    const witness=await import('../a5_alias_motor_probe/a5_private_blockly_probe.js');
    await witness.runPrivateBlockly(backend,report,
      config.mode==='blockly_fixed'?'fixed':'reactive');
    return;
  }
  await backend.setSpeed(.16);
  await backend.takeoff(.50);
  await report('A5_FACTOR_MOTOR_TAKEOFF',{height_m:.50,testOnly:true});
  // Positive witness: early H must be observed and remembered for its pad.
  // Negative witness: omit the read itself, not merely its later use.
  // The latter cannot claim to be a genuinely blind program otherwise.
  let initialH=null;
  if(config.mode!=='blind_h'){
    initialH=await backend.readRange('left');
    if(!Number.isFinite(initialH)||initialH<0||initialH>2.001)
      throw Error('missing genuine initial H observation');
  }
  const targetRight=config.mode==='blind_h'?false:initialH>.80;
  if(config.mode==='blind_h')
    await report('A5_FACTOR_MOTOR_H_OMITTED',{
      initial_range_requested:false,destination:'left',testOnly:true
    });
  else
    await report('A5_FACTOR_MOTOR_H_OBSERVATION',{
      left_m:initialH,destination:targetRight?'right':'left',
      decision_source:'initial_left_only',testOnly:true
    });
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
  // The gate's opening is independent of the H-indicated final destination.
  // Once beyond the true gate, shift laterally only when the two sides differ.
  if(chooseLeft===targetRight){
    await backend.turn(targetRight?-90:90);
    await backend.move('forward',1.24);
  }
  await report('A5_FACTOR_MOTOR_PAD_SELECTED',{
    side:targetRight?'right':'left',
    decision_source:config.mode==='blind_h'?'blind_no_initial_read':'initial_left_only',
    testOnly:true
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
