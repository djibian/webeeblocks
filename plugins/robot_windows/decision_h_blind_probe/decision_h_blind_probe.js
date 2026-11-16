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
      // The same presenter used by the classroom Blockly window translates
      // ONLY native exact-attempt A4 evidence. Check the real browser DOM.
      const evaluation={type:'mission-state-v1',oracle:'progression-decision-h-v1'};
      const display=WebeeBlocksRuntimeOutcome.classifyMission(refused,evaluation);
      const target=document.getElementById('a4-native-failure-feedback');
      assert(target&&target.getAttribute('aria-live')==='polite',
        'accessible real browser failure-feedback element missing');
      target.textContent=display.state+' — '+display.detail;
      assert(refused.reason==='unsafe-clearance' &&
        target.textContent==='MISSION NON RÉUSSIE — Mission non accomplie — Zone ou hauteur de franchissement non respectée',
        'native failure reason absent or not displayed by actual browser');
      await report('A4_BLIND_NATIVE_REFUSED',{variant,wrong,
        status:refused.status,reason:refused.reason,
        renderedDetail:target.textContent,movementError});
      if(variant==='a') {
        await backend.resetSimulation();
        await report('A4_BLIND_NATIVE_RESET',{between:'a,b'});
      }
    }
    // Third adversarial pupil error: succeed at both *physical* crossings,
    // then deliberately land on the real Floor outside the correct pad.
    // No Supervisor teleport and no synthetic/native-identity oracle bypass.
    await backend.resetSimulation();
    await report('A4_BLIND_NATIVE_RESET',{between:'b,wrong-pad'});
    await backend.prepareActivity({runtime:{scene:'decision-h-a-v1'}});
    await report('A4_BLIND_SCENE_READY',{variant:'a',case:'wrong-pad'});
    await backend.setSpeed(0.1);
    await backend.takeoff(0.50);
    await backend.vertical('up',0.25);
    await backend.move('forward',0.20);
    await backend.vertical('down',0.35);  // Genuine low H clearance in A.
    await backend.move('forward',0.75);
    await backend.vertical('up',0.25);
    await backend.vertical('up',0.20);    // Genuine curb clearance in A.
    await backend.move('forward',0.80);
    await backend.move('left',0.35);     // x>1.60, off the target pad.
    await report('A4_BLIND_WRONG_PAD_STARTED',{variant:'a',offsetY_m:0.35});
    await backend.land();
    await backend.completeActivityMission({
      type:'mission-state-v1',oracle:'progression-decision-h-v1'});
    const padResult=await outcome(backend);
    const padDisplay=WebeeBlocksRuntimeOutcome.classifyMission(padResult,{
      type:'mission-state-v1',oracle:'progression-decision-h-v1'});
    const padTarget=document.getElementById('a4-native-failure-feedback');
    assert(padTarget && padTarget.getAttribute('aria-live')==='polite',
      'missing real DOM target for wrong pad');
    padTarget.textContent=padDisplay.state+' — '+padDisplay.detail;
    assert(padResult.reason==='wrong-pad' &&
      padTarget.textContent==='MISSION NON RÉUSSIE — Mission non accomplie — Atterrissage hors de la zone prévue',
      'native wrong-pad cause or browser rendering missing');
    await report('A4_BLIND_WRONG_PAD_REFUSED',{variant:'a',reason:padResult.reason,
      status:padResult.status,renderedDetail:padTarget.textContent});
    // Fourth adversarial case: strike the INNER left H upright at legal
    // low-H altitude, before the corridor y-boundary. Never weaken the
    // oracle's pre-collision unsafe-clearance guard to obtain a contact.
    await backend.resetSimulation();
    await report('A4_BLIND_NATIVE_RESET',{between:'wrong-pad,contact'});
    await backend.prepareActivity({runtime:{scene:'decision-h-a-v1'}});
    await report('A4_BLIND_SCENE_READY',{variant:'a',case:'H_LEFT-contact'});
    await backend.setSpeed(0.1);
    await backend.takeoff(0.50);
    await backend.vertical('up',0.25);
    await backend.vertical('down',0.35); // Safe centre altitude below H bar.
    await backend.move('forward',0.75); // Real motor flight inside H passage.
    await report('A4_BLIND_CONTACT_STARTED',{variant:'a',target:'H_LEFT'});
    let contactMovementError=null;
    try{await backend.move('left',0.32);}
    catch(error){contactMovementError=String(error?.code||error?.message||error);}
    const contactResult=await outcome(backend);
    const contactDisplay=WebeeBlocksRuntimeOutcome.classifyMission(contactResult,{
      type:'mission-state-v1',oracle:'progression-decision-h-v1'});
    const contactTarget=document.getElementById('a4-native-failure-feedback');
    assert(contactTarget&&contactTarget.getAttribute('aria-live')==='polite',
      'missing accessible real DOM target for native collision');
    contactTarget.textContent=contactDisplay.state+' — '+contactDisplay.detail;
    assert(contactResult.reason==='obstacle-contact' &&
      contactTarget.textContent==='MISSION NON RÉUSSIE — Mission non accomplie — Contact avec un obstacle',
      'native H_LEFT contact cause or real browser rendering missing');
    await report('A4_BLIND_CONTACT_REFUSED',{variant:'a',target:'H_LEFT',
      status:contactResult.status,reason:contactResult.reason,
      renderedDetail:contactTarget.textContent,movementError:contactMovementError});
    await report('A4_BLIND_TEST_COMPLETE',{
      variants:['a','b','a-wrong-pad','a-H_LEFT-contact'],
      status:'four-native-not-achieved',rangeReads:0});
  } catch(error) {
    await report('A4_BLIND_ERROR',{message:String(error?.stack||error)});
  }
})();
