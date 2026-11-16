'use strict';
// Diagnostic only. One native R2025a World/Robot Window, no pupil profile.
// A negative, a RESET ACK, a motorized success, another RESET and another
// motorized success must all be observed without restarting Webots.
export async function runReplay(backend,report,variant) {
  if(variant!==1)throw new Error('bounded A6 same-world replay tests n=1 only');
  const evaluation={type:'mission-state-v1',oracle:'progression-count-h-v1'};
  await backend.completeActivityMission(evaluation);
  const negative=await backend.readActivityOutcome(evaluation);
  if(!negative||negative.status!=='not-achieved')
    throw new Error('early COMPLETE before flying did not fail native C oracle');
  await report('A6_REPLAY_FIRST_NEGATIVE',{nativeStatus:negative.status,attempt:1});
  async function staleMustFail(epoch) {
    try {
      const outcome=await backend.readActivityOutcome(evaluation);
      throw new Error('stale result unexpectedly readable after RESET: '+JSON.stringify(outcome));
    } catch(e) {
      if(!e||!(e.code==='OUTCOME_UNAVAILABLE'||e.code==='STALE_OUTCOME'))
        throw e;
    }
    await report('A6_REPLAY_STALE_DENIED',{epoch,oldOutcomeRejected:true});
  }
  async function fly(epoch) {
    // Observable native RANGE ACK after RESET; never infer READY from pose.
    const front=await backend.readRange('front');
    if(typeof front!=='number'||!Number.isFinite(front))
      throw new Error('fresh native front range unavailable');
    await backend.setSpeed(0.20);
    await backend.takeoff(0.40);
    for(let i=0;i<6;i++)await backend.move('forward',0.48);
    await backend.move('forward',0.12);
    await backend.land();
    await backend.completeActivityMission(evaluation);
    const outcome=await backend.readActivityOutcome(evaluation);
    if(!outcome||outcome.status!=='achieved')
      throw new Error('new native epoch not achieved '+epoch);
    await report('A6_REPLAY_POSITIVE',{epoch,front_m:front,status:outcome.status});
  }
  await backend.resetSimulation();
  await report('A6_REPLAY_RESET_ACK',{epoch:2,nativeReply:true});
  await staleMustFail(2);
  await fly(2);
  await backend.resetSimulation();
  await report('A6_REPLAY_RESET_ACK',{epoch:3,nativeReply:true});
  await staleMustFail(3);
  await fly(3);
  await report('A6_REPLAY_TEST_COMPLETE',{nativeEpochs:[1,2,3],sameWorld:true});
}
