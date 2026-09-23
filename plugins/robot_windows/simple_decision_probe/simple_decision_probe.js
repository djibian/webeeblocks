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

function condition(op) {
  return {
    kind:'compare', op:op,
    left:{kind:'range', direction:'front', unit:'m'},
    right:{kind:'number', value:1}
  };
}

function reactiveProgram(op, lowBranch, highBranch) {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:[
      {kind:'takeoff', height_m:0.5},
      {kind:'move', direction:'left', distance_m:0.8},
      {kind:'move', direction:'forward', distance_m:1.0},
      {kind:'if', condition:condition(op), then:lowBranch, else:highBranch},
      {kind:'land'}
    ]
  };
}

const LEFT_THEN_FORWARD = [
  {kind:'move', direction:'left', distance_m:0.4},
  {kind:'move', direction:'forward', distance_m:0.4}
];
const FORWARD_THEN_LEFT = [
  {kind:'move', direction:'forward', distance_m:0.4},
  {kind:'move', direction:'left', distance_m:0.4}
];

function fixedProgram(first, second) {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:[
      {kind:'takeoff', height_m:0.5},
      {kind:'move', direction:'left', distance_m:0.8},
      {kind:'move', direction:'forward', distance_m:1.0},
      {kind:'move', direction:first, distance_m:0.4},
      {kind:'move', direction:second, distance_m:0.4},
      {kind:'land'}
    ]
  };
}

function bypassProgram() {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:[
      {kind:'takeoff', height_m:0.5},
      {kind:'move', direction:'left', distance_m:1.2},
      {kind:'move', direction:'left', distance_m:0.1},
      {kind:'move', direction:'forward', distance_m:1.2},
      {kind:'move', direction:'forward', distance_m:0.2},
      {kind:'land'}
    ]
  };
}

async function executeCase(backend, evaluation, program, expected, eventName, expectRuntimeFailure) {
  let runtimeError = null;
  try {
    await WebeeBlocksInterpreter.run(program, backend);
  } catch (error) {
    runtimeError = error;
  }
  if (runtimeError) {
    if (!expectRuntimeFailure || runtimeError.code !== 'UNSAFE_OR_TIMEOUT')
      throw runtimeError;
    await backend.probeActivityMissionFailure(evaluation);
  } else {
    if (expectRuntimeFailure)
      throw new Error('expected fail-safe interruption for ' + eventName);
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
    const evaluation = {type:'mission-state-v1', oracle:'progression-simple-decision-v1'};
    await report('DECISION_PROBE_READY', {ready:backend.ready});

    const ordinary = reactiveProgram('LT', LEFT_THEN_FORWARD, FORWARD_THEN_LEFT);
    const blocked = await executeCase(backend, evaluation, ordinary, 'achieved', 'DECISION_BLOCKED_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'DECISION_BLOCKED_RESET_FRESH');
    const open = await executeCase(backend, evaluation, ordinary, 'achieved', 'DECISION_OPEN_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'DECISION_OPEN_RESET_FRESH');
    const hardForward = await executeCase(
      backend, evaluation, fixedProgram('forward', 'left'), 'not-achieved',
      'DECISION_HARDCODED_FORWARD_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'DECISION_FORWARD_RESET_FRESH');
    const hardLeft = await executeCase(
      backend, evaluation, fixedProgram('left', 'forward'), 'not-achieved',
      'DECISION_HARDCODED_LEFT_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'DECISION_LEFT_RESET_FRESH');
    const alternative = reactiveProgram('GT', FORWARD_THEN_LEFT, LEFT_THEN_FORWARD);
    const alternateBlocked = await executeCase(
      backend, evaluation, alternative, 'achieved', 'DECISION_ALTERNATIVE_BLOCKED_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'DECISION_ALT_BLOCKED_RESET_FRESH');
    const alternateOpen = await executeCase(
      backend, evaluation, alternative, 'achieved', 'DECISION_ALTERNATIVE_OPEN_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'DECISION_ALT_OPEN_RESET_FRESH');
    const wrongDecision = reactiveProgram('LT', FORWARD_THEN_LEFT, LEFT_THEN_FORWARD);
    const wrong = await executeCase(
      backend, evaluation, wrongDecision, 'not-achieved', 'DECISION_WRONG_DECISION_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'DECISION_WRONG_RESET_FRESH');
    const bypass = await executeCase(
      backend, evaluation, bypassProgram(), 'not-achieved', 'DECISION_BYPASS_NOT_ACHIEVED', false);

    await report('DECISION_MISSION_TEST_COMPLETE', {
      blocked:blocked.status,
      open:open.status,
      hard_forward:hardForward.status,
      hard_left:hardLeft.status,
      alternative_blocked:alternateBlocked.status,
      alternative_open:alternateOpen.status,
      wrong_decision:wrong.status,
      bypass:bypass.status
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
