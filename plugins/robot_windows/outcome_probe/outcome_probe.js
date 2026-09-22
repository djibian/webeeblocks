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
        await sleep(150);
        continue;
      }
      throw error;
    }
  }
  throw new Error('timeout waiting for outcome ' + expected);
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
    await report('PROBE_READY', {ready: backend.ready});

    const evaluation = {type: 'mission-state-v1', oracle: 'ci-outcome-v1'};
    const first = await waitForOutcome(backend, evaluation, 'achieved', 10000);
    await report('ATTEMPT_A', first);

    await backend.resetSimulation();
    await report('RESET_OK', {ready: backend.ready});

    let staleCode = null;
    try {
      const stale = await backend.readActivityOutcome(evaluation);
      throw new Error('stale outcome survived reset: ' + JSON.stringify(stale));
    } catch (error) {
      if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
        throw error;
      staleCode = error.code;
    }
    await report('NO_STALE_AFTER_RESET', {code: staleCode});

    const second = await waitForOutcome(backend, evaluation, 'not-achieved', 12000);
    await report('ATTEMPT_B', second);
    await report('OUTCOME_PROVIDER_TEST_COMPLETE', {first: first.status, second: second.status});
  } catch (error) {
    await report('ERROR', {message: error && error.message ? error.message : String(error), code: error && error.code ? error.code : null});
  }
})();
