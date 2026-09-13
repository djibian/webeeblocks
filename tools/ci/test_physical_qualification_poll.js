'use strict';

const assert = require('assert');
const path = require('path');

const HELPER = path.resolve(__dirname, '../physical/physical_qualification_runtime.js');
const originalFetch = global.fetch;
const originalSetTimeout = global.setTimeout;

function response(payload, ok = true, status = 200) {
  return {
    ok: ok,
    status: status,
    async json() { return JSON.parse(JSON.stringify(payload)); }
  };
}

async function runCase({preflightFails}) {
  let prepareGets = 0;
  let preparedPosts = 0;
  const preparedPayloads = [];
  let preparedResolve;
  const preparedPromise = new Promise(resolve => { preparedResolve = resolve; });

  global.runtimeProfile = {id: 'activity-1'};
  global.WebeeBlocksPhysicalPreflight = {
    executionAuthority: false,
    configure(bootstrap) {
      assert.strictEqual(bootstrap.executionAuthority, false);
      assert.strictEqual(bootstrap.baseUrl, 'http://127.0.0.1:8765');
      assert.strictEqual(bootstrap.token, 'capability-token');
      assert.strictEqual(bootstrap.preflightResponderToken, 'responder-token');
    },
    async preflightCurrentProgram() {
      if (preflightFails)
        throw new Error('synthetic physical preflight failure');
      return {
        astBinding: '{"program":[]}',
        connectionEpoch: 'epoch-1',
        executionAuthority: false
      };
    }
  };
  global.WebeeBlocksPhysicalQualificationConfig = {
    launcherBaseUrl: 'http://127.0.0.1:9876',
    launcherToken: 'launcher-token',
    hostBootstrap: {
      baseUrl: 'http://127.0.0.1:8765',
      token: 'capability-token',
      preflightResponderToken: 'responder-token',
      executionAuthority: false
    },
    executionAuthority: false
  };

  global.fetch = async function(url, options) {
    if (url === 'http://127.0.0.1:9876/v1/prepare-request') {
      prepareGets += 1;
      assert.strictEqual(options.method, 'GET');
      assert.strictEqual(options.headers.Authorization, 'Bearer launcher-token');
      return response({requestId: 'prepare-1', executionAuthority: false});
    }
    if (url === 'http://127.0.0.1:9876/v1/prepared') {
      preparedPosts += 1;
      assert.strictEqual(options.method, 'POST');
      assert.strictEqual(options.headers.Authorization, 'Bearer launcher-token');
      const payload = JSON.parse(options.body);
      preparedPayloads.push(payload);
      preparedResolve(payload);
      return response({ok: true, executionAuthority: false});
    }
    throw new Error('unexpected qualification helper URL: ' + url);
  };

  // Let any post-settlement poll happen quickly. The fixed helper returns before
  // scheduling this delay; the pre-fix loop therefore becomes observably noisy.
  global.setTimeout = function(resolve, ms, ...args) {
    return originalSetTimeout(resolve, Math.min(Number(ms) || 0, 1), ...args);
  };

  delete require.cache[require.resolve(HELPER)];
  require(HELPER);

  const firstPrepared = await Promise.race([
    preparedPromise,
    new Promise((_, reject) => originalSetTimeout(
      () => reject(new Error('qualification browser helper did not settle preparation')),
      1000
    ))
  ]);

  // Give the real helper multiple opportunities to schedule another 200 ms poll.
  // With the accelerated timer above, an implementation that keeps polling will
  // issue many additional GETs during this window.
  await new Promise(resolve => originalSetTimeout(resolve, 30));

  assert.strictEqual(prepareGets, 1, 'settled one-shot preparation must stop launcher GET polling');
  assert.strictEqual(preparedPosts, 1, 'one-shot preparation must publish exactly one terminal result');
  assert.strictEqual(preparedPayloads.length, 1);
  assert.strictEqual(firstPrepared.executionAuthority, false);
  assert.strictEqual(firstPrepared.requestId, 'prepare-1');
  assert.strictEqual(firstPrepared.ok, !preflightFails);
  if (preflightFails) {
    assert.match(firstPrepared.error, /synthetic physical preflight failure/);
  } else {
    assert.strictEqual(firstPrepared.profileId, 'activity-1');
    assert.strictEqual(firstPrepared.astBinding, '{"program":[]}');
    assert.strictEqual(firstPrepared.connectionEpoch, 'epoch-1');
  }

  delete require.cache[require.resolve(HELPER)];
  delete global.WebeeBlocksPhysicalQualificationConfig;
  delete global.WebeeBlocksPhysicalPreflight;
  delete global.runtimeProfile;
  global.fetch = originalFetch;
  global.setTimeout = originalSetTimeout;
}

(async function() {
  await runCase({preflightFails: false});
  await runCase({preflightFails: true});
  console.log('PASS physical qualification browser preparation polls exactly once after success and fail-closed settlement');
})().catch(error => {
  global.fetch = originalFetch;
  global.setTimeout = originalSetTimeout;
  console.error(error);
  process.exit(1);
});
