'use strict';
// EXPERIMENT ONLY: a private motor/PID feasibility pilot, NOT a Blockly
// student program, activity solution, independent oracle or hardware path.
// The same script on A/B never uses variant identity to choose the pad;
// only the early genuine left Multi-ranger measurement is retained.
let a5AliasReports=Promise.resolve();
function report(event,detail) {
  a5AliasReports=a5AliasReports.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw Error('native A5 event rejected: '+event);}));
  return a5AliasReports;
}
window.addEventListener('error',e=>report('A5_ALIAS_MOTOR_ERROR',{reason:String(e.message)}));
window.addEventListener('unhandledrejection',e=>
  report('A5_ALIAS_MOTOR_ERROR',{reason:String(e.reason)}));
(async()=>{
 try {
  const boot=await window.WB_A5_ALIAS_BOOTSTRAP;
  if(!boot||!boot.ok)throw Error('A5 browser bootstrap not confirmed');
  const response=await fetch('http://127.0.0.1:8765/variant');
  if(!response.ok)throw Error('private native world identity unavailable');
  const config=await response.json();
  const variant=config&&config.variant;
  if(variant!=='A'&&variant!=='B')throw Error('untrusted A5 pilot variant');
  await report('A5_ALIAS_MOTOR_JS_STARTED',{variant,testOnly:true});
  const mod=await import('../blockly_v2/webots/RobotWindow.js');
  const bridge=new mod.default();
  const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
    {simulationScenes:true,simulationReset:true,timeoutMs:90000});
  bridge.receive=s=>backend.handleMessage(String(s));
  await backend.waitUntilReady();
  await report('A5_ALIAS_MOTOR_READY',{variant});
  // Only the private controller accepts this scene: never a production
  // WebeeBlocks activity ID or a pupil-accessible backend capability.
  await backend._request(['SCENE','a5-memory-alias-'+variant.toLowerCase()+'-proto']);
  await report('A5_ALIAS_MOTOR_SCENE_ACK',{variant});
  const savedClue=await backend.readRange('left');
  if(!Number.isFinite(savedClue)||savedClue<0||savedClue>2.001)
    throw Error('early left native range is unavailable');
  await report('A5_ALIAS_MOTOR_EARLY_CUE',{range_m:savedClue});
  // The branching evidence is always from the retained EARLY observation;
  // the late state is never remeasured in this positive reference.
  const goLeft=savedClue<.84;
  await backend.setSpeed(.16);
  await backend.takeoff(.50);
  await report('A5_ALIAS_MOTOR_TAKEOFF',{height_m:.50});
  await backend.move('forward',.70);
  await backend.move('forward',.70);
  await backend.move('forward',.15);
  await report('A5_ALIAS_MOTOR_COMMON_APPROACH',{moves:3,testOnly:true});
  await backend.turn(goLeft?90:-90);
  await backend.move('forward',.65);
  await report('A5_ALIAS_MOTOR_PAD_SELECTED',{
    side:goLeft?'left':'right',initial_left_m:savedClue,
    decision_source:'retained_early_sensor',testOnly:true
  });
  await backend.land();
  await report('A5_ALIAS_MOTOR_LAND_ACK',{nativeReply:true});
  await report('A5_ALIAS_MOTOR_TEST_COMPLETE',{testOnly:true,
    pupilWbb:false,missionOracle:false});
 }catch(e){
  await report('A5_ALIAS_MOTOR_ERROR',{reason:String(e&&(e.stack||e.message)||e)});
 }
})();
