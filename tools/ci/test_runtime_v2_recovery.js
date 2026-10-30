'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Backend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const Recovery = require('../../plugins/robot_windows/blockly_v2/simulation_recovery.js');

module.exports = async function testWorldRecovery() {
  const p = 'WEBEEBLOCKS_RUNTIME_V2 ';
  const sent = [];
  const backend = new Backend({send: m => sent.push(m)}, {
    timeoutMs: 1000, simulationReset: true, simulationScenes: true, simulationWorldReload: true
  });
  backend.handleMessage(p + 'READY');
  let rejected = backend.move('forward', 0.2).then(() => assert.fail('old command succeeded'), e => e);
  let reset = backend.resetSimulation(true);
  assert.strictEqual((await rejected).code, 'RESET_CANCELLED');
  let m = sent[1].match(/ REQUEST (\d+) RESET ([0-9a-f]{64})$/);
  assert(m, 'Recovery RESET must use fresh 256-bit correlation');
  backend.handleMessage(p + 'RESPONSE ' + m[1] + ' OK');
  assert.strictEqual(backend.ready, false, 'stale numeric ACK unlocked recovery');
  backend.handleMessage(p + 'RESPONSE ' + m[1] + ' RESET_OK ' + '0'.repeat(64));
  assert.strictEqual(backend.ready, false, 'wrong generation unlocked recovery');
  backend.handleMessage(p + 'RESPONSE ' + m[1] + ' RESET_OK ' + m[2]);
  await reset;
  assert.strictEqual(backend.ready, true);
  const scene = backend.prepareActivity({runtime:{scene:'sequence-v1'}});
  m = sent[2].match(/ REQUEST (\d+) SCENE sequence-v1 ([0-9a-f]{64})$/);
  assert(m);
  backend.handleMessage(p + 'RESPONSE ' + m[1] + ' OK');
  backend.handleMessage(p + 'RESPONSE ' + m[1] + ' SCENE_OK ' + m[2]);
  await scene;
  const subsequent = backend.resetSimulation(true);
  m = sent[3].match(/ REQUEST (\d+) RESET ([0-9a-f]{64})$/);
  assert(m);
  backend.handleMessage(p + 'RESPONSE ' + m[1] + ' RESET_OK ' + m[2]);
  await subsequent;
  assert.strictEqual(backend.sceneIdentity, null);
  const again = backend.prepareActivity({runtime:{scene:'sequence-v1'}});
  m = sent[4].match(/ REQUEST (\d+) SCENE sequence-v1 ([0-9a-f]{64})$/);
  assert(m);
  backend.handleMessage(p + 'RESPONSE ' + m[1] + ' SCENE_OK ' + m[2]);
  await again;
  backend.requestWorldReload('a'.repeat(64));
  const fresh = new Backend({send:m => sent.push(m)}, {simulationReset:true,timeoutMs:1000});
  fresh.nextId = backend.nextId;
  fresh.handleMessage(p + 'READY');
  const newRequest = fresh.resetSimulation(true);
  const newId = sent[sent.length-1].match(/ REQUEST (\d+) RESET ([0-9a-f]{64})$/);
  assert(newId && Number(newId[1]) >= backend.nextId);
  fresh.handleMessage(p + 'RESPONSE 1 OK');
  assert.strictEqual(fresh.ready, false, 'old numeric ACK unlocked new RESET');
  fresh.handleMessage(p + 'RESPONSE ' + newId[1] + ' RESET_OK ' + newId[2]);
  await newRequest;
  assert.strictEqual(sent[5], p + 'RELOAD_WORLD ' + 'a'.repeat(64));
  assert.strictEqual(backend.ready, false);
  assert.strictEqual(backend.simulationStopped, true);
  const status = fresh.readRecoveryStatus();
  const statusMessage = sent[sent.length-1];
  const statusMatch = statusMessage.match(/ REQUEST (\d+) RECOVERY_STATUS ([0-9a-f]{64})$/);
  assert(statusMatch);
  fresh.handleMessage(p + 'RESPONSE ' + statusMatch[1] + ' RECOVERY_STATUS ' + '0'.repeat(64) + ' NONE');
  assert(Object.keys(fresh.pending).length === 1, 'old status ACK was accepted');
  fresh.handleMessage(p + 'RESPONSE ' + statusMatch[1] + ' RECOVERY_STATUS ' + statusMatch[2] + ' PENDING ' + 'a'.repeat(64));
  assert.deepStrictEqual(await status, {state:'PENDING',token:'a'.repeat(64)});
  const clear = fresh.clearRecoveryWitness('a'.repeat(64));
  const clearMatch = sent[sent.length-1].match(/ REQUEST (\d+) RECOVERY_CLEAR ([0-9a-f]{64}) ([0-9a-f]{64})$/);
  assert(clearMatch);
  fresh.handleMessage(p + 'RESPONSE ' + clearMatch[1] + ' RECOVERY_CLEARED ' + '0'.repeat(64));
  assert(Object.keys(fresh.pending).length === 1, 'old clear ACK accepted');
  fresh.handleMessage(p + 'RESPONSE ' + clearMatch[1] + ' RECOVERY_CLEARED ' + clearMatch[3]);
  await clear;
  const noReload = new Backend({send(){}},{simulationReset:true});
  assert.throws(() => noReload.requestWorldReload(), /unavailable/);
  const beforeResetSource = fs.readFileSync(path.join(__dirname,'../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'),'utf8');
  assert.match(beforeResetSource, /wb_supervisor_world_reload\(\);/);
  assert.match(beforeResetSource, /if \(world_reload_requested\)\s*continue;/);
  assert.match(beforeResetSource, /RESET_OK %s/);
  assert.match(beforeResetSource, /#define RESET_TIMEOUT 5\.0/);
  assert.match(beforeResetSource, /#define RESET_WINDOW 0\.25/);
  const uiSource = fs.readFileSync(path.join(__dirname,'../../plugins/robot_windows/blockly_v2/main.js'),'utf8');
  assert.match(uiSource, /WebeeBlocksSimulationRecovery\.save\(runtimeProfile\.id, serializedWorkspace\(\), runtimeBackend\.nextId\)/);
  assert.match(uiSource, /await runtimeBackend\.resetSimulation\(true\);[\s\S]*await runtimeBackend\.prepareActivity\(runtimeProfile\);[\s\S]*await runtimeBackend\.resetSimulation\(true\);/);
  assert.match(uiSource, /WebeeBlocksSimulationRecovery\.clear\(recovery\);[\s\S]*runtimeTerminal = false;/);

  // Simulated localStorage survives loss of controller and browser JS realm.
  const saved = new Map();
  global.localStorage = {
    getItem: key => saved.has(key) ? saved.get(key) : null,
    setItem: (key, value) => saved.set(key, value),
    removeItem: key => saved.delete(key)
  };
  try {
    const workspace = JSON.stringify({blocks:{blocks:[{type:'math_number',id:'unsaved'}]}});
    const checkpoint = Recovery.save('progression-sequence-v1', workspace, 41);
    assert.strictEqual(Recovery.peek().nextRequestId, 41);
    assert.deepStrictEqual(Recovery.peek(), checkpoint);
    const damaged = JSON.parse(saved.values().next().value);
    damaged.workspace = '{';
    saved.set(saved.keys().next().value, JSON.stringify(damaged));
    assert.throws(() => Recovery.peek());
    saved.clear();
    Recovery.save('progression-sequence-v1', workspace, 41);
    assert.throws(() => Recovery.clear({...checkpoint, workspace:'{}'}), /changed/);
    assert(Recovery.peek(), 'bad token erased pupil blocks');
    Recovery.clear(checkpoint);
    assert.strictEqual(Recovery.peek(), null);
    global.localStorage = {
      getItem: key => saved.get(key) || null,
      setItem() { throw new Error('quota'); },
      removeItem: key => saved.delete(key)
    };
    assert.throws(() => Recovery.save('progression-sequence-v1', workspace, 41), /quota/);
    assert.strictEqual(Recovery.peek(), null);
  } finally { delete global.localStorage; }
  console.log('PASS: recovery RESET correlation, scene revalidation, reload fail-closed, durable Blockly checkpoint');
};
