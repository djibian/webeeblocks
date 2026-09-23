function sleep(ms) {
  return new Promise(function(resolve) { setTimeout(resolve, ms); });
}

let reportChain = Promise.resolve();
function report(event, detail) {
  const payload = {event:event, detail:detail === undefined ? null : detail, wall_ms:Date.now()};
  reportChain = reportChain.then(function() {
    return fetch('http://127.0.0.1:8765/event', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
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

async function resetAndProveFresh(backend, evaluation, eventName) {
  await backend.resetSimulation();
  try {
    const stale = await backend.readActivityOutcome(evaluation);
    throw new Error('previous mission outcome survived reset: ' + JSON.stringify(stale));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await report(eventName, {code:error.code});
  }
}

async function repeatedMotif(backend) {
  await backend.move('forward', 0.2);
  await backend.move('left', 0.6);
}

window.addEventListener('error', function(event) {
  report('WINDOW_ERROR', {message:event.message, filename:event.filename, lineno:event.lineno});
});
window.addEventListener('unhandledrejection', function(event) {
  report('UNHANDLED_REJECTION', String(event.reason));
});

(async function() {
  try {
    const module = await import('../blockly_v2/webots/RobotWindow.js');
    const robotWindow = new module.default();
    const backend = new WebeeBlocksWwiBackend(robotWindow, {simulationReset:true});
    robotWindow.receive = function(message) { backend.handleMessage(String(message)); };
    await backend.waitUntilReady();
    const repeat = {type:'mission-state-v1', oracle:'progression-repeat-v1'};
    await report('REPEAT_PROBE_READY', {ready:backend.ready});

    await backend.takeoff(0.5);
    for (let index = 0; index < 3; ++index)
      await repeatedMotif(backend);
    await backend.move('forward', 0.2);
    await backend.land();
    await backend.completeActivityMission(repeat);
    const loopShaped = await waitForOutcome(backend, repeat, 'achieved', 8000);
    await report('REPEAT_LOOP_SHAPED_ACHIEVED', loopShaped);

    await resetAndProveFresh(backend, repeat, 'REPEAT_LOOP_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('forward', 0.2);
    await backend.move('left', 0.6);
    await backend.move('forward', 0.2);
    await backend.move('left', 0.6);
    await backend.move('forward', 0.2);
    await backend.move('left', 0.6);
    await backend.move('forward', 0.2);
    await backend.land();
    await backend.completeActivityMission(repeat);
    const unrolled = await waitForOutcome(backend, repeat, 'achieved', 8000);
    await report('REPEAT_UNROLLED_ACHIEVED', unrolled);

    await resetAndProveFresh(backend, repeat, 'REPEAT_UNROLLED_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('forward', 0.2);
    await backend.move('left', 0.6);
    await backend.move('forward', 0.6);
    await backend.move('left', 0.6);
    await backend.move('left', 0.6);
    await backend.land();
    await backend.completeActivityMission(repeat);
    const skipped = await waitForOutcome(backend, repeat, 'not-achieved', 8000);
    await report('REPEAT_SKIPPED_BEACONS_NOT_ACHIEVED', skipped);

    await resetAndProveFresh(backend, repeat, 'REPEAT_SKIP_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('forward', 0.4);
    await backend.move('left', 0.6);
    await backend.move('left', 0.6);
    const outOfOrder = await waitForOutcome(backend, repeat, 'not-achieved', 8000);
    await report('REPEAT_OUT_OF_ORDER_NOT_ACHIEVED', outOfOrder);

    await resetAndProveFresh(backend, repeat, 'REPEAT_ORDER_RESET_FRESH');
    await backend.takeoff(0.5);
    await backend.move('forward', 0.1);
    await backend.move('left', 0.6);
    await backend.move('forward', 0.2);
    await backend.move('left', 0.6);
    await backend.move('forward', 0.2);
    await backend.move('left', 0.6);
    await backend.move('forward', 0.3);
    await backend.land();
    await backend.completeActivityMission(repeat);
    const wrongDistance = await waitForOutcome(backend, repeat, 'not-achieved', 8000);
    await report('REPEAT_WRONG_DISTANCE_NOT_ACHIEVED', wrongDistance);

    await resetAndProveFresh(backend, repeat, 'REPEAT_DISTANCE_RESET_FRESH');
    await backend.takeoff(0.5);
    let collisionError = null;
    try {
      await backend.move('forward', 0.4);
    } catch (error) {
      collisionError = error;
    }
    if (!collisionError || collisionError.code !== 'UNSAFE_OR_TIMEOUT')
      throw new Error('expected obstacle contact fail-safe, got: ' + String(collisionError));
    await backend.completeActivityMission(repeat);
    const collision = await waitForOutcome(backend, repeat, 'not-achieved', 8000);
    await report('REPEAT_COLLISION_NOT_ACHIEVED', {
      status:collision.status, runtime_code:collisionError.code, completion_preserved:true
    });

    await resetAndProveFresh(backend, repeat, 'REPEAT_COLLISION_RESET_FRESH');
    await report('REPEAT_MISSION_TEST_COMPLETE', {
      loop_shaped:loopShaped.status,
      unrolled:unrolled.status,
      skipped:skipped.status,
      out_of_order:outOfOrder.status,
      wrong_distance:wrongDistance.status,
      collision:collision.status
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
