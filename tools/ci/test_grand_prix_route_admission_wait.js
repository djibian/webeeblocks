'use strict';
// Real backend over controlled WWI/timers. No Webots/GUI/flight PASS.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const backendSource = fs.readFileSync(
  'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js', 'utf8');

async function flush() { for (let i = 0; i < 12; ++i) await Promise.resolve(); }

function fixture(options = {}, onSend = null) {
  const tasks = new Map();
  let nextTimer = 0;
  const clock = {now: 100};
  const context = {
    module: {exports: {}}, performance: {now: () => clock.now},
    setTimeout(fn, delay) {
      const id = ++nextTimer;
      tasks.set(id, {at: clock.now + delay, fn});
      return id;
    },
    clearTimeout(id) { tasks.delete(id); }
  };
  vm.runInNewContext(backendSource, context);
  const sent = [];
  let backend;
  const transport = {send(text) {
    const match = text.match(/^WEBEEBLOCKS_RUNTIME_V2 REQUEST (\d+) (.*)$/);
    assert(match, text);
    const item = {id: Number(match[1]), command: match[2]};
    sent.push(item);
    if (onSend) onSend(item, backend);
  }};
  backend = new context.module.exports(transport, Object.assign({
    timeoutMs: 120, simulationAdmission: true,
    simulationReset: true, simulationStop: true
  }, options));
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY');
  async function advance(ms) {
    const end = clock.now + ms;
    await flush();
    while (tasks.size) {
      const entry = Array.from(tasks).sort((a, b) => a[1].at - b[1].at)[0];
      if (entry[1].at > end) break;
      tasks.delete(entry[0]);
      clock.now = entry[1].at;
      entry[1].fn();
      await flush();
    }
    clock.now = end;
    await flush();
  }
  return {backend, sent, clock, advance,
    respond(item, payload) {
      backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + item.id + ' ' + payload);
    },
    takeoffs() { return sent.filter(item => item.command.startsWith('TAKEOFF ')); }
  };
}
function response(backend, item, payload) {
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + item.id + ' ' + payload);
}
function observe(promise) {
  // Attach before advancing timers so rejections never become unhandled.
  return promise.then(() => ({ok: true}), error => ({error}));
}

async function run() {
  // Historical opt-out behavior has no extra request or scheduling boundary.
  let f = fixture({simulationAdmission: false}, (item, backend) => response(backend, item, 'OK'));
  await f.backend.takeoff(.4);
  assert.equal(f.sent.length, 1);
  assert.equal(f.takeoffs().length, 1);
  assert.equal(f.backend.capabilities.simulationAdmission, undefined);

  let polls = 0;
  f = fixture({}, (item, backend) => response(backend, item,
    item.command === 'ADMISSION' ? 'VALUE ' + (++polls >= 3 ? 1 : 0) : 'OK'));
  const completed = observe(f.backend.takeoff(.4));
  await flush();
  assert.equal(f.takeoffs().length, 0);
  await f.advance(50);
  assert.equal(f.takeoffs().length, 0);
  await f.advance(50);
  assert.equal((await completed).ok, true);
  assert.equal(f.takeoffs().length, 1);
  assert.equal(f.takeoffs()[0].command, 'TAKEOFF 0.40000000000000002');
  assert.equal(polls, 3);

  for (const payload of ['OK', 'VALUE 2', 'VALUE -1', 'STATE achieved',
    'ERR UNKNOWN_COMMAND', 'VALUE NaN']) {
    f = fixture({}, (item, backend) => response(backend, item, payload));
    assert((await observe(f.backend.takeoff(.4))).error, payload);
    assert.equal(f.takeoffs().length, 0, payload);
  }

  // A rejected physical request is never resent, even if READY was positive.
  f = fixture({}, (item, backend) => response(backend, item,
    item.command === 'ADMISSION' ? 'VALUE 1' : 'ERR INVALID_ATTEMPT'));
  assert.equal((await observe(f.backend.takeoff(.4))).error.code, 'INVALID_ATTEMPT');
  assert.equal(f.takeoffs().length, 1);

  // Missing transport response and an evaluator that never becomes ready are bounded.
  f = fixture();
  let failed = observe(f.backend.takeoff(.4));
  await f.advance(120);
  assert.match((await failed).error.message, /timeout id=1 command=ADMISSION$/);
  assert.equal(f.takeoffs().length, 0);
  assert.equal(Object.keys(f.backend.pending).length, 0);
  f = fixture({}, (item, backend) => {
    if (item.command === 'ADMISSION') response(backend, item, 'VALUE 1');
  });
  failed = observe(f.backend.takeoff(.4));
  await f.advance(120);
  assert.match((await failed).error.message, /timeout id=2 command=TAKEOFF$/);
  assert.equal(f.takeoffs().length, 1);
  assert.equal(Object.keys(f.backend.pending).length, 0);
  f = fixture({}, (item, backend) => response(backend, item, 'VALUE 0'));
  failed = observe(f.backend.takeoff(.4));
  await f.advance(200);
  assert.equal((await failed).error.code, 'ADMISSION_UNAVAILABLE');
  assert.equal(f.takeoffs().length, 0);

  // Cancellation during a request and in the positive-reply/effect gap.
  for (const mode of ['stop', 'reset', 'restart']) {
    for (const positiveFirst of [false, true]) {
      f = fixture();
      failed = observe(f.backend.takeoff(.4));
      await flush();
      const admission = f.sent[0];
      assert.equal(admission.command, 'ADMISSION');
      if (positiveFirst) f.respond(admission, 'VALUE 1');
      let operation;
      if (mode === 'stop') operation = f.backend.stopSimulation();
      if (mode === 'reset') operation = f.backend.resetSimulation();
      if (mode === 'restart') f.backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY');
      if (operation) {
        f.respond(f.sent[f.sent.length - 1], 'OK');
        await operation;
      }
      f.respond(admission, 'VALUE 1'); // late answer cannot resurrect the cancelled wait
      await f.advance(200);
      assert.equal((await failed).error.code, mode === 'stop' ? 'USER_STOPPED' : 'RESET_CANCELLED');
      assert.equal(f.takeoffs().length, 0, mode + '/' + positiveFirst);
    }
  }

  // Cancellation between polls also prevents the next observation/effect.
  f = fixture({}, (item, backend) => response(backend, item,
    item.command === 'ADMISSION' ? 'VALUE 0' : 'OK'));
  failed = observe(f.backend.takeoff(.4));
  await flush();
  await f.backend.stopSimulation();
  await f.advance(200);
  assert.equal((await failed).error.code, 'USER_STOPPED');
  assert.equal(f.sent.filter(item => item.command === 'ADMISSION').length, 1);
  assert.equal(f.takeoffs().length, 0);

  // Positive observation after a broken clock or at the deadline grants no effect.
  for (const now of [99, NaN, 220]) {
    f = fixture();
    failed = observe(f.backend.takeoff(.4));
    await flush();
    f.clock.now = now;
    f.respond(f.sent[0], 'VALUE 1');
    assert.equal((await failed).error.code, 'ADMISSION_UNAVAILABLE');
    assert.equal(f.takeoffs().length, 0);
  }
  f = fixture();
  f.backend.ready = false;
  assert.equal((await observe(f.backend.takeoff(.4))).error.code, 'ADMISSION_UNAVAILABLE');
  assert.equal(f.sent.length, 0);

  // Only the route profile opts in; no course/private token enters Blockly/AST.
  const setup = fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/setup.js', 'utf8');
  const context = {
    WebeeBlocksActivities: {BLOCK_CATALOG: {}}, Blockly: {inject() {}},
    WebeeBlocksWwiBackend: function(_transport, options) { this.options = options; },
    WebeeBlocksRuntimeOutcome: {classify() {}},
    // Real bundled HTML must provide a complete activity contract before
    // the variable route backend is constructed; this harness models that
    // valid script while keeping the native admission path under test.
    WebeeBlocksActivityContract: {
      execute() {}, preflightWorkspace() {}, applyFieldBounds() {}
    }
  };
  context.window = context;
  vm.runInNewContext(setup, context);
  assert.equal(new context.WebeeBlocksWwiBackend({}, {}).options.simulationAdmission, true);
  assert.equal(new context.WebeeBlocksWwiBackend({}, {}).options.simulationScenes, false);
  console.log('PASS route admission wait: bounded peek, one TAKEOFF, cancellation, native effect recheck');
}

module.exports = run;
if (require.main === module) run().catch(error => { console.error(error); process.exitCode = 1; });
