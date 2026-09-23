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

function frontBlockedCondition() {
  return {
    kind:'compare', op:'LT',
    left:{kind:'range', direction:'front', unit:'m'},
    right:{kind:'number', value:1}
  };
}

function approach() {
  return [
    {kind:'takeoff', height_m:0.5},
    {kind:'move', direction:'left', distance_m:0.8},
    {kind:'move', direction:'left', distance_m:0.8},
    {kind:'move', direction:'forward', distance_m:0.9}
  ];
}

function freshDecisionStep() {
  return {
    kind:'if', condition:frontBlockedCondition(),
    then:[{kind:'move', direction:'left', distance_m:0.3}],
    else:[]
  };
}

function repeatedReactiveProgram() {
  return {
    version:1, semantics:'webeeblocks-ast-v1',
    program:approach().concat([
      {kind:'repeat', count:3, body:[
        freshDecisionStep(),
        {kind:'move', direction:'forward', distance_m:0.3}
      ]},
      {kind:'land'}
    ])
  };
}

function oneMeasurementProgram() {
  return {
    version:1, semantics:'webeeblocks-ast-v1',
    program:approach().concat([
      {kind:'if', condition:frontBlockedCondition(), then:[
        {kind:'repeat', count:3, body:[
          {kind:'move', direction:'left', distance_m:0.3},
          {kind:'move', direction:'forward', distance_m:0.3}
        ]}
      ], else:[
        {kind:'repeat', count:3, body:[
          {kind:'move', direction:'forward', distance_m:0.3}
        ]}
      ]},
      {kind:'land'}
    ])
  };
}

function fixedProgram(goLeft) {
  const body = [];
  if (goLeft)
    body.push({kind:'move', direction:'left', distance_m:0.3});
  body.push({kind:'move', direction:'forward', distance_m:0.3});
  return {
    version:1, semantics:'webeeblocks-ast-v1',
    program:approach().concat([{kind:'repeat', count:3, body:body}, {kind:'land'}])
  };
}

function unrolledFreshProgram() {
  const program = approach();
  for (let row = 0; row < 3; ++row) {
    program.push(freshDecisionStep());
    program.push({kind:'move', direction:'forward', distance_m:0.3});
  }
  program.push({kind:'land'});
  return {version:1, semantics:'webeeblocks-ast-v1', program:program};
}

function rowBypassProgram() {
  return {
    version:1, semantics:'webeeblocks-ast-v1',
    program:[
      {kind:'takeoff', height_m:0.5},
      {kind:'move', direction:'left', distance_m:1.2},
      {kind:'move', direction:'left', distance_m:0.1},
      {kind:'move', direction:'forward', distance_m:1.2},
      {kind:'move', direction:'forward', distance_m:0.6},
      {kind:'move', direction:'left', distance_m:0.6},
      {kind:'land'}
    ]
  };
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
    const evaluation = {type:'mission-state-v1', oracle:'progression-reactive-v1'};
    await report('REACTIVE_PROBE_READY', {ready:backend.ready});

    const repeatedA = await executeCase(backend, evaluation, repeatedReactiveProgram(), 'achieved', 'REACTIVE_BOB_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'REACTIVE_BOB_RESET_FRESH');
    const repeatedB = await executeCase(backend, evaluation, repeatedReactiveProgram(), 'achieved', 'REACTIVE_OBO_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'REACTIVE_OBO_RESET_FRESH');
    const stale = await executeCase(backend, evaluation, oneMeasurementProgram(), 'not-achieved', 'REACTIVE_ONE_MEASUREMENT_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'REACTIVE_ONE_MEASUREMENT_RESET_FRESH');
    const fixedForward = await executeCase(backend, evaluation, fixedProgram(false), 'not-achieved', 'REACTIVE_FIXED_FORWARD_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'REACTIVE_FIXED_FORWARD_RESET_FRESH');
    const fixedLeft = await executeCase(backend, evaluation, fixedProgram(true), 'not-achieved', 'REACTIVE_FIXED_LEFT_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'REACTIVE_FIXED_LEFT_RESET_FRESH');
    const unrolledA = await executeCase(backend, evaluation, unrolledFreshProgram(), 'achieved', 'REACTIVE_UNROLLED_OBO_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'REACTIVE_UNROLLED_OBO_RESET_FRESH');
    const unrolledB = await executeCase(backend, evaluation, unrolledFreshProgram(), 'achieved', 'REACTIVE_UNROLLED_BOB_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'REACTIVE_UNROLLED_BOB_RESET_FRESH');
    const bypass = await executeCase(backend, evaluation, rowBypassProgram(), 'not-achieved', 'REACTIVE_BYPASS_NOT_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'REACTIVE_BYPASS_RESET_FRESH');
    await report('REACTIVE_MISSION_TEST_COMPLETE', {
      repeated_bob:repeatedA.status,
      repeated_obo:repeatedB.status,
      one_measurement:stale.status,
      fixed_forward:fixedForward.status,
      fixed_left:fixedLeft.status,
      unrolled_obo:unrolledA.status,
      unrolled_bob:unrolledB.status,
      bypass:bypass.status
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
