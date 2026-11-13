'use strict';
// CI-only raw native protocol witness: NOT the student's Blockly backend.
// The browser-facing altitude-v1 allowlist is a separate candidate (#989).
const PREFIX = 'WEBEEBLOCKS_RUNTIME_V2';
let reports = Promise.resolve();
function report(event, detail) {
  reports = reports.then(() => fetch('http://127.0.0.1:8765/event', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event, detail:detail || null, wall_ms:Date.now()})
  }).then(response => {
    if (!response.ok) throw new Error('CI observer refused event ' + event);
  }));
  return reports;
}
function nonce() {
  const bytes = new Uint8Array(32);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
}
window.addEventListener('error', event => {
  report('WINDOW_ERROR', {message:String(event.message)});
});
window.addEventListener('unhandledrejection', event => {
  report('WINDOW_ERROR', {message:String(event.reason)});
});
(async function() {
  try {
    await report('CLASSROOM_PROBE_JS_STARTED', {page:'altitude_scene_ack_probe'});
    const module = await import('../blockly_v2/webots/RobotWindow.js');
    const windowBridge = new module.default();
    await report('CLASSROOM_BRIDGE_CONSTRUCTED', {nativeBridge:true});
    const backend = new WebeeBlocksWwiBackend({send:m => windowBridge.send(m)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000});
    const pending = new Map();
    windowBridge.receive = function(value) {
      const message = String(value);
      backend.handleMessage(message);
      const found = /^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (.+)$/.exec(message);
      if (!found) return;
      const id = Number(found[1]);
      const waiter = pending.get(id);
      if (!waiter) return;
      pending.delete(id);
      clearTimeout(waiter.timer);
      if (found[2] === waiter.expected) waiter.resolve(message);
      else waiter.reject(new Error('wrong native response for id ' + id +
                                   ': expected ' + waiter.expected + ' got ' + found[2]));
    };
    await backend.waitUntilReady();
    await report('CLASSROOM_RUNTIME_READY', {ready:true});
    let nextId = 1;
    function request(parts, expected) {
      const id = nextId++;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new Error('native request timeout id=' + id + ' command=' + parts));
        }, 60000);
        pending.set(id, {expected,resolve,reject,timer});
        windowBridge.send(PREFIX + ' REQUEST ' + id + ' ' + parts);
      });
    }
    // Nothing can fly before an admissible native scene selection.
    await request('TAKEOFF 0.45', 'ERR SCENE_UNAVAILABLE');
    await report('TAKEOFF_BEFORE_SCENE_REFUSED', {code:'SCENE_UNAVAILABLE'});
    const unknownNonce = nonce();
    await request('SCENE unknown-v1 ' + unknownNonce, 'ERR SCENE_UNAVAILABLE');
    await report('UNKNOWN_SCENE_REFUSED', {code:'SCENE_UNAVAILABLE'});
    // SCENE_OK is accepted only when it echoes the actual random nonce.
    const altitudeNonce = nonce();
    await request('SCENE altitude-v1 ' + altitudeNonce, 'SCENE_OK ' + altitudeNonce);
    await report('ALTITUDE_SCENE_ACK', {scene:'altitude-v1', nonce_correlated:true});
    const legacyNonce = nonce();
    await request('SCENE legacy-v1 ' + legacyNonce, 'SCENE_OK ' + legacyNonce);
    await report('LEGACY_SCENE_RESTORED', {scene:'legacy-v1', nonce_correlated:true});
    const againNonce = nonce();
    await request('SCENE altitude-v1 ' + againNonce, 'SCENE_OK ' + againNonce);
    await report('ALTITUDE_SCENE_REATTACHED', {scene:'altitude-v1', nonce_correlated:true});
    await report('NATIVE_SCENE_ACK_TEST_COMPLETE', {selected:2, legacy:1, negative:2});
  } catch (error) {
    await report('WINDOW_ERROR', {message:error && error.message ? error.message : String(error)});
  }
})();
