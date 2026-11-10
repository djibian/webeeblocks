'use strict';
// Unmodified normal WWI backend; no physical sender and no oracle shortcuts.
// An unexpected native refusal is retained as a failed/partial experiment.
const fs = require('fs');
const path = require('path');
const Backend = require(path.resolve(__dirname, '../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));
const port = Number(process.argv[2]), scenario = process.argv[3], output = process.argv[4];
if (!Number.isInteger(port) || port < 1024 || port > 65535 ||
    !['primitives', 'ceiling', 'stop', 'deadline', 'reset'].includes(scenario) || !output)
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
  await step('takeoff-0.8', () => backend.takeoff(.8));
  await step('wait-0.5', () => backend.wait(.5));
  await step('move-forward-0.12', () => backend.move('forward', .12));
  await step('vertical-up-0.10', () => backend.vertical('up', .10));
  await step('turn-15', () => backend.turn(15));
  await step('vertical-down-0.10', () => backend.vertical('down', .10));
  await step('wait-0.5-after', () => backend.wait(.5));
  // Non-terminal position is not the Grand Prix mission landing zone.
  // A mission failure is recorded, never recast as a course success.
  await step('land-away-from-goal', () => backend.land());
  await step('strict-reset', () => backend.resetSimulation());
  await step('takeoff-after-reset-0.5', () => backend.takeoff(.5));
  await step('stop-after-reset-takeoff', () => backend.stopSimulation());
}
async function caseCeiling() {
  await step('takeoff-1.0', () => backend.takeoff(1.0));
  await step('vertical-near-ceiling-up-0.1', () => backend.vertical('up', .1));
  try {
    await step('vertical-exceed-ceiling-up-0.1', () => backend.vertical('up', .1));
    log('unexpected-ceiling-acceptance', 'required ceiling refusal was absent');
    throw new Error('native ceiling guard failed to refuse');
  } catch (e) {
    if (String(e).includes('native ceiling guard failed')) throw e;
    log('ceiling-refusal-observed', {message:String(e), code:e.code||null});
  }
  await step('stop-after-ceiling-refusal', () => backend.stopSimulation());
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
}
async function caseReset() {
  await step('takeoff-0.8', () => backend.takeoff(.8));
  await step('strict-reset-from-airborne-idle', () => backend.resetSimulation());
  await step('takeoff-after-reset-0.5', () => backend.takeoff(.5));
  await step('stop-after-reset', () => backend.stopSimulation());
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
