'use strict';
// CI-only real Webots/WWI boundary test, not a student's program or a product
// Blockly profile. Deliberately NO AST-shape inspection or safety bypass.
const PROFILE = {id:'ci-altitude-canopy',runtime:{scene:'altitude-v1'}};
const ORACLE = {type:'mission-state-v1',oracle:'progression-altitude-3d-v1'};
let reportChain = Promise.resolve();
function report(event, detail) {
  reportChain = reportChain.then(() => fetch('http://127.0.0.1:8765/event', {
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail || null,wall_ms:Date.now()})
  }).then(response => {
    if (!response.ok) throw new Error('CI observer refused '+event);
  }));
  return reportChain;
}
function sleep(ms) { return new Promise(resolve => setTimeout(resolve,ms)); }
async function outcome(backend, status, ms) {
  const end = Date.now()+ms;
  while (Date.now() < end) {
    try {
      const actual = await backend.readActivityOutcome(ORACLE);
      if (actual.status !== status) throw new Error('wrong native outcome '+JSON.stringify(actual));
      return actual;
    } catch (error) {
      if (!error || error.code !== 'OUTCOME_UNAVAILABLE') throw error;
      await sleep(200);
    }
  }
  throw new Error('timed out waiting for native outcome '+status);
}
async function fresh(backend) {
  try {
    const actual = await backend.readActivityOutcome(ORACLE);
    throw new Error('RESET retained native outcome '+JSON.stringify(actual));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE') throw error;
  }
}
window.addEventListener('error', e => report('CANOPY_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection', e => report('CANOPY_ERROR',{message:String(e.reason)}));
(async () => {
  try {
    await report('CANOPY_JS_STARTED',{kind:'native-webots-boundary'});
    const module = await import('../blockly_v2/webots/RobotWindow.js');
    const bridge = new module.default();
    const backend = new WebeeBlocksWwiBackend({send:message => bridge.send(message)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000});
    bridge.receive = message => backend.handleMessage(String(message));
    await backend.waitUntilReady();
    await report('CANOPY_RUNTIME_READY',{ready:true});

    // SCENE itself must be acknowledged by the school C++ selector, not by
    // the browser. The evaluator C must then register a REAL obstacle contact.
    await backend.prepareActivity(PROFILE);
    await report('CANOPY_SCENE_ACK',{scene:'altitude-v1'});
    let highError = null;
    try { await backend.takeoff(0.80); }
    catch (error) { highError = String(error && error.code || error && error.message || error); }
    await outcome(backend,'not-achieved',80000);
    await report('CANOPY_HIGH_REJECTED',{status:'not-achieved',takeoffError:highError});

    await backend.resetSimulation();
    await fresh(backend);
    await report('CANOPY_RESET_FRESH',{code:'OUTCOME_UNAVAILABLE'});
    await backend.prepareActivity(PROFILE);
    await report('CANOPY_SCENE_REATTACHED',{scene:'altitude-v1'});

    // A deliberately simple first pilot trajectory. Its feasibility is NOT
    // presumed: CI must prove actual contact-free native flight before Ready.
    await backend.setSpeed(0.14);
    await backend.takeoff(0.45);
    await backend.move('forward',0.32);
    await report('CANOPY_CLEARED_LOW',{step:'forward',distance:0.32});
    await backend.vertical('up',0.36);
    await report('CANOPY_ASCENDED_AFTER_CLEARANCE',{step:'up',distance:0.36});
    await backend.move('forward',1.03);
    await backend.land();
    // A successful physical landing is not a mission verdict until the
    // student Runtime submits its attempt-bound completion to the C oracle.
    await backend.completeActivityMission(ORACLE);
    await outcome(backend,'achieved',80000);
    await report('CANOPY_LOW_CLIMB_ACHIEVED',{status:'achieved'});

    await report('CANOPY_TEST_COMPLETE',{high:'not-achieved',low:'achieved',reset:'fresh'});
  } catch (error) {
    await report('CANOPY_ERROR',{message:String(error && (error.stack || error.message) || error)});
  }
})();
