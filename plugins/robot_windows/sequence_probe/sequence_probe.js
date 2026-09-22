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
    throw new Error('previous sequence outcome survived reset: ' + JSON.stringify(stale));
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

    // Activity 1 fixes movement distance at 0.1 m so parameter choice cannot
    // solve the task. Two short forward actions are one valid sequence shape.
    await flyCanonicalSequence(backend);
    await backend.completeActivityMission(evaluation);
    const achieved = await waitForOutcome(backend, evaluation, 'achieved', 8000);
    await report('SEQUENCE_ACHIEVED', achieved);

    await backend.resetSimulation();
    const fresh = await expectFreshAfterReset(backend, evaluation);
    await report('SEQUENCE_RESET_FRESH', fresh);

    // Repeat the exact same valid sequence after reset. This is deliberately
    // redundant evidence for the completion/landing boundary: a one-off green
    // run must not hide a physics-settling race in the mission oracle.
    await flyCanonicalSequence(backend);
    await backend.completeActivityMission(evaluation);
    const repeat = await waitForOutcome(backend, evaluation, 'achieved', 8000);
    await report('SEQUENCE_REPEAT_ACHIEVED', repeat);

    await backend.resetSimulation();
    const repeatFresh = await expectFreshAfterReset(backend, evaluation);
    await report('SEQUENCE_REPEAT_RESET_FRESH', repeatFresh);

    // A complete executable sequence that lands back outside the target must
    // remain a world-state failure rather than a solution-shape judgement.
    await backend.takeoff(0.5);
    await backend.land();
    await backend.completeActivityMission(evaluation);
    const notAchieved = await waitForOutcome(backend, evaluation, 'not-achieved', 8000);
    await report('SEQUENCE_NOT_ACHIEVED', notAchieved);

    await backend.resetSimulation();
    const freshAgain = await expectFreshAfterReset(backend, evaluation);
    await report('SEQUENCE_SECOND_RESET_FRESH', freshAgain);

    // Three identical fixed-distance moves are a different valid block sequence
    // with the same observable mission result, proving the oracle is not tied to
    // one expected Blockly/AST shape.
    await backend.takeoff(0.5);
    await backend.move('forward', 0.1);
    await backend.move('forward', 0.1);
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
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
