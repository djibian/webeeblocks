function sleep(ms) {
  return new Promise(function(resolve) { setTimeout(resolve, ms); });
}

let reportChain = Promise.resolve();
function report(event, detail) {
  const payload = {event: event, detail: detail === undefined ? null : detail, wall_ms: Date.now()};
  reportChain = reportChain.then(function() {
    return fetch('http://127.0.0.1:8765/event', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
  });
  return reportChain;
}

async function waitForOutcome(backend, evaluation, expected, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const result = await backend.readActivityOutcome(evaluation);
      if (!result || result.status !== expected)
        throw new Error('unexpected outcome: ' + JSON.stringify(result));
      return result;
    } catch (error) {
      if (error && error.code === 'OUTCOME_UNAVAILABLE') {
        await sleep(120);
        continue;
      }
      throw error;
    }
  }
  throw new Error('timeout waiting for outcome ' + expected);
}

async function expectFreshAfterReset(backend, evaluation) {
  try {
    const stale = await backend.readActivityOutcome(evaluation);
    throw new Error('previous mission outcome survived reset: ' + JSON.stringify(stale));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    return {code:error.code};
  }
}

async function flyCanonicalSequence(backend) {
  try { await backend.readElapsedTime(); throw new Error('time available before takeoff'); }
  catch (error) { if (error.code !== 'TIME_UNAVAILABLE') throw error; }
  await backend.takeoff(0.5);
  const before = await backend.readRange('front');
  if (Math.abs(before - 2.0) > 0.01) throw new Error('off-activity obstacle remains visible: ' + before);
  try {
    await backend.prepareActivity({id:'progression-precise-movement-v1'});
    throw new Error('scene changed in flight');
  } catch (error) {
    if (!error || error.code !== 'RESET_REQUIRED') throw error;
  }
  const start = await backend.readElapsedTime();
  if (!Number.isFinite(start) || start <= 0) throw new Error('takeoff duration missing from simulated clock');
  await backend.wait(0.5);
  const after = await backend.readElapsedTime();
  if (after - start < 0.5 || after - start > 1.5) throw new Error('wrong Webots wait/elapsed time relationship');
  await report('ELAPSED_TIME_WEBOTS', {start:start, after:after});
  await backend.move('forward', 0.1);
  await backend.move('forward', 0.1);
  await backend.land();
  try { await backend.readElapsedTime(); throw new Error('time available after land'); }
  catch (error) { if (error.code !== 'TIME_UNAVAILABLE') throw error; }
}

async function resetAndProveFresh(backend, evaluation, eventName) {
  await backend.resetSimulation();
  const fresh = await expectFreshAfterReset(backend, evaluation);
  await report(eventName, fresh);
}

// CI-only: both neutral and ordinary progression probes can advance fewer
// than 25 simulated seconds during 35 wall seconds under software Webots.
// Keep the actual native fail-safe (25 simulated seconds) and every mission
// oracle unchanged. Only these test windows have a bounded 60s response budget;
// the product WWI backend retains its 35s default and silence still fails.
const PROGRESSION_CI_TIMEOUT_MS = 60000;

window.addEventListener('error', function(event) {
  report('WINDOW_ERROR', {message: event.message, filename: event.filename, lineno: event.lineno});
});
window.addEventListener('unhandledrejection', function(event) {
  report('UNHANDLED_REJECTION', String(event.reason));
});

(async function() {
  try {
    const module = await import('../blockly_v2/webots/RobotWindow.js');
    const robotWindow = new module.default();
    const sent = [];
    const transport = {send(message) { sent.push(message); robotWindow.send(message); }};
    let backend = new WebeeBlocksWwiBackend(transport, {simulationReset: true, simulationScenes: true, timeoutMs: PROGRESSION_CI_TIMEOUT_MS});
    robotWindow.receive = function(message) {
      backend.handleMessage(String(message));
    };
    await backend.waitUntilReady();
    async function reattachScene(profile, event) {
      // Keep the native controller and RobotWindow connection alive; replace
      // only the page-side backend, as when attaching a fresh Robot Window.
      backend = new WebeeBlocksWwiBackend(transport, {simulationReset:true,simulationScenes:true, timeoutMs: PROGRESSION_CI_TIMEOUT_MS});
      await backend.waitUntilReady();
      if (backend.sceneIdentity !== null) throw new Error('reattached backend presumed scene');
      const start = sent.length;
      await backend.prepareActivity(profile);
      const scene = profile.id === 'progression-sequence-v1' ? 'sequence-v1' : 'legacy-v1';
      const requests = sent.slice(start);
      if (requests.length !== 1 || !new RegExp('^WEBEEBLOCKS_RUNTIME_V2 REQUEST \\d+ SCENE ' + scene + ' [0-9a-f]{64}$').test(requests[0]))
        throw new Error('reattachment did not acknowledge one native scene request: ' + JSON.stringify(requests));
      await report(event, {scene:scene, requests:requests.length});
    }
    const evaluation = {type:'mission-state-v1', oracle:'progression-sequence-v1'};
    await report('SEQUENCE_PROBE_READY', {ready:backend.ready});
    if (window.WebeeBlocksNeutralStartupProbe === true) {
      try {
        await backend.takeoff(0.5);
        throw new Error('neutral startup accepted TAKEOFF before SCENE');
      } catch (error) {
        if (!error || error.code !== 'SCENE_UNAVAILABLE') throw error;
        await report('NEUTRAL_TAKEOFF_REFUSED', {code:error.code});
      }
    }
    await backend.prepareActivity({id:'progression-sequence-v1'});
    await report('SEQUENCE_SCENE_ISOLATED', {scene:'sequence-v1'});

    await flyCanonicalSequence(backend);
    await backend.completeActivityMission(evaluation);
    const achieved = await waitForOutcome(backend, evaluation, 'achieved', 8000);
    await report('SEQUENCE_ACHIEVED', achieved);

    await resetAndProveFresh(backend, evaluation, 'SEQUENCE_RESET_FRESH');

    await flyCanonicalSequence(backend);
    await backend.completeActivityMission(evaluation);
    const repeat = await waitForOutcome(backend, evaluation, 'achieved', 8000);
    await report('SEQUENCE_REPEAT_ACHIEVED', repeat);

    await resetAndProveFresh(backend, evaluation, 'SEQUENCE_REPEAT_RESET_FRESH');

    await backend.takeoff(0.5);
    await backend.land();
    await backend.completeActivityMission(evaluation);
    const notAchieved = await waitForOutcome(backend, evaluation, 'not-achieved', 8000);
    await report('SEQUENCE_NOT_ACHIEVED', notAchieved);

    await resetAndProveFresh(backend, evaluation, 'SEQUENCE_SECOND_RESET_FRESH');

    await backend.takeoff(0.5);
    await backend.move('forward', 0.1);
    await backend.land();
    await backend.takeoff(0.5);
    await backend.move('forward', 0.1);
    await backend.land();
    await backend.completeActivityMission(evaluation);
    const alternative = await waitForOutcome(backend, evaluation, 'achieved', 8000);
    await report('SEQUENCE_ALTERNATIVE_ACHIEVED', alternative);
    await report('SEQUENCE_MISSION_TEST_COMPLETE', {
      canonical:achieved.status,
      repeat:repeat.status,
      negative:notAchieved.status,
      alternative:alternative.status
    });

    const precise = {type:'mission-state-v1', oracle:'progression-precise-movement-v1'};
    await resetAndProveFresh(backend, precise, 'PRECISE_INITIAL_RESET_FRESH');
    await reattachScene({id:'progression-precise-movement-v1'}, 'LEGACY_SCENE_REATTACHED');
    await report('LEGACY_SCENE_RESTORED', {scene:'legacy-v1'});

    await backend.takeoff(0.5);
    await backend.move('forward', 0.3);
    await backend.move('left', 0.4);
    await backend.land();
    await backend.completeActivityMission(precise);
    const preciseAchieved = await waitForOutcome(backend, precise, 'achieved', 8000);
    await report('PRECISE_ACHIEVED', preciseAchieved);

    await resetAndProveFresh(backend, precise, 'PRECISE_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('forward', 0.1);
    await backend.move('left', 0.4);
    await backend.land();
    await backend.completeActivityMission(precise);
    const undershoot = await waitForOutcome(backend, precise, 'not-achieved', 8000);
    await report('PRECISE_UNDERSHOOT_NOT_ACHIEVED', undershoot);

    await resetAndProveFresh(backend, precise, 'PRECISE_UNDERSHOOT_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('left', 0.4);
    await backend.move('forward', 0.5);
    await backend.land();
    await backend.completeActivityMission(precise);
    const overshoot = await waitForOutcome(backend, precise, 'not-achieved', 8000);
    await report('PRECISE_OVERSHOOT_NOT_ACHIEVED', overshoot);

    await resetAndProveFresh(backend, precise, 'PRECISE_OVERSHOOT_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('forward', 0.3);
    await backend.move('left', 0.1);
    await backend.land();
    await backend.completeActivityMission(precise);
    const lateralMiss = await waitForOutcome(backend, precise, 'not-achieved', 8000);
    await report('PRECISE_LATERAL_NOT_ACHIEVED', lateralMiss);

    await resetAndProveFresh(backend, precise, 'PRECISE_LATERAL_RESET_FRESH');
    await backend.takeoff(0.5);
    let collisionError = null;
    try {
      await backend.move('forward', 0.4);
    } catch (error) {
      collisionError = error;
    }
    if (!collisionError || collisionError.code !== 'UNSAFE_OR_TIMEOUT')
      throw new Error('expected obstacle contact to trigger Runtime fail-safe, got: ' + String(collisionError));
    await backend.completeActivityMission(precise);
    const collision = await waitForOutcome(backend, precise, 'not-achieved', 8000);
    await report('PRECISE_COLLISION_NOT_ACHIEVED', {
      status:collision.status,
      runtime_code:collisionError.code,
      completion_preserved:true
    });

    await resetAndProveFresh(backend, precise, 'PRECISE_COLLISION_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('forward', 0.2);
    await backend.move('forward', 0.1);
    await backend.move('left', 0.2);
    await backend.move('left', 0.2);
    await backend.land();
    await backend.completeActivityMission(precise);
    const preciseAlternative = await waitForOutcome(backend, precise, 'achieved', 8000);
    await report('PRECISE_ALTERNATIVE_ACHIEVED', preciseAlternative);
    await backend.resetSimulation();
    await reattachScene({id:'progression-sequence-v1'}, 'SEQUENCE_SCENE_REATTACHED');
    await backend.takeoff(0.5);
    const restoredRange = await backend.readRange('front');
    if (Math.abs(restoredRange - 2.0) > 0.01) throw new Error('reattached Activity 1 retained a legacy obstacle');
    await backend.land();
    await report('SEQUENCE_REATTACHED_RANGE', {front:restoredRange});
    await report('PRECISE_MISSION_TEST_COMPLETE', {
      canonical:preciseAchieved.status,
      undershoot:undershoot.status,
      overshoot:overshoot.status,
      lateral:lateralMiss.status,
      collision:collision.status,
      alternative:preciseAlternative.status
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
