'use strict';
// Diagnostic transport only: ordinary production WWI backend/interpreter.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '../..');
const Backend = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));
const Interpreter = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/interpreter.js'));
const [port, mode, directory] = process.argv.slice(2);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function report(event, detail) {
  fs.appendFileSync(path.join(directory, 'events.jsonl'), JSON.stringify({event, detail, wall_ms: Date.now()}) + '\n');
}
const socket = new WebSocket('ws://127.0.0.1:' + Number(port) + '/');
const backend = new Backend({send: message => {
  report('request', message);
  socket.send('robot:Crazyflie WebeeBlocks:' + message);
}}, {simulationReset: true});
socket.onmessage = event => {
  for (const line of String(event.data).split(/\r?\n/)) {
    if (!line.startsWith('robot:')) continue;
    const data = JSON.parse(line.slice(6));
    if (data.name === 'Crazyflie WebeeBlocks') {
      report('response', data.message);
      backend.handleMessage(data.message);
    }
  }
};

async function baseline() {
  // Load the exact existing program builders and oracle helpers, without
  // invoking their browser startup. No copied/retuned student strategy.
  const source = fs.readFileSync(path.join(root, 'plugins/robot_windows/autonomous_probe/autonomous_probe.js'), 'utf8');
  const start = source.indexOf('async function waitForOutcome(');
  const end = source.indexOf("window.addEventListener('error'");
  if (start < 0 || end <= start) throw new Error('historical probe boundary unavailable');
  const context = vm.createContext({backend, WebeeBlocksInterpreter: Interpreter, sleep, report, Date, Number, Error});
  vm.runInContext(source.slice(start, end), context);
  await vm.runInContext(`(async () => {
    const evaluation = {type:'mission-state-v1', oracle:'progression-autonomous-strategy-v1'};
    await proveFailureProbeUnavailableWithoutFailure(backend, evaluation);
    for (let index = 0; index < 4; index++) {
      await executeCase(backend, evaluation, integratedStrategy(), 'achieved', 'integrated-'+index, false);
      await resetAndProveFresh(backend, evaluation, 'integrated-reset-'+index);
    }
    await executeCase(backend, evaluation, fixedRouteShortcut(), 'not-achieved', 'fixed-negative', true);
    await resetAndProveFresh(backend, evaluation, 'fixed-reset');
    await executeCase(backend, evaluation, noMemoryShortcut(), 'not-achieved', 'memory-negative', false);
    await resetAndProveFresh(backend, evaluation, 'memory-reset');
    await executeCase(backend, evaluation, frontOnlyShortcut(), 'not-achieved', 'front-negative', true);
    await resetAndProveFresh(backend, evaluation, 'front-reset');
  })()`, context);
}

async function sweep() {
  const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'cases.json'), 'utf8'));
  let id = 0;
  for (const initial of cases.states) for (const steps of cases.observation_steps) {
    const input = {id: ++id, ...initial, steps};
    fs.writeFileSync(path.join(directory, 'inject.tmp'), JSON.stringify(input));
    fs.renameSync(path.join(directory, 'inject.tmp'), path.join(directory, 'inject.json'));
    const until = Date.now() + 10000;
    let ready;
    while (Date.now() < until) {
      try { ready = JSON.parse(fs.readFileSync(path.join(directory, 'ready.json'), 'utf8')); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      if (ready && ready.id === id) break;
      await sleep(5);
    }
    if (!ready || ready.id !== id) throw new Error('injection not observed: ' + id);
    report('CASE', {input, ready});
    try {
      await backend.resetSimulation();
      report('RESET_OK', {id});
    } catch (error) {
      report('RESET_FAILED', {id, code: error.code});
      throw error; // Preserve first refusal, never retry the failed RESET.
    }
  }
}

socket.onopen = async () => {
  try {
    socket.send('robot:Crazyflie WebeeBlocks:init robot window');
    await backend.waitUntilReady();
    if (mode === 'baseline') await baseline();
    else if (mode === 'sweep') await sweep();
    else throw new Error('unknown diagnostic mode');
    report('COMPLETE', {mode, claim: 'diagnostic-only-not-main-health-or-full-progression'});
  } catch (error) {
    report('ERROR', {code: error.code || null, message: String(error)});
    process.exitCode = 1;
  } finally {
    socket.close();
    setTimeout(() => process.exit(process.exitCode || 0), 30);
  }
};
socket.onerror = error => { report('TRANSPORT_ERROR', String(error)); process.exit(2); };
setTimeout(() => { report('WALL_TIMEOUT', {}); process.exit(3); }, 330000).unref();
