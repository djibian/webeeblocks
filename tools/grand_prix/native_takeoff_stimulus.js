'use strict';
/* Native Webots-only measurement stimulus.  Uses the exact normal WWI backend,
 * including pre-takeoff ADMISSION; never issues a physical-radio command.
 * No RESET, direct raw request or mission oracle override.
 */
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Backend = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));
const port = Number(process.argv[2]);
const height = Number(process.argv[3]);
const evidenceFile = process.argv[4];
if (!Number.isInteger(port) || port < 1024 || port > 65535 ||
    ![0.5, 0.8, 1.0].includes(height) || !evidenceFile)
  throw Error('Native-only three-height diagnostic requires port, height and evidence file');
let finished = false;
function record(kind, details) {
  const data = {kind, details};
  fs.appendFileSync(evidenceFile, JSON.stringify(data) + '\n');
  console.log('GP_TAKEOFF_NATIVE_STIMULUS ' + JSON.stringify(data));
}
const socket = new WebSocket('ws://127.0.0.1:' + port + '/');
const backend = new Backend({
  send: message => {
    if (socket.readyState !== WebSocket.OPEN)
      throw Error('Webots WWI connection not open');
    record('request', message);
    socket.send('robot:Crazyflie WebeeBlocks:' + message);
  }
}, {simulationReset: true, simulationStop: true, simulationAdmission: true, timeoutMs: 300000});
socket.onmessage = event => {
  for (const line of String(event.data).split(/\r?\n/)) {
    if (!line.startsWith('robot:')) continue;
    let data;
    try {data = JSON.parse(line.slice(6));}
    catch (_) {record('malformed-robot-event', line); continue;}
    if (data.name !== 'Crazyflie WebeeBlocks') continue;
    if (typeof data.message === 'string')
      record('response', data.message);
    backend.handleMessage(data.message);
  }
};
socket.onopen = async () => {
  try {
    socket.send('robot:Crazyflie WebeeBlocks:init robot window');
    await backend.waitUntilReady();
    record('runtime-ready', {height});
    await backend.takeoff(height);  // Normal ADMISSION and native TAKEOFF, no bypass
    const ackElapsed = await backend.readElapsedTime();
    record('takeoff-ack', {height, elapsed_s: ackElapsed});
    let latest = ackElapsed;
    const wallBound = Date.now() + 90000;
    while (latest < ackElapsed + 1.5 && Date.now() < wallBound) {
      await new Promise(resolve => setTimeout(resolve, 250));
      latest = await backend.readElapsedTime();
      if (!Number.isFinite(latest) || latest < ackElapsed)
        throw Error('native simulation elapsed time not monotone');
    }
    if (latest < ackElapsed + 1.5)
      throw Error('native post-takeoff stability observation window missing');
    record('observed-window', {height, from_elapsed_s: ackElapsed, to_elapsed_s: latest});
    finished = true;
  } catch (error) {
    record('native-refusal-or-error', {height, message: String(error),
      code: error && error.code || null});
    process.exitCode = 2;
  } finally {
    // Do not assert a successful mission, send LAND/STOP or bypass protection.
    // The runner terminates ONLY the isolated Webots measurement process.
    socket.close();
    setTimeout(() => process.exit(process.exitCode || (finished ? 0 : 2)), 100);
  }
};
socket.onerror = error => {
  record('socket-error', {height, message:String(error)});
  process.exitCode = 2;
};
setTimeout(() => {
  if (!finished) {
    record('measurement-wall-timeout', {height});
    process.exit(3);
  }
}, 420000).unref();
