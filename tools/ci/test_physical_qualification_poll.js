'use strict';

const assert = require('assert');
const childProcess = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const HELPER = path.resolve(__dirname, '../physical/physical_qualification_runtime.js');
const WEBOTS_WRAPPER = path.resolve(__dirname, '../physical/run_webots_qualification_world.sh');
const PERSPECTIVE_SOURCE = path.resolve(__dirname, '../physical/qualification_world.wbproj');
const originalFetch = global.fetch;
const originalSetTimeout = global.setTimeout;

function response(payload, ok = true, status = 200) {
  return {
    ok: ok,
    status: status,
    async json() { return JSON.parse(JSON.stringify(payload)); }
  };
}

function writeFakeWebots(root, body) {
  const fakeWebots = path.join(root, 'fake-webots.sh');
  fs.writeFileSync(fakeWebots, '#!/usr/bin/env bash\nset -euo pipefail\n' + body, 'utf8');
  fs.chmodSync(fakeWebots, 0o755);
  return fakeWebots;
}

function testFinalWorldGetsExactLifecyclePerspective() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'webeeblocks-qualification-perspective-'));
  try {
    const worlds = path.join(root, 'worlds');
    fs.mkdirSync(worlds);
    const world = path.join(worlds, '.webeeblocks-physical-regression.wbt');
    fs.writeFileSync(world, '#VRML_SIM R2025a utf8\nRobot { }\n', 'utf8');
    const observed = path.join(root, 'observed-perspective.txt');
    const fakeWebots = writeFakeWebots(
      root,
      'last=""\n' +
      'for arg in "$@"; do last="$arg"; done\n' +
      'base="$(basename "$last" .wbt)"\n' +
      'perspective="$(dirname "$last")/.$base.wbproj"\n' +
      'test -f "$perspective"\n' +
      "grep -Fxq 'Webots Project File version R2025a' \"$perspective\"\n" +
      "test \"$(grep -Fxc 'robotWindow: Crazyflie WebeeBlocks' \"$perspective\")\" -eq 1\n" +
      'printf \'%s\\n\' "$perspective" > "$WEBEEBLOCKS_OBSERVED_PERSPECTIVE"\n'
    );

    const expectedPerspective = path.join(worlds, '..webeeblocks-physical-regression.wbproj');
    const result = childProcess.spawnSync(
      'bash',
      [WEBOTS_WRAPPER, '--mode=fast', world],
      {
        cwd: root,
        encoding: 'utf8',
        env: {
          ...process.env,
          WEBEEBLOCKS_REAL_WEBOTS: fakeWebots,
          WEBEEBLOCKS_QUALIFICATION_PERSPECTIVE: PERSPECTIVE_SOURCE,
          WEBEEBLOCKS_OBSERVED_PERSPECTIVE: observed
        }
      }
    );
    assert.strictEqual(
      result.status,
      0,
      'qualification Webots wrapper must start fake Webots with the exact final perspective: ' +
        result.stdout + '\n' + result.stderr
    );
    assert.strictEqual(
      fs.readFileSync(observed, 'utf8').trim(),
      expectedPerspective,
      'Webots must observe the perspective derived from the final ephemeral world complete basename'
    );
    assert.strictEqual(
      fs.existsSync(expectedPerspective),
      false,
      'final qualification perspective must be removed when Webots exits'
    );
  } finally {
    fs.rmSync(root, {recursive: true, force: true});
  }
}

function testPerspectiveSurvivesForwardedTermination() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'webeeblocks-qualification-signal-'));
  try {
    const worlds = path.join(root, 'worlds');
    fs.mkdirSync(worlds);
    const world = path.join(worlds, '.webeeblocks-physical-signal.wbt');
    fs.writeFileSync(world, '#VRML_SIM R2025a utf8\nRobot { }\n', 'utf8');
    const ready = path.join(root, 'child-ready.txt');
    const observed = path.join(root, 'child-exit-observation.txt');
    const fakeWebots = writeFakeWebots(
      root,
      'last=""\n' +
      'for arg in "$@"; do last="$arg"; done\n' +
      'base="$(basename "$last" .wbt)"\n' +
      'perspective="$(dirname "$last")/.$base.wbproj"\n' +
      'test -f "$perspective"\n' +
      'printf ready > "$WEBEEBLOCKS_CHILD_READY"\n' +
      "trap 'test -f \"$perspective\"; sleep 0.25; test -f \"$perspective\"; printf perspective_present_before_child_exit > \"$WEBEEBLOCKS_CHILD_OBSERVED\"; exit 143' TERM\n" +
      'while true; do sleep 0.05; done\n'
    );
    const expectedPerspective = path.join(worlds, '..webeeblocks-physical-signal.wbproj');
    const driver = [
      'set -euo pipefail',
      `wrapper=${JSON.stringify(WEBOTS_WRAPPER)}`,
      `world=${JSON.stringify(world)}`,
      `ready=${JSON.stringify(ready)}`,
      `observed=${JSON.stringify(observed)}`,
      `perspective=${JSON.stringify(expectedPerspective)}`,
      'bash "$wrapper" "$world" &',
      'wrapper_pid=$!',
      'for _ in $(seq 1 100); do [[ -f "$ready" ]] && break; sleep 0.02; done',
      'test -f "$ready"',
      'test -f "$perspective"',
      'kill -TERM "$wrapper_pid"',
      'sleep 0.08',
      'kill -0 "$wrapper_pid"',
      'test -f "$perspective"',
      'set +e',
      'wait "$wrapper_pid"',
      'wrapper_status=$?',
      'set -e',
      'test "$wrapper_status" -ne 0',
      'test "$(cat "$observed")" = perspective_present_before_child_exit',
      'test ! -e "$perspective"'
    ].join('\n');
    const result = childProcess.spawnSync(
      'bash',
      ['-c', driver],
      {
        cwd: root,
        encoding: 'utf8',
        timeout: 5000,
        env: {
          ...process.env,
          WEBEEBLOCKS_REAL_WEBOTS: fakeWebots,
          WEBEEBLOCKS_QUALIFICATION_PERSPECTIVE: PERSPECTIVE_SOURCE,
          WEBEEBLOCKS_CHILD_READY: ready,
          WEBEEBLOCKS_CHILD_OBSERVED: observed
        }
      }
    );
    assert.strictEqual(
      result.status,
      0,
      'wrapper must remain alive with perspective until delayed child termination: ' +
        result.stdout + '\n' + result.stderr
    );
  } finally {
    fs.rmSync(root, {recursive: true, force: true});
  }
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
  testFinalWorldGetsExactLifecyclePerspective();
  testPerspectiveSurvivesForwardedTermination();
  await runCase({preflightFails: false});
  await runCase({preflightFails: true});
  console.log('PASS physical qualification browser preparation and Webots perspective lifecycle fail closed');
})().catch(error => {
  global.fetch = originalFetch;
  global.setTimeout = originalSetTimeout;
  console.error(error);
  process.exit(1);
});
