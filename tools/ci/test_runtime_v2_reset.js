'use strict';
const assert = require('assert');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');

(async () => {
  const sent = [];
  const backend = new WwiBackend({send: message => sent.push(String(message))}, {
    timeoutMs: 1000,
    simulationDebug: true,
    simulationReset: true
  });

  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY');
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(backend.capabilities.simulationReset, true);

  const oldRequest = backend.move('forward', 0.2).then(
    () => { throw new Error('old request unexpectedly resolved'); },
    error => error
  );
  assert.match(sent[0], / REQUEST 1 MOVE forward /);
  assert.strictEqual(Object.keys(backend.pending).length, 1);

  const reset = backend.resetSimulation();
  const cancelled = await oldRequest;
  assert.strictEqual(cancelled.code, 'RESET_CANCELLED');
  assert.strictEqual(backend.ready, false);
  assert.strictEqual(Object.keys(backend.pending).length, 1);
  assert.match(sent[1], / REQUEST 2 RESET$/);

  // A response from the pre-reset generation must be harmless.
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK');
  assert.strictEqual(Object.keys(backend.pending).length, 1);
  assert.strictEqual(backend.ready, false);

  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK');
  await reset;
  assert.strictEqual(backend.ready, true);
  assert.strictEqual(Object.keys(backend.pending).length, 0);

  const physical = new WwiBackend({send: () => {}}, {timeoutMs: 1000});
  assert.notStrictEqual(physical.capabilities.simulationReset, true);
  await assert.rejects(() => physical.resetSimulation(), /simulation reset unavailable/);

  console.log('PASS: simulation reset is explicit, cancels pending requests, ignores stale replies, and is unavailable without the simulation capability.');
})().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
