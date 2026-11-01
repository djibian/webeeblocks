'use strict';
// Two actual producers share one storage Map and one simulated Web Locks manager.
// This test is executed by the existing fast Runtime suite.
const assert = require('node:assert/strict');
const Recovery = require('../../plugins/robot_windows/blockly_v2/simulation_recovery.js');
const makeRenewal = require('../../plugins/robot_windows/blockly_v2/window_renewal.js');
const KEY = 'webeeblocks-world-recovery-v1';
module.exports = async function () {
  const store = new Map(), old = global.localStorage;
  const storage = {
    getItem: k => store.has(k) ? store.get(k) : null,
    setItem: (k,v) => store.set(k,v),
    removeItem: k => store.delete(k)
  };
  let inLock = 0, peak = 0, tail = Promise.resolve(), natives = [];
  const locks = {request(name, options, callback) {
    assert.equal(name, 'webeeblocks-recovery-v1');
    assert.equal(options.mode, 'exclusive');
    const operation = tail.then(async () => {
      if (options.signal.aborted) throw new Error('lock aborted');
      ++inLock; peak = Math.max(peak, inLock);
      try { return await callback(); } finally { --inLock; }
    });
    tail = operation.then(() => undefined, () => undefined);
    return operation;
  }};
  const root = () => ({
    navigator: {locks}, localStorage: storage, AbortController,
    performance: {now: () => performance.now()},
    setTimeout, clearTimeout,
    location:{protocol:'http:',hostname:'localhost',pathname:'/robot_windows/blockly_v2/blockly_v2.html'}
  });
  const A = makeRenewal(root()), B = makeRenewal(root());
  const program = n => JSON.stringify({blocks:{blocks:[{type:'math_number',fields:{NUM:n}}]}});
  async function produce(instance, label, number) {
    return instance.withRecoveryLock(async () => {
      const workspace = program(number);
      const digest = await Recovery.fingerprint('reactive-obstacle-v2', workspace);
      const cp = Recovery.save('reactive-obstacle-v2', workspace, 4, digest);
      assert(instance.arm(cp.token), 'producer failed to arm its own checkpoint');
      natives.push({label, token:cp.token, digest});
      return cp;
    });
  }
  global.localStorage = storage;
  try {
    // Baseline vulnerable save() overwrote A with B; this run MUST keep A intact.
    const [first, second] = await Promise.allSettled([produce(A,'A',1), produce(B,'B',2)]);
    assert.equal(first.status,'fulfilled');
    assert.equal(second.status,'rejected');
    assert.match(second.reason.message,/already exists/);
    assert.equal(store.get(KEY),JSON.stringify(first.value),'checkpoint A bytes changed');
    assert.equal(Recovery.peek().workspace,program(1));
    assert.deepEqual(natives.map(n=>n.label),['A'],'B armed a second native reload');
    assert.equal(peak,1,'two native producers overlapped');
    assert.notEqual(await Recovery.fingerprint('reactive-obstacle-v2',program(1)),
      await Recovery.fingerprint('reactive-obstacle-v2',program(2)));
    store.set(KEY,'{invalid preexisting checkpoint');
    const before=store.get(KEY);
    await assert.rejects(produce(B,'B',2),/already exists/);
    assert.equal(store.get(KEY),before,'corrupt previous checkpoint overwritten');
    assert.equal(natives.length,1);
    await assert.rejects(makeRenewal({navigator:{},performance:{now:()=>0},
      AbortController,setTimeout,clearTimeout}).withRecoveryLock(() => produce(B,'B',2)),
      /indisponible/);
    assert.equal(natives.length,1);
  } finally {
    if (old === undefined) delete global.localStorage;
    else global.localStorage=old;
  }
  console.log('PASS R1: real shared-store two producers, single exclusive lock, corrupt occupancy, no second native arm');
};
