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
  await backend.takeoff(0.5);
  await backend.move('forward', 0.1);
  await backend.move('forward', 0.1);
  await backend.land();
}

async function resetAndProveFresh(backend, evaluation, eventName) {
  await backend.resetSimulation();
  const fresh = await expectFreshAfterReset(backend, evaluation);
  await report(eventName, fresh);
}

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
    const backend = new WebeeBlocksWwiBackend(robotWindow, {simulationReset: true});
    robotWindow.receive = function(message) {
      backend.handleMessage(String(message));
    };
    await backend.waitUntilReady();
    const evaluation = {type:'mission-state-v1', oracle:'progression-sequence-v1'};
    await report('SEQUENCE_PROBE_READY', {ready:backend.ready});

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
    const collision = await waitForOutcome(backend, precise, 'not-achieved', 8000);
    await report('PRECISE_COLLISION_NOT_ACHIEVED', {status:collision.status, runtime_code:collisionError.code});

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
