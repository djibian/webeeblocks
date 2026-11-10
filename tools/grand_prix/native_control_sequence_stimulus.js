'use strict';
// Unmodified normal WWI backend; no physical sender and no oracle shortcuts.
// An unexpected native refusal is retained as a failed/partial experiment.
const fs = require('fs');
const path = require('path');
const Backend = require(path.resolve(__dirname, '../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));
const port = Number(process.argv[2]), scenario = process.argv[3], output = process.argv[4];
if (!Number.isInteger(port) || port < 1024 || port > 65535 ||
    !['primitives', 'ceiling', 'ceiling_safe_ascent', 'ceiling_takeoff', 'route_lh', 'stop', 'deadline', 'reset'].includes(scenario) || !output)
  throw new Error('Native R2025a sequence requires a valid port, scenario and event path');

let settled = false;
function log(kind, value) {
  const data = {kind, scenario, value};
  fs.appendFileSync(output, JSON.stringify(data) + '\n');
  console.log('GP_SEQUENCE_EVENT ' + JSON.stringify(data));
}
const socket = new WebSocket('ws://127.0.0.1:' + port + '/');
const backend = new Backend({send: request => {
  if (socket.readyState !== WebSocket.OPEN) throw new Error('native WWI socket closed');
  log('request', request);
  socket.send('robot:Crazyflie WebeeBlocks:' + request);
}}, {simulationAdmission:true, simulationReset:true, simulationStop:true, timeoutMs:300000});
socket.onmessage = event => {
  for (const line of String(event.data).split(/\r?\n/)) {
    if (!line.startsWith('robot:')) continue;
    let message;
    try { message = JSON.parse(line.slice(6)); }
    catch (_) { log('malformed', line); continue; }
    if (message.name !== 'Crazyflie WebeeBlocks') continue;
    if (typeof message.message !== 'string') continue;
    log('response', message.message);
    backend.handleMessage(message.message);
  }
};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function step(name, action) {
  log('step-begin', name);
  try {
    const value = await action();
    log('step-ok', {name, result:value === undefined ? null : value});
    return value;
  } catch (error) {
    log('step-refused', {name, message:String(error), code:error && error.code || null});
    throw error;
  }
}
async function casePrimitives() {
  // Stay inside the already-authorized 0.14 m initial takeoff zone; its
  // 15-second privilege is never prolonged/recreated by a return flight.
  // This is a controlled PRIMITIVE TRANSITION witness, not a mission shortcut.
  await step('takeoff-0.5', () => backend.takeoff(.5));
  await step('wait-0.1', () => backend.wait(.1));
  await step('move-forward-0.04', () => backend.move('forward', .04));
  await step('vertical-up-0.10', () => backend.vertical('up', .10));
  await step('turn-5', () => backend.turn(5));
  await step('vertical-down-0.10', () => backend.vertical('down', .10));
  await step('land-within-takeoff-exception', () => backend.land());
  await step('strict-reset-after-land', () => backend.resetSimulation());
  await step('takeoff-after-reset-0.5', () => backend.takeoff(.5));
  await step('stop-after-reset-takeoff', () => backend.stopSimulation());
}
async function caseCeiling() {
  await step('takeoff-1.0', () => backend.takeoff(1.0));
  try {
    await step('vertical-near-ceiling-up-0.1', () => backend.vertical('up', .1));
    log('unexpected-vertical-acceptance', 'ceiling preflight did not refuse');
    throw new Error('insufficient-headroom ascent was accepted');
  } catch (error) {
    if (error && error.code === 'VERTICAL_LIMIT') {
      log('preventive-ceiling-refusal', error.code);
      await step('stop-after-preventive-refusal', () => backend.stopSimulation());
      await sleep(10000);
      log('ceiling-post-stop-landing-window', {wall_ms:10000});
      return;
    }
    // TIME_LIMIT means the oracle observed physical ceiling breach.
    throw error;
  }
}
async function caseSafeAscent() {
  await step('takeoff-0.8', () => backend.takeoff(.8));
  await step('vertical-safe-up-0.10', () => backend.vertical('up', .10));
  await step('stop-after-safe-ascent', () => backend.stopSimulation());
  await sleep(10000);
  log('safe-ascent-land-window', {wall_ms:10000});
}
async function caseTakeoffCeiling() {
  let denied = false;
  try { await step('takeoff-1.1-must-refuse', () => backend.takeoff(1.1)); }
  catch (e) {
    if (e && e.code === 'INVALID_TAKEOFF') {
      log('preventive-takeoff-refusal', e.code); denied = true;
    } else throw e;
  }
  if (!denied) throw Error('unsafe TAKEOFF was accepted');
  await step('takeoff-1.0-after-refusal', () => backend.takeoff(1.0));
  await step('stop-after-valid-takeoff', () => backend.stopSimulation());
  await sleep(10000);
  log('takeoff-preflight-land-window', {wall_ms:10000});
}
// DIAGNOSTIC ONLY: one specific reference course with real native L corners,
// TWO real open H gates (leg 0 at 1.0 m, leg 2 at 0.85 m), terminal H/collision,
// native route oracle and normal WWI; never an AST or classroom certification.
// Course gp-route-v2-L2000-2500-3000-TGD-s105-H2, fixed native-world hash.
async function caseRouteLH() {
  const evalProfile = {type:'mission-state-v1', oracle:'grand-prix-route-v2'};
  await step('route-takeoff-0.8', () => backend.takeoff(.8));
  await step('leg0-approach-h', () => backend.move('forward', .68));
  await step('leg0-descend-for-h', () => backend.vertical('down', .30));
  await step('leg0-cross-open-h', () => backend.move('forward', .72));
  await step('leg0-climb-after-h', () => backend.vertical('up', .30));
  await step('leg0-to-l-corner', () => backend.move('forward', .58));
  await step('corner0-left-90', () => backend.turn(90));
  await step('leg1-forward-1.9', () => backend.move('forward', 1.9));
  await step('leg1-forward-0.58', () => backend.move('forward', .58));
  await step('corner1-right-90', () => backend.turn(-90));
  await step('leg2-approach-h', () => backend.move('forward', .55));
  await step('leg2-descend-for-h', () => backend.vertical('down', .30));
  await step('leg2-cross-open-h', () => backend.move('forward', .72));
  await step('leg2-climb-after-h', () => backend.vertical('up', .30));
  await step('leg2-approach-landing', () => backend.move('forward', 1.03));
  await step('terminal-left-offset-0.50', () => backend.move('left', .50));
  await step('terminal-low-landing-zone', () => backend.vertical('down', .30));
  // The normal interpreter requests COMPLETE only AFTER LAND returns OK.
  // Publishing completion while still descending starts the immutable
  // terminal 1.5 s oracle window too soon (run 42874656881, wrong-landing).
  await step('route-land', () => backend.land());
  await step('oracle-complete', () => backend.completeActivityMission(evalProfile));
  const outcome = await step('route-outcome', () => backend.readActivityOutcome(evalProfile));
  log('route-native-outcome', outcome);
  if (!outcome || outcome.status !== 'achieved')
    throw Error('route evaluator did not publish achieved after native LAND');
}
async function caseStop() {
  await step('takeoff-0.8', () => backend.takeoff(.8));
  let moveSettled = false;
  const movePromise = backend.move('forward', .5).then(
    () => { moveSettled=true; log('move-finished-before-stop',true); },
    error => { moveSettled=true; log('move-interrupted-by-stop', String(error)); });
  await sleep(120);
  await step('stop-during-or-after-move', () => backend.stopSimulation());
  await Promise.race([movePromise, sleep(1500)]);
  log('stop-move-settled', moveSettled);
  // STOP only acknowledges cancellation, not physical touchdown. Keep the
  // native world alive so the *independent* LAND reaches ground confirmation.
  await sleep(10000);
  log('stop-native-land-observation-window', {wall_ms:10000});
}
async function caseReset() {
  // Initial confirmed-ground RESET must complete and establish a NEW
  // native evaluator epoch before a normal admitted takeoff.
  await step('strict-reset-from-ground', () => backend.resetSimulation());
  await step('takeoff-after-ground-reset-0.8', () => backend.takeoff(.8));
  let refusal = null;
  try {
    await step('airborne-reset-must-refuse', () => backend.resetSimulation());
  } catch (error) {
    if (error && error.code === 'LANDING_UNCONFIRMED')
      refusal = error.code;
    else throw error;
  }
  if (refusal !== 'LANDING_UNCONFIRMED')
    throw Error('airborne RESET unexpectedly accepted');
  log('strict-airborne-reset-refused', refusal);
  // Do not fake a confirmed landing in order to reset a flying vehicle.
}
async function caseDeadline() {
  await step('takeoff-0.8', () => backend.takeoff(.8));
  let elapsed = await backend.readElapsedTime();
  log('deadline-start-elapsed', elapsed);
  const until = Date.now() + 570000;
  let deadlineRefused = false;
  let count=0;
  while (Date.now()<until && elapsed < 214) {
    await sleep(200);
    try { elapsed = await backend.readElapsedTime(); }
    catch(e) {
      log('elapsed-refused-after-deadline', {message:String(e), code:e.code||null});
      if (e.code !== 'TIME_LIMIT' || elapsed < 209)
        throw e;
      deadlineRefused = true;
      break;
    }
    if (++count % 40 === 0) log('deadline-progress-elapsed', elapsed);
  }
  log('deadline-final-elapsed', elapsed);
  if (elapsed < 210 && !deadlineRefused)
    throw Error('independent 210s simulated deadline was not reached');
  if (deadlineRefused) {
    // Give the independent watchdog a native descent/touchdown opportunity.
    // The runner MUST separately verify GP_U_DEADLINE and LAND_TOUCHDOWN.
    await sleep(8000);
  }
  log('deadline-observation-completed', {elapsed, deadlineRefused});
  // Deliberately NO explicit LAND: the independent native watchdog must own it.
}
socket.onopen = async () => {
  try {
    socket.send('robot:Crazyflie WebeeBlocks:init robot window');
    await backend.waitUntilReady();
    log('runtime-ready', scenario);
    if (scenario === 'primitives') await casePrimitives();
    else if (scenario === 'ceiling') await caseCeiling();
    else if (scenario === 'ceiling_safe_ascent') await caseSafeAscent();
    else if (scenario === 'ceiling_takeoff') await caseTakeoffCeiling();
    else if (scenario === 'route_lh') await caseRouteLH();
    else if (scenario === 'stop') await caseStop();
    else if (scenario === 'reset') await caseReset();
    else await caseDeadline();
    log('scenario-finished', scenario);
    settled=true;
  } catch(error) {
    log('scenario-refused-or-incomplete', {message:String(error), code:error && error.code||null});
    process.exitCode=2;
  } finally {
    socket.close();
    setTimeout(() => process.exit(process.exitCode || (settled ? 0 : 2)), 120);
  }
};
socket.onerror = error => {
  log('socket-error', String(error));
  process.exitCode=2;
};
setTimeout(() => {
  if (!settled) {
    log('wall-timeout', scenario);
    process.exit(3);
  }
}, 600000).unref();
