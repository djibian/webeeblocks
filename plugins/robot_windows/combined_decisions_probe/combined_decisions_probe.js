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

async function proveFailureProbeUnavailableWithoutFailure(backend, evaluation) {
  try {
    const unexpected = await backend.readActivityOutcome(evaluation);
    throw new Error('unexpected outcome while priming Activity 6 attempt: ' + JSON.stringify(unexpected));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
  }
  await sleep(120);
  await backend.probeActivityMissionFailure(evaluation);
  try {
    const unexpected = await backend.readActivityOutcome(evaluation);
    throw new Error('failure probe synthesized outcome without route failure: ' + JSON.stringify(unexpected));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await report('COMBINED_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE', {code:error.code});
  }
}

async function resetAndProveFresh(backend, evaluation, eventName) {
  await backend.resetSimulation();
  try {
    const stale = await backend.readActivityOutcome(evaluation);
    throw new Error('previous Activity 6 outcome survived reset: ' + JSON.stringify(stale));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await report(eventName, {code:error.code});
  }
}

function clearCondition(direction) {
  return {
    kind:'compare', op:'GT',
    left:{kind:'range', direction:direction, unit:'m'},
    right:{kind:'number', value:1.0}
  };
}

function approach() {
  return [
    {kind:'takeoff', height_m:0.5},
    {kind:'move', direction:'right', distance_m:0.6},
    {kind:'repeat', count:2, body:[
      {kind:'move', direction:'forward', distance_m:0.7}
    ]}
  ];
}

function forwardRoute() {
  return [
    {kind:'move', direction:'forward', distance_m:0.3},
    {kind:'move', direction:'forward', distance_m:0.1},
    {kind:'move', direction:'left', distance_m:0.3}
  ];
}

function leftRoute() {
  return [
    {kind:'move', direction:'left', distance_m:0.3},
    {kind:'move', direction:'forward', distance_m:0.4}
  ];
}

function rightRoute() {
  return [
    {kind:'move', direction:'right', distance_m:0.3},
    {kind:'move', direction:'forward', distance_m:0.4},
    {kind:'move', direction:'left', distance_m:0.6}
  ];
}

function programWithDecision(decision) {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:approach().concat([decision, {kind:'land'}])
  };
}

function multiPerceptionProgram() {
  return programWithDecision({
    kind:'if', condition:clearCondition('front'), then:forwardRoute(), else:[
      {kind:'if', condition:clearCondition('left'), then:leftRoute(), else:[
        {kind:'if', condition:clearCondition('right'), then:rightRoute(), else:[]}
      ]}
    ]
  });
}

function frontOnlyShortcutProgram() {
  return programWithDecision({
    kind:'if', condition:clearCondition('front'), then:forwardRoute(), else:leftRoute()
  });
}

function frontLeftShortcutProgram() {
  return programWithDecision({
    kind:'if', condition:clearCondition('front'), then:forwardRoute(), else:[
      {kind:'if', condition:clearCondition('left'), then:leftRoute(), else:forwardRoute()}
    ]
  });
}

function rightFirstEquivalentProgram() {
  return programWithDecision({
    kind:'if', condition:clearCondition('right'), then:rightRoute(), else:[
      {kind:'if', condition:clearCondition('left'), then:leftRoute(), else:forwardRoute()}
    ]
  });
}

async function executeCase(backend, evaluation, program, expected, eventName, allowRuntimeFailure) {
  let runtimeError = null;
  try {
    await WebeeBlocksInterpreter.run(program, backend);
  } catch (error) {
    runtimeError = error;
  }
  if (runtimeError) {
    if (!allowRuntimeFailure || runtimeError.code !== 'UNSAFE_OR_TIMEOUT')
      throw runtimeError;
    await backend.probeActivityMissionFailure(evaluation);
  } else {
    await backend.completeActivityMission(evaluation);
  }
  const outcome = await waitForOutcome(backend, evaluation, expected, 8000);
  await report(eventName, runtimeError ? {status:outcome.status, runtime_code:runtimeError.code} : outcome);
  return outcome;
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
    const evaluation = {type:'mission-state-v1', oracle:'progression-combined-decisions-v1'};
    await report('COMBINED_PROBE_READY', {ready:backend.ready});
    await proveFailureProbeUnavailableWithoutFailure(backend, evaluation);

    const multiObb = await executeCase(backend, evaluation, multiPerceptionProgram(), 'achieved', 'COMBINED_MULTI_OBB_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'COMBINED_MULTI_OBB_RESET_FRESH');
    const multiBob = await executeCase(backend, evaluation, multiPerceptionProgram(), 'achieved', 'COMBINED_MULTI_BOB_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'COMBINED_MULTI_BOB_RESET_FRESH');
    const multiBbo = await executeCase(backend, evaluation, multiPerceptionProgram(), 'achieved', 'COMBINED_MULTI_BBO_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'COMBINED_SKIP_TO_OBB_FRESH');
    await resetAndProveFresh(backend, evaluation, 'COMBINED_SKIP_TO_BOB_FRESH');
    await resetAndProveFresh(backend, evaluation, 'COMBINED_FRONT_ONLY_BBO_FRESH');
    const frontOnly = await executeCase(backend, evaluation, frontOnlyShortcutProgram(), 'not-achieved', 'COMBINED_FRONT_ONLY_BBO_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'COMBINED_FRONT_LEFT_SKIP_OBB_FRESH');
    await resetAndProveFresh(backend, evaluation, 'COMBINED_FRONT_LEFT_SKIP_BOB_FRESH');
    await resetAndProveFresh(backend, evaluation, 'COMBINED_FRONT_LEFT_BBO_FRESH');
    const frontLeft = await executeCase(backend, evaluation, frontLeftShortcutProgram(), 'not-achieved', 'COMBINED_FRONT_LEFT_BBO_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'COMBINED_ALT_OBB_FRESH');
    const altObb = await executeCase(backend, evaluation, rightFirstEquivalentProgram(), 'achieved', 'COMBINED_ALT_OBB_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'COMBINED_ALT_OBB_RESET_FRESH');
    const altBob = await executeCase(backend, evaluation, rightFirstEquivalentProgram(), 'achieved', 'COMBINED_ALT_BOB_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'COMBINED_ALT_BOB_RESET_FRESH');
    const altBbo = await executeCase(backend, evaluation, rightFirstEquivalentProgram(), 'achieved', 'COMBINED_ALT_BBO_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'COMBINED_FINAL_RESET_FRESH');
    await report('COMBINED_MISSION_TEST_COMPLETE', {
      multi_obb:multiObb.status,
      multi_bob:multiBob.status,
      multi_bbo:multiBbo.status,
      front_only_bbo:frontOnly.status,
      front_left_bbo:frontLeft.status,
      alternate_obb:altObb.status,
      alternate_bob:altBob.status,
      alternate_bbo:altBbo.status
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
