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
    throw new Error('unexpected outcome while priming Activity 7 attempt: ' + JSON.stringify(unexpected));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
  }
  await sleep(180);
  await backend.probeActivityMissionFailure(evaluation);
  try {
    const unexpected = await backend.readActivityOutcome(evaluation);
    throw new Error('failure probe synthesized outcome without sorting failure: ' + JSON.stringify(unexpected));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await report('MEMORY_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE', {code:error.code});
  }
}

async function resetAndProveFresh(backend, evaluation, eventName) {
  await backend.resetSimulation();
  try {
    const stale = await backend.readActivityOutcome(evaluation);
    throw new Error('previous Activity 7 outcome survived reset: ' + JSON.stringify(stale));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await sleep(180);
    await report(eventName, {code:error.code});
  }
}

const parcelVariable = {id:'parcel-reference', name:'gabarit mémorisé'};

function number(value) {
  return {kind:'number', value:value};
}

function rangeFront() {
  return {kind:'range', direction:'front', unit:'m'};
}

function variableValue() {
  return {kind:'variable_get', variable:parcelVariable};
}

function smallFromStored(alternate) {
  if (alternate)
    return {kind:'compare', op:'LT', left:number(1.0), right:variableValue()};
  return {kind:'compare', op:'GT', left:variableValue(), right:number(1.0)};
}

function smallFromFreshRange() {
  return {kind:'compare', op:'GT', left:rangeFront(), right:number(1.0)};
}

function approachAndMeasure(valueExpression) {
  return [
    {kind:'takeoff', height_m:0.5},
    {kind:'move', direction:'right', distance_m:1.2},
    {kind:'move', direction:'right', distance_m:0.3},
    {kind:'set_variable', variable:parcelVariable, value:valueExpression},
    {kind:'move', direction:'forward', distance_m:0.65}
  ];
}

function firstSort(condition) {
  return {
    kind:'if',
    condition:condition,
    then:[
      {kind:'move', direction:'left', distance_m:0.25},
      {kind:'move', direction:'forward', distance_m:0.30},
      {kind:'move', direction:'right', distance_m:0.25}
    ],
    else:[
      {kind:'move', direction:'right', distance_m:0.25},
      {kind:'move', direction:'forward', distance_m:0.30},
      {kind:'move', direction:'left', distance_m:0.25}
    ]
  };
}

function secondSort(condition) {
  return {
    kind:'if',
    condition:condition,
    then:[
      {kind:'move', direction:'right', distance_m:0.25},
      {kind:'move', direction:'forward', distance_m:0.30},
      {kind:'move', direction:'left', distance_m:0.25}
    ],
    else:[
      {kind:'move', direction:'left', distance_m:0.25},
      {kind:'move', direction:'forward', distance_m:0.30},
      {kind:'move', direction:'right', distance_m:0.25}
    ]
  };
}

function rememberedProgram(alternate) {
  const storedCondition1 = smallFromStored(alternate);
  const storedCondition2 = smallFromStored(alternate);
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:approachAndMeasure(rangeFront()).concat([
      firstSort(storedCondition1),
      {kind:'move', direction:'forward', distance_m:0.25},
      secondSort(storedCondition2),
      {kind:'move', direction:'forward', distance_m:0.15},
      {kind:'land'}
    ])
  };
}

function lateRereadProgram() {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:approachAndMeasure(rangeFront()).concat([
      firstSort(smallFromFreshRange()),
      {kind:'move', direction:'forward', distance_m:0.25},
      secondSort(smallFromFreshRange()),
      {kind:'move', direction:'forward', distance_m:0.15},
      {kind:'land'}
    ])
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
  const outcome = await waitForOutcome(backend, evaluation, expected, 10000);
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
    const evaluation = {type:'mission-state-v1', oracle:'progression-memory-v1'};
    await report('MEMORY_PROBE_READY', {ready:backend.ready});
    await proveFailureProbeUnavailableWithoutFailure(backend, evaluation);

    const storedSmall = await executeCase(
      backend, evaluation, rememberedProgram(false), 'achieved', 'MEMORY_STORED_SMALL_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'MEMORY_STORED_SMALL_RESET_FRESH');
    const storedLarge = await executeCase(
      backend, evaluation, rememberedProgram(false), 'achieved', 'MEMORY_STORED_LARGE_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'MEMORY_REREAD_SMALL_FRESH');
    const rereadSmall = await executeCase(
      backend, evaluation, lateRereadProgram(), 'achieved', 'MEMORY_REREAD_SMALL_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'MEMORY_REREAD_LARGE_FRESH');
    const rereadLarge = await executeCase(
      backend, evaluation, lateRereadProgram(), 'not-achieved', 'MEMORY_REREAD_LARGE_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'MEMORY_ALT_SMALL_FRESH');
    const altSmall = await executeCase(
      backend, evaluation, rememberedProgram(true), 'achieved', 'MEMORY_ALT_SMALL_ACHIEVED', false);
    await resetAndProveFresh(backend, evaluation, 'MEMORY_ALT_SMALL_RESET_FRESH');
    const altLarge = await executeCase(
      backend, evaluation, rememberedProgram(true), 'achieved', 'MEMORY_ALT_LARGE_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'MEMORY_FINAL_RESET_FRESH');
    await report('MEMORY_MISSION_TEST_COMPLETE', {
      stored_small:storedSmall.status,
      stored_large:storedLarge.status,
      reread_small:rereadSmall.status,
      reread_large:rereadLarge.status,
      alternate_small:altSmall.status,
      alternate_large:altLarge.status
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
