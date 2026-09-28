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
    throw new Error('unexpected outcome while priming Activity 8 attempt: ' + JSON.stringify(unexpected));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
  }
  await sleep(180);
  await backend.probeActivityMissionFailure(evaluation);
  try {
    const unexpected = await backend.readActivityOutcome(evaluation);
    throw new Error('failure probe synthesized Activity 8 outcome without irreversible failure: ' + JSON.stringify(unexpected));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await report('AUTONOMOUS_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE', {code:error.code});
  }
}

async function resetAndProveFresh(backend, evaluation, eventName) {
  await backend.resetSimulation();
  try {
    const stale = await backend.readActivityOutcome(evaluation);
    throw new Error('previous Activity 8 outcome survived reset: ' + JSON.stringify(stale));
  } catch (error) {
    if (!error || error.code !== 'OUTCOME_UNAVAILABLE')
      throw error;
    await sleep(180);
    await report(eventName, {code:error.code});
  }
}

const parcelVariable = {id:'activity8-parcel', name:'gabarit mémorisé'};
const alternateParcelVariable = {id:'activity8-parcel-alt', name:'référence de départ'};

function number(value) {
  return {kind:'number', value:value};
}

function range(direction) {
  return {kind:'range', direction:direction, unit:'m'};
}

function variableValue(variable) {
  return {kind:'variable_get', variable:variable || parcelVariable};
}

function clear(direction) {
  return {kind:'compare', op:'GT', left:range(direction), right:number(0.30)};
}

function smallFromStored() {
  return {kind:'compare', op:'GT', left:variableValue(parcelVariable), right:number(1.0)};
}

function smallFromAlternative() {
  return {kind:'compare', op:'LT', left:number(1.1), right:variableValue(alternateParcelVariable)};
}

function takeParcelAndReachRows(variable, storedExpression) {
  return [
    {kind:'takeoff', height_m:0.5},
    {kind:'move', direction:'right', distance_m:1.2},
    {kind:'move', direction:'right', distance_m:0.3},
    {kind:'set_variable', variable:variable, value:storedExpression},
    {kind:'move', direction:'forward', distance_m:0.2},
    {kind:'move', direction:'right', distance_m:1.0}
  ];
}

function reachRowsWithoutMemory() {
  return [
    {kind:'takeoff', height_m:0.5},
    {kind:'move', direction:'right', distance_m:1.2},
    {kind:'move', direction:'right', distance_m:0.3},
    {kind:'move', direction:'forward', distance_m:0.2},
    {kind:'move', direction:'right', distance_m:1.0}
  ];
}

function reactiveRow() {
  return {
    kind:'if',
    condition:clear('front'),
    then:[{kind:'move', direction:'forward', distance_m:0.3}],
    else:[
      {kind:'move', direction:'left', distance_m:0.25},
      {kind:'move', direction:'forward', distance_m:0.3},
      {kind:'move', direction:'right', distance_m:0.25}
    ]
  };
}

function forwardJunctionRoute() {
  return [{kind:'move', direction:'forward', distance_m:0.3}];
}

function leftJunctionRoute() {
  return [
    {kind:'move', direction:'left', distance_m:0.25},
    {kind:'move', direction:'forward', distance_m:0.3},
    {kind:'move', direction:'right', distance_m:0.25}
  ];
}

function rightJunctionRoute() {
  return [
    {kind:'move', direction:'right', distance_m:0.25},
    {kind:'move', direction:'forward', distance_m:0.3},
    {kind:'move', direction:'left', distance_m:0.25}
  ];
}

function frontLeftJunctionDecision() {
  return {
    kind:'if', condition:clear('front'), then:forwardJunctionRoute(), else:[
      {kind:'if', condition:clear('left'), then:leftJunctionRoute(), else:rightJunctionRoute()}
    ]
  };
}

function rightFirstJunctionDecision() {
  return {
    kind:'if', condition:clear('right'), then:rightJunctionRoute(), else:[
      {kind:'if', condition:clear('left'), then:leftJunctionRoute(), else:forwardJunctionRoute()}
    ]
  };
}

function frontOnlyJunctionDecision() {
  return {
    kind:'if', condition:clear('front'), then:forwardJunctionRoute(), else:leftJunctionRoute()
  };
}

function rememberedDelivery(condition) {
  return {
    kind:'if',
    condition:condition,
    then:[
      {kind:'move', direction:'left', distance_m:0.25},
      {kind:'move', direction:'forward', distance_m:0.3}
    ],
    else:[
      {kind:'move', direction:'right', distance_m:0.25},
      {kind:'move', direction:'forward', distance_m:0.3}
    ]
  };
}

function completeProgram(prefix, rows, junction, delivery) {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:prefix.concat(rows, [junction, delivery, {kind:'land'}])
  };
}

function integratedStrategy() {
  return completeProgram(
    takeParcelAndReachRows(parcelVariable, range('front')),
    [{kind:'repeat', count:2, body:[reactiveRow()]}],
    frontLeftJunctionDecision(),
    rememberedDelivery(smallFromStored())
  );
}

function alternativeStrategy() {
  const shiftedReference = {
    kind:'arithmetic',
    op:'ADD',
    left:range('front'),
    right:number(0.1)
  };
  return completeProgram(
    takeParcelAndReachRows(alternateParcelVariable, shiftedReference),
    [reactiveRow(), reactiveRow()],
    rightFirstJunctionDecision(),
    rememberedDelivery(smallFromAlternative())
  );
}

function fixedRouteShortcut() {
  return completeProgram(
    takeParcelAndReachRows(parcelVariable, range('front')),
    [
      {kind:'move', direction:'forward', distance_m:0.3},
      {kind:'move', direction:'forward', distance_m:0.3}
    ],
    forwardJunctionRoute()[0],
    rememberedDelivery(smallFromStored())
  );
}

function noMemoryShortcut() {
  return completeProgram(
    reachRowsWithoutMemory(),
    [{kind:'repeat', count:2, body:[reactiveRow()]}],
    frontLeftJunctionDecision(),
    {
      kind:'if',
      condition:{kind:'compare', op:'GT', left:number(1), right:number(0)},
      then:[
        {kind:'move', direction:'left', distance_m:0.25},
        {kind:'move', direction:'forward', distance_m:0.3}
      ],
      else:[]
    }
  );
}

function frontOnlyShortcut() {
  return completeProgram(
    takeParcelAndReachRows(parcelVariable, range('front')),
    [{kind:'repeat', count:2, body:[reactiveRow()]}],
    frontOnlyJunctionDecision(),
    rememberedDelivery(smallFromStored())
  );
}

function incompleteProgram() {
  return {
    version:1,
    semantics:'webeeblocks-ast-v1',
    program:takeParcelAndReachRows(parcelVariable, range('front')).concat([
      {kind:'repeat', count:2, body:[reactiveRow()]},
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
    const evaluation = {type:'mission-state-v1', oracle:'progression-autonomous-strategy-v1'};
    await report('AUTONOMOUS_PROBE_READY', {ready:backend.ready});
    await proveFailureProbeUnavailableWithoutFailure(backend, evaluation);

    const integrated = [];
    integrated.push(await executeCase(backend, evaluation, integratedStrategy(), 'achieved', 'AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_ACHIEVED', false));
    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_RESET_FRESH');
    integrated.push(await executeCase(backend, evaluation, integratedStrategy(), 'achieved', 'AUTONOMOUS_INTEGRATED_LARGE_EB_LEFT_ACHIEVED', false));
    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_INTEGRATED_LARGE_EB_LEFT_RESET_FRESH');
    integrated.push(await executeCase(backend, evaluation, integratedStrategy(), 'achieved', 'AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_ACHIEVED', false));
    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_RESET_FRESH');
    integrated.push(await executeCase(backend, evaluation, integratedStrategy(), 'achieved', 'AUTONOMOUS_INTEGRATED_LARGE_EE_FORWARD_ACHIEVED', false));

    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_FIXED_ROUTE_FRESH');
    const fixedRoute = await executeCase(backend, evaluation, fixedRouteShortcut(), 'not-achieved', 'AUTONOMOUS_FIXED_ROUTE_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_NO_MEMORY_FRESH');
    const noMemory = await executeCase(backend, evaluation, noMemoryShortcut(), 'not-achieved', 'AUTONOMOUS_NO_MEMORY_LARGE_NOT_ACHIEVED', false);

    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_FRONT_ONLY_FRESH');
    const frontOnly = await executeCase(backend, evaluation, frontOnlyShortcut(), 'not-achieved', 'AUTONOMOUS_FRONT_ONLY_RIGHT_NOT_ACHIEVED', true);

    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_INCOMPLETE_FRESH');
    const incomplete = await executeCase(backend, evaluation, incompleteProgram(), 'not-achieved', 'AUTONOMOUS_INCOMPLETE_NOT_ACHIEVED', false);

    const alternate = [];
    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_ALT_SMALL_BE_FORWARD_FRESH');
    alternate.push(await executeCase(backend, evaluation, alternativeStrategy(), 'achieved', 'AUTONOMOUS_ALT_SMALL_BE_FORWARD_ACHIEVED', false));
    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_ALT_LARGE_EB_LEFT_FRESH');
    alternate.push(await executeCase(backend, evaluation, alternativeStrategy(), 'achieved', 'AUTONOMOUS_ALT_LARGE_EB_LEFT_ACHIEVED', false));
    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_ALT_SMALL_BB_RIGHT_FRESH');
    alternate.push(await executeCase(backend, evaluation, alternativeStrategy(), 'achieved', 'AUTONOMOUS_ALT_SMALL_BB_RIGHT_ACHIEVED', false));
    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_ALT_LARGE_EE_FORWARD_FRESH');
    alternate.push(await executeCase(backend, evaluation, alternativeStrategy(), 'achieved', 'AUTONOMOUS_ALT_LARGE_EE_FORWARD_ACHIEVED', false));

    await resetAndProveFresh(backend, evaluation, 'AUTONOMOUS_FINAL_RESET_FRESH');
    await report('AUTONOMOUS_MISSION_TEST_COMPLETE', {
      integrated:integrated.map(result => result.status),
      fixed_route:fixedRoute.status,
      no_memory:noMemory.status,
      front_only:frontOnly.status,
      incomplete:incomplete.status,
      alternate:alternate.map(result => result.status)
    });
  } catch (error) {
    await report('ERROR', {message:error && error.message ? error.message : String(error), code:error && error.code ? error.code : null});
  }
})();
