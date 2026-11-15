'use strict';
/* SCHOOL CI EXPERIMENT ONLY: variant-blind motor/sensor pilot.
 * No Blockly project, scene identifier, GPS, supervisor, or AST.
 * Same code can be executed against 1/2/3 H through external world loading.
 * Motor MOVE is blocking; RANGE is sampled AFTER each short motor step.
 * Never expose this file as an activity/pupil solution.
 */
export async function runSensorOnly(backend,report) {
  await backend.setSpeed(0.20);
  await backend.takeoff(0.40);
  await report('A6_TAKEOFF',{height_m:0.40,sensorPilot:true});
  let count=0,underH=false;
  let front=await backend.readRange('front');
  let steps=0;
  for(;steps<80;steps++) {
    if(!Number.isFinite(front)||front<0||front>2.001)
      throw new Error('native front sensor unavailable');
    if(front<=0.82)break;
    await backend.move('forward',0.08);
    const up=await backend.readRange('up');
    front=await backend.readRange('front');
    if(!Number.isFinite(up)||up<0||up>2.001)
      throw new Error('native upper sensor unavailable');
    if(up<0.75) {
      const confirmed=await backend.readRange('up');
      if(!Number.isFinite(confirmed)||confirmed<0||confirmed>2.001)
        throw new Error('upper sensor confirmation unavailable');
      if(confirmed<0.75)underH=true;
    } else if(up>1.30&&underH) {
      count+=1;
      underH=false;
      if(count>3)throw new Error('too many H events');
    }
  }
  if(front>0.82||underH||count<1||count>3)
    throw new Error('no bounded scene-blind H count before terminal');
  await report('A6_SENSOR_COUNT',{count,steps,front_m:front,
    sceneBlind:true,testOnly:true});
  const finalApproach=front-0.36;
  if(!Number.isFinite(finalApproach)||finalApproach<0.10||finalApproach>0.70)
    throw new Error('terminal approach outside bounded sensor geometry');
  await backend.move('forward',finalApproach);
  await report('A6_CORRIDOR_DONE',{sensorOnly:true,steps,
    finalApproach_m:finalApproach});
  if(count===2)await backend.move('left',0.55);
  else if(count===3)await backend.move('right',0.55);
  await report('A6_PAD_SELECTED',{count,sensorOnly:true});
  await backend.land();
  await report('A6_LANDED',{nativeReply:true,sensorOnly:true});
  await backend.completeActivityMission({type:'mission-state-v1',oracle:'progression-count-h-v1'});
  await report('A6_NATIVE_COMPLETION_ACK',{nativeReply:true,testOnly:true});
  await report('A6_TEST_COMPLETE',{testOnly:true,sensorOnly:true,
    pupilWbbUnproven:true});
}
