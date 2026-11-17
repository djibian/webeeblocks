'use strict';
const assert = require('assert');
const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const proveMissionFailure = require('./test_runtime_mission_failure.js');

const mainSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');
const brokerRuntimeSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/file_broker_runtime.cpp'), 'utf8');
const interposeSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/file_broker_interpose.h'), 'utf8');
assert.match(mainSource,
  /runtimeRunning = false;\s*runtimeTerminal = true;\s*runtimeOutcomePending = true;\s*updateRuntimeActions\(\);\s*var missionOutcome = await WebeeBlocksRuntimeOutcome\.evaluateMission\(runtimeProfile, runtimeBackend\);/,
  'Runtime-v2 completion must stay terminal and hold the UI interlock until mission evaluation settles');
assert.match(mainSource,
  /if \(missionOutcome\)\s*setRuntimeStatus\(missionOutcome\.state, missionOutcome\.detail\);\s*else\s*setRuntimeStatus\('TERMINÉ', 'Programme exécuté'\);/,
  'mission outcome presentation must preserve the existing non-mission completion path');
assert.match(interposeSource,
  /#define wb_robot_wwi_send webeeblocks_file_broker_send/,
  'Runtime-v2 controller responses must pass through the attempt-freshness transport interposer');
assert.match(brokerRuntimeSource,
  /extern "C" void webeeblocks_file_broker_send\(const char \*data, int size\)/,
  'the send interposer must preserve the exact Webots WWI transport signature');
assert.match(brokerRuntimeSource,
  /WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1/,
  'live world channel must publish an attempt identity');
assert.match(brokerRuntimeSource,
  /WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%63s status=%31s/,
  'live world provider must consume attempt-bound oracle/status evidence');
assert.match(brokerRuntimeSource,
  /attempt != gActivityAttempt[\s\S]*STALE_OUTCOME/,
  'provider must reject terminal evidence from a previous simulation attempt');
assert.match(brokerRuntimeSource,
  /std::strcmp\(payload, "OK"\) == 0[\s\S]*(?:\+\+gActivityAttempt|gActivityAttempt = 0)[\s\S]*publishActivityAttempt\(\)/,
  'a successful Reset must rotate the attempt identity and clear prior terminal evidence before the UI resumes');
assert.match(brokerRuntimeSource,
  /if \(resetRequestId\(message, &resetId\) && gPendingResetRequest < 1\)\s*gPendingResetRequest = resetId;/,
  'a later Reset request must not replace the identity of the already in-flight Reset');
assert.match(brokerRuntimeSource,
  /std::sscanf\(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s %1s", &parsedId, command, extra\) != 2[\s\S]*std::strcmp\(command, "RESET"\) != 0/,
  'attempt rotation must be armed only by an exact RESET command token with no trailing arguments');
assert.doesNotMatch(brokerRuntimeSource,
  /WEBEEBLOCKS_RUNTIME_V2 REQUEST %d RESET %1s/,
  'Reset recognition must not rely on sscanf assignment count before checking the RESET literal');

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return {promise, resolve};
}

async function until(predicate, label) {
  const start = Date.now();
  while (Date.now() - start < 1000) {
    if (predicate()) return;
    await new Promise(r => setTimeout(r, 0));
  }
  throw new Error('timeout ' + label);
}

function proveExactResetClassificationContract() {
  let attempt = 1;
  let pendingReset = -1;

  function observeRequest(message) {
    const match = String(message).match(/^WEBEEBLOCKS_RUNTIME_V2 REQUEST (\d+) ([A-Z]+)$/);
    if (!match || match[2] !== 'RESET' || pendingReset >= 1)
      return;
    pendingReset = Number(match[1]);
  }

  function observeRuntimeResponse(id, payload) {
    if (pendingReset < 1 || id !== pendingReset)
      return;
    if (payload === 'OK')
      attempt += 1;
    pendingReset = -1;
  }

  const ordinary = [
    ['WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 TAKEOFF 0.5', 1],
    ['WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 MOVE forward 0.1', 2],
    ['WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 LAND', 3]
  ];
  ordinary.forEach(([request, id]) => {
    observeRequest(request);
    assert.strictEqual(pendingReset, -1,
      'ordinary TAKEOFF/MOVE/LAND request must not arm activity-attempt rotation');
    observeRuntimeResponse(id, 'OK');
    assert.strictEqual(attempt, 1,
      'ordinary successful action must not rotate the activity attempt');
  });

  observeRequest('WEBEEBLOCKS_RUNTIME_V2 REQUEST 4 RESET extra');
  assert.strictEqual(pendingReset, -1,
    'RESET with trailing arguments must fail closed as an attempt-rotation trigger');

  observeRequest('WEBEEBLOCKS_RUNTIME_V2 REQUEST 10 RESET');
  assert.strictEqual(pendingReset, 10);
  observeRuntimeResponse(10, 'ERR RESET_TIMEOUT');
  assert.strictEqual(attempt, 1,
    'failed exact Reset must not rotate the activity attempt');
  assert.strictEqual(pendingReset, -1,
    'failed exact Reset must release its pending identity');

  observeRequest('WEBEEBLOCKS_RUNTIME_V2 REQUEST 11 RESET');
  observeRuntimeResponse(11, 'OK');
  assert.strictEqual(attempt, 2,
    'successful exact Reset must rotate the activity attempt exactly once');
  assert.strictEqual(pendingReset, -1);

  observeRuntimeResponse(11, 'OK');
  assert.strictEqual(attempt, 2,
    'duplicate or unrelated responses after Reset completion must not rotate again');
}

function proveOverlappingResetFreshnessContract() {
  let attempt = 1;
  let pendingReset = -1;

  function observeResetRequest(id) {
    if (id >= 1 && pendingReset < 1)
      pendingReset = id;
  }

  function observeRuntimeResponse(id, payload) {
    if (pendingReset < 1 || id !== pendingReset)
      return;
    if (payload === 'OK')
      attempt += 1;
    pendingReset = -1;
  }

  observeResetRequest(10);
  observeResetRequest(11);
  assert.strictEqual(pendingReset, 10,
    'RESET B must not overwrite RESET A while A is still in flight');

  observeRuntimeResponse(11, 'ERR BUSY');
  assert.strictEqual(pendingReset, 10,
    'RESET B BUSY must not clear the pending identity of RESET A');
  assert.strictEqual(attempt, 1,
    'a rejected overlapping Reset must not rotate the attempt identity');

  observeRuntimeResponse(10, 'OK');
  assert.strictEqual(pendingReset, -1,
    'RESET A terminal response must release the pending Reset slot');
  assert.strictEqual(attempt, 2,
    'RESET A OK must rotate the attempt identity after an overlapping RESET B BUSY');
}

async function proveWwiOutcomeTransport() {
  const sent = [];
  const backend = new WwiBackend({send: message => sent.push(String(message))}, {timeoutMs:1000});
  const evaluation = {type:'mission-state-v1', oracle:'world-observation-v1'};

  const achieved = backend.readActivityOutcome(evaluation);
  assert.strictEqual(sent[0], 'WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 OUTCOME world-observation-v1');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 STATE achieved');
  assert.deepStrictEqual(await achieved, {status:'achieved'});

  const negativeReason = backend.readActivityOutcome(evaluation);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 STATE not-achieved reason=low-outside-zone');
  assert.deepStrictEqual(await negativeReason, {status:'not-achieved', reason:'low-outside-zone'});
  const stale = backend.readActivityOutcome(evaluation);
  assert.strictEqual(sent[2], 'WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 OUTCOME world-observation-v1');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 ERR STALE_OUTCOME');
  await assert.rejects(stale, error => error && error.code === 'STALE_OUTCOME');

  const invalidState = backend.readActivityOutcome(evaluation);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 STATE mystery');
  await assert.rejects(invalidState, /invalid activity outcome state/,
    'unknown live-world terminal states must fail closed at the transport boundary');

  const beforeInvalidOracle = sent.length;
  await assert.rejects(
    () => backend.readActivityOutcome({type:'mission-state-v1', oracle:'bad oracle'}),
    /invalid activity outcome oracle/,
    'oracle identifiers must not be able to inject WWI protocol tokens'
  );
  assert.strictEqual(sent.length, beforeInvalidOracle, 'invalid oracle unexpectedly emitted a WWI request');
}

async function provePendingMissionOutcomeKeepsActionsGated(runtime, expectedMaxSteps, terminal) {
  const elements = {};
  function element(id) {
    if (!elements[id]) {
      elements[id] = {
        id, disabled:false, hidden:false, checked:false, textContent:'', onclick:null,
        setAttribute(){}, addEventListener(){},
        click() {
          if (this.disabled || typeof this.onclick !== 'function') return undefined;
          return this.onclick();
        }
      };
    }
    return elements[id];
  }

  const pendingOutcome = deferred();
  let executeCalls = 0;
  let outcomeReads = 0;
  let resetCalls = 0;
  const context = {
    console:{log(){},error(){}},
    Blockly:{Theme:{defineTheme(){return{};}},Themes:{Classic:{}},Events:{UI:'ui',BLOCK_MOVE:'move',BLOCK_CREATE:'create'},Blocks:{}},
    document:{
      currentScript:{src:'https://example.invalid/main.js'},
      getElementById:element,
      body:{dataset:{}},
      createElement(){return{setAttribute(){},appendChild(){}};}
    },
    window:{dispatchEvent(){},addEventListener(){}},
    CustomEvent:function(type,init){this.type=type;this.detail=init&&init.detail;},
    WebeeBlocksRuntimeOutcome:Outcome,
    WebeeBlocksActivityContract:{
      async execute(profile, workspace, compiler, interpreter, backend, options) {
        executeCalls += 1;
        assert.strictEqual(options.maxSteps, expectedMaxSteps,
          'execution must receive the configured step budget or its default');
        options.onAst({version:1, semantics:'webeeblocks-ast-v1', program:[]});
      },
      applyFieldBounds(){}
    },
    WebeeBlocksSemanticAst:{},
    WebeeBlocksInterpreter:{},
    WebeeBlocksExecutionObserver:{create(){return null;}},
    WebeeBlocksActivities:{BLOCK_CATALOG:{}},
    WebeeBlocksActivityProfiles:{},
    WebeeBlocksWwiBackend:function(){},
    URL,
    setTimeout, clearTimeout, Promise
  };
  vm.createContext(context);
  vm.runInContext(mainSource, context, {filename:'blockly_v2/main.js'});

  context.runtimeProfile = {runtime, evaluation:{type:'mission-state-v1',
    oracle:terminal ? terminal.oracle : 'world-observation-v1'}};
  context.workspace = {};
  context.runtimeBackend = {
    ready:true,
    capabilities:{simulationDebug:false, simulationReset:true, simulationStop:true},
    async readActivityOutcome() {
      outcomeReads += 1;
      return pendingOutcome.promise;
    },
    async resetSimulation() { resetCalls += 1; }
  };
  element('stepMode').checked = false;
  element('resetSimulation').onclick = context.resetSimulation;
  context.updateRuntimeActions();

  const run = context.runProgram();
  await until(() => outcomeReads === 1, 'mission outcome read');

  assert.strictEqual(context.runtimeRunning, false, 'program execution must be finished while the mission result is pending');
  assert.strictEqual(context.runtimeTerminal, true, 'pending mission evaluation must remain terminal to block a second run');
  assert.strictEqual(element('runtimeState').textContent, 'EXÉCUTION', 'public runtime state must stay in the locked execution state until mission outcome settles');
  assert.strictEqual(element('runtimeDetail').textContent, 'Programme en cours — vol non confirmé', 'starting the interpreter must not claim flight');
  assert.strictEqual(element('resetSimulation').disabled, true, 'Reset must stay disabled while the mission outcome provider is pending');
  assert.strictEqual(element('submit').textContent, 'Arrêter le vol', 'primary action must not reopen as Lancer while mission outcome is pending');
  assert.strictEqual(element('submit').disabled, true,
    'primary stop must remain disabled until the mission outcome settles, even when simulationStop is supported');

  await element('submit').click();
  await element('resetSimulation').click();
  assert.strictEqual(executeCalls, 1, 'pending mission outcome allowed a second program execution');
  assert.strictEqual(resetCalls, 0, 'pending mission outcome allowed a simulation reset');

  pendingOutcome.resolve(terminal ? terminal.raw : {status:'achieved'});
  await run;
  assert.strictEqual(element('runtimeState').textContent,
    terminal ? terminal.state : 'MISSION RÉUSSIE',
    'actual product main.js must display the exact native-oracle terminal state');
  assert.strictEqual(element('runtimeDetail').textContent,
    terminal ? terminal.detail : 'Mission accomplie',
    'actual product main.js must display the exact authorized causal reason');
  assert.strictEqual(element('resetSimulation').disabled, false, 'Reset should reopen only after the mission outcome is presented');
}

function proveRealWebotsOutcomeFreshness() {
  // The full native proof moves to three mandatory isolated R2025a jobs.
  // Fail closed for unknown modes and never permit an ordinary standalone call
  // or another CI job to silently omit its expected native proof.
  const mode = process.env.WEBEEBLOCKS_CI_NATIVE_PROGRESSION_MODE;
  if (mode !== undefined) {
    assert.strictEqual(mode, 'sharded', 'unknown native progression qualification mode');
    assert.strictEqual(process.env.GITHUB_ACTIONS, 'true', 'native sharding requires GitHub Actions');
    assert.strictEqual(process.env.GITHUB_JOB, 'runtime-v2-core', 'only the core job may delegate native progression');
    console.log('PASS unit outcome checks; real R2025a evidence is required from all three independent progression jobs');
    return;
  }
  const runner = path.resolve(__dirname, 'run_runtime_v2_outcome_probe.py');
  const result = childProcess.spawnSync('python3', [runner], {stdio:'inherit'});
  if (result.error)
    throw result.error;
  assert.strictEqual(result.status, 0,
    'real R2025a outcome provider did not prove attempt A terminal -> reset -> no stale terminal -> attempt B terminal');
}

(async function() {
  assert.strictEqual(Outcome.MISSION_EVALUATION_TYPE, 'mission-state-v1');
  assert.strictEqual(Outcome.supportsMissionEvaluation({type:'mission-state-v1'}), true);
  assert.strictEqual(Outcome.supportsMissionEvaluation({type:'training-objective'}), false);
  assert.strictEqual(await Outcome.evaluateMission({evaluation:{type:'training-objective'}}, {}), null,
    'legacy/non-mission evaluation must preserve current runtime completion behavior');

  const evaluation = {type:'mission-state-v1', oracle:'world-observation-v1'};
  let observedEvaluation = null;
  const achieved = await Outcome.evaluateMission({evaluation}, {
    async readActivityOutcome(request) {
      observedEvaluation = request;
      return {status:'achieved'};
    }
  });
  assert.strictEqual(observedEvaluation, evaluation,
    'backend must receive declarative evaluation, not a Blockly solution shape');
  assert.deepStrictEqual(achieved, {
    status:'achieved', state:'MISSION RÉUSSIE', detail:'Mission accomplie'
  });
  // A2 exposes only reasons attested by its native mission oracle.
  const a2 = {type:'mission-state-v1', oracle:'progression-altitude-3d-v1'};
  for (const [reason, french] of [
    ['obstacle-contact', 'Contact avec un obstacle'],
    ['unsafe-clearance', 'Hauteur ou passage dangereux près de l’obstacle'],
    ['early-finish', 'Parcours non franchi avant la fin du programme'],
    ['landing-timeout', 'Atterrissage non stabilisé dans le délai'],
    ['wrong-pad', 'Atterrissage hors du damier']
  ]) {
    assert.strictEqual(Outcome.classifyMission(
      {status:'not-achieved',reason}, a2).detail,
      'Mission non accomplie — ' + french);
    assert.strictEqual(Outcome.classifyMission(
      {status:'not-achieved',reason}, evaluation).detail,
      'Mission non accomplie', 'A2 reason must not leak to other oracles');
  }
  for (const bad of [
    {status:'not-achieved',reason:'forged'},
    {status:'not-achieved',reason:'__proto__'},
    {status:'achieved',reason:'wrong-pad'},
    {status:'interrupted',reason:'wrong-pad'}
  ]) {
    const got = Outcome.classifyMission(bad,a2);
    assert.strictEqual(got.detail, bad.status==='achieved'
      ? 'Mission accomplie' : bad.status==='interrupted'
      ? 'Mission interrompue' : 'Mission non accomplie');
  }
  const a4 = {type:'mission-state-v1', oracle:'progression-decision-h-v1'};
  assert.deepStrictEqual(Outcome.classifyMission(
    {status:'not-achieved',reason:'obstacle-contact'},a4), {
    status:'not-achieved',state:'MISSION NON RÉUSSIE',
    detail:'Mission non accomplie — Contact avec un obstacle'
  });
  for(const bad of [
    {status:'not-achieved',reason:'mystery'},
    {status:'achieved',reason:'obstacle-contact'}
  ]) {
    const got=Outcome.classifyMission(bad,a4);
    assert.strictEqual(got.detail,bad.status==='achieved'
      ? 'Mission accomplie' : 'Mission non accomplie');
  }
  assert.strictEqual(Outcome.classifyMission(
    {status:'not-achieved',reason:'obstacle-contact'},evaluation).detail,
    'Mission non accomplie','another oracle cannot claim A4 causes');
  assert.strictEqual(Outcome.classifyMission(
    {status:'not-achieved',reason:'unsafe-h-crossing'},a2).detail,
    'Mission non accomplie','A7-only reason must not leak into A2');
  assert.strictEqual(Outcome.classifyMission(
    {status:'not-achieved',reason:'route-incomplete'},a2).detail,
    'Mission non accomplie','A4/A7-only reason must not leak into A2');
  const a7={type:'mission-state-v1',oracle:'progression-mini-grand-prix-v1'};
  assert.deepStrictEqual(Outcome.classifyMission(
    {status:'not-achieved',reason:'unsafe-h-crossing'},a7), {
    status:'not-achieved',state:'MISSION NON RÉUSSIE',
    detail:'Mission non accomplie — Franchissement du H hors du passage autorisé'
  });
  for(const status of ['achieved','interrupted'])
    assert.strictEqual(Outcome.classifyMission(
      {status,reason:'unsafe-h-crossing'},a7).detail,
      status==='achieved'?'Mission accomplie':'Mission interrompue');
  for(const reason of ['unknown','__proto__',null])
    assert.strictEqual(Outcome.classifyMission(
      {status:'not-achieved',reason},a7).detail,'Mission non accomplie');
  assert.strictEqual(Outcome.classifyMission(
    {status:'not-achieved',reason:'unsafe-h-crossing'},a4).detail,
    'Mission non accomplie','A7 reason cannot impersonate A4');
  assert.deepStrictEqual(Outcome.classifyMission('not-achieved'), {
    status:'not-achieved', state:'MISSION NON RÉUSSIE', detail:'Mission non accomplie'
  });
  assert.deepStrictEqual(Outcome.classifyMission({status:'interrupted'}), {
    status:'interrupted', state:'MISSION INTERROMPUE', detail:'Mission interrompue'
  });
  // Object.freeze preserves inherited properties. Unknown states must never
  // become an undefined/success-looking product status through prototype
  // lookup, even for raw strings or malformed object-shaped responses.
  for (const invalid of [
    '__proto__','constructor','toString','hasOwnProperty','valueOf',
    'mystery',null,undefined,0,true,[],{},
    Object.create(null),new String('achieved')
  ]) {
    assert.throws(() => Outcome.classifyMission(invalid, a7),
      /invalid mission state/, 'invalid raw mission state must be refused');
    assert.throws(() => Outcome.classifyMission({status:invalid}, a7),
      /invalid mission state/, 'invalid field state must be refused');
  }
  let coerced = false;
  const forged = {toString(){coerced=true;return 'achieved';}};
  assert.throws(() => Outcome.classifyMission({status:forged}, a7),
    /invalid mission state/,
    'non-string status must not be coerced into a successful terminal state');
  assert.strictEqual(coerced,false, 'status validation must avoid untrusted coercion');
  // The three actual own statuses retain their exact public presentations.
  for (const valid of ['achieved','not-achieved','interrupted'])
    assert.deepStrictEqual(
      Outcome.classifyMission({status:valid},a7),Outcome.classifyMission(valid,a7)
    );

  await assert.rejects(
    () => Outcome.evaluateMission({evaluation}, {}),
    /backend mission outcome capability unavailable/,
    'mission evaluation must fail closed when no world-outcome provider exists'
  );
  await assert.rejects(
    () => Outcome.evaluateMission({evaluation}, {readActivityOutcome: async () => ({status:'mystery'})}),
    /invalid mission state/,
    'unknown mission states must not be presented as success'
  );

  proveExactResetClassificationContract();
  proveOverlappingResetFreshnessContract();
  await proveWwiOutcomeTransport();
  await require('./test_runtime_outcome_settling.js')();
  await provePendingMissionOutcomeKeepsActionsGated({maxSteps:20000}, 20000);
  await provePendingMissionOutcomeKeepsActionsGated({}, 1000);
  // Exercise the unmodified production runProgram / setRuntimeStatus path
  // using the exact A7 terminal token proved independently by motorized C
  // and WWI in the native Chrome witness. This DOM is Node VM-only; do not
  // mistake the unit test for a live Webots student-window qualification.
  await provePendingMissionOutcomeKeepsActionsGated({}, 1000, {
    oracle:'progression-mini-grand-prix-v1',
    raw:{status:'not-achieved',reason:'early-finish'},
    state:'MISSION NON RÉUSSIE',
    detail:'Mission non accomplie — Programme terminé avant la fin du parcours'
  });
  // A7-only causes must not be transposed onto a different oracle, and
  // A4-only causes must not leak into A7's reason catalogue.
  await provePendingMissionOutcomeKeepsActionsGated({}, 1000, {
    oracle:'progression-decision-h-v1',
    raw:{status:'not-achieved',reason:'unsafe-h-crossing'},
    state:'MISSION NON RÉUSSIE',
    detail:'Mission non accomplie'
  });
  await provePendingMissionOutcomeKeepsActionsGated({}, 1000, {
    oracle:'progression-mini-grand-prix-v1',
    raw:{status:'not-achieved',reason:'unsafe-clearance'},
    state:'MISSION NON RÉUSSIE',
    detail:'Mission non accomplie'
  });
  await proveMissionFailure();
  proveRealWebotsOutcomeFreshness();
  const nativeScope = process.env.WEBEEBLOCKS_CI_NATIVE_PROGRESSION_MODE === 'sharded'
    ? 'native Webots proofs delegated to required progression jobs'
    : 'real-Webots freshness';
  console.log('PASS backend-neutral activity mission outcome contract, exact Reset classification, overlapping Reset freshness, attempt-scoped live-world transport, ' + nativeScope + ', Runtime-v2 completion wiring, and pending-outcome action gating');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
