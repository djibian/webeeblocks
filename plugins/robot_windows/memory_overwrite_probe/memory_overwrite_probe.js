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
    throw new Error('previous Activity 7 outcome survived reset: ' + JSON.stringify(stale));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await sleep(180);
    await report(eventName, {code:error.code});
  }
}

const parcelVariable = {id:'parcel-reference-overwrite', name:'gabarit retenu'};
function number(value) { return {kind:'number', value:value}; }
function rangeFront() { return {kind:'range', direction:'front', unit:'m'}; }
function variableValue() { return {kind:'variable_get', variable:parcelVariable}; }
function smallFromStored() {
  return {kind:'compare', op:'GT', left:variableValue(), right:number(1.0)};
}
function smallFromFreshRange() {
  return {kind:'compare', op:'GT', left:rangeFront(), right:number(1.0)};
}
function approachAndMeasure() {
  return [
    {kind:'takeoff', height_m:0.5},
    {kind:'move', direction:'right', distance_m:1.2},
    {kind:'move', direction:'right', distance_m:0.3},
    {kind:'set_variable', variable:parcelVariable, value:rangeFront()},
    {kind:'move', direction:'forward', distance_m:0.65}
  ];
}
function firstSort(condition) {
  return {
    kind:'if', condition:condition,
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
    kind:'if', condition:condition,
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
function overwrittenBeforeSecondDecisionProgram() {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:approachAndMeasure().concat([
      firstSort(smallFromStored()),
      {kind:'move', direction:'forward', distance_m:0.25},
      {kind:'set_variable', variable:parcelVariable, value:number(2.0)},
      secondSort(smallFromStored()),
      {kind:'move', direction:'forward', distance_m:0.15},
      {kind:'land'}
    ])
  };
}
function collisionProgram() {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:[
      {kind:'takeoff', height_m:0.5},
      {kind:'move', direction:'right', distance_m:0.6},
      {kind:'move', direction:'forward', distance_m:1.2},
      {kind:'move', direction:'forward', distance_m:0.6}
    ]
  };
}
function lateralRereadProgram() {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:[
      {kind:'takeoff', height_m:0.5},
      {kind:'move', direction:'right', distance_m:1.2},
      {kind:'move', direction:'right', distance_m:0.3},
      {kind:'move', direction:'left', distance_m:0.2},
      {kind:'move', direction:'forward', distance_m:0.65},
      {kind:'set_variable', variable:parcelVariable, value:rangeFront()},
      {kind:'move', direction:'right', distance_m:0.2},
      firstSort(smallFromStored()),
      {kind:'move', direction:'forward', distance_m:0.25},
      secondSort(smallFromStored()),
      {kind:'move', direction:'forward', distance_m:0.15},
      {kind:'land'}
    ]
  };
}
function wrongFinalBayProgram() {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:approachAndMeasure().concat([
      firstSort(smallFromStored()),
      {kind:'move', direction:'forward', distance_m:0.25},
      secondSort(smallFromStored()),
      {kind:'move', direction:'right', distance_m:0.25},
      {kind:'land'}
    ])
  };
}

async function executeNegativeCase(backend, evaluation, program, eventName) {
  let runtimeError = null;
  try {
    await WebeeBlocksInterpreter.run(program, backend);
  } catch (error) {
    runtimeError = error;
  }
  if (runtimeError) {
    if (runtimeError.code !== 'UNSAFE_OR_TIMEOUT')
      throw runtimeError;
    await backend.probeActivityMissionFailure(evaluation);
  } else {
    await backend.completeActivityMission(evaluation);
  }
  const outcome = await waitForOutcome(backend, evaluation, 'not-achieved', 10000);
  await report(eventName,
    runtimeError ? {status:outcome.status, runtime_code:runtimeError.code} : outcome);
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
    await report('MEMORY_OVERWRITE_PROBE_READY', {ready:backend.ready});

    await resetAndProveFresh(backend, evaluation, 'MEMORY_OVERWRITE_LARGE_FRESH');
    const overwritten = await executeNegativeCase(
      backend, evaluation, overwrittenBeforeSecondDecisionProgram(), 'MEMORY_OVERWRITE_LARGE_NOT_ACHIEVED');

    await resetAndProveFresh(backend, evaluation, 'MEMORY_COLLISION_FRESH');
    const collision = await executeNegativeCase(
      backend, evaluation, collisionProgram(), 'MEMORY_COLLISION_NOT_ACHIEVED');

    await resetAndProveFresh(backend, evaluation, 'MEMORY_LATERAL_REREAD_LARGE_FRESH');
    const lateralReread = await executeNegativeCase(
      backend, evaluation, lateralRereadProgram(), 'MEMORY_LATERAL_REREAD_LARGE_NOT_ACHIEVED');

    await resetAndProveFresh(backend, evaluation, 'MEMORY_FINAL_BAY_FRESH');
    const finalBay = await executeNegativeCase(
      backend, evaluation, wrongFinalBayProgram(), 'MEMORY_FINAL_BAY_NOT_ACHIEVED');

    await report('MEMORY_OVERWRITE_TEST_COMPLETE', {
      overwritten_large:overwritten.status,
      collision:collision.status,
      lateral_reread_large:lateralReread.status,
      wrong_final_bay:finalBay.status
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
