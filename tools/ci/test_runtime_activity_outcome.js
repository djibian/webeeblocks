'use strict';
const assert = require('assert');
const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');

const mainSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');
const brokerRuntimeSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/file_broker_runtime.cpp'), 'utf8');
const interposeSource = fs.readFileSync(path.resolve(__dirname, '../../controllers/crazyflie_runtime_v2/file_broker_interpose.h'), 'utf8');
assert.match(mainSource,
  /runtimeRunning = false;\s*runtimeTerminal = true;\s*var missionOutcome = await WebeeBlocksRuntimeOutcome\.evaluateMission\(runtimeProfile, runtimeBackend\);/,
  'Runtime-v2 completion must become terminal before mission evaluation without reopening actions while the outcome is pending');
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

function proveScenarioMissionObjectiveSeparation() {
  const catalog = {takeoff:{}};
  const mission = 'Dépose le colis dans la zone d’arrivée.';
  const objective = 'Construire une séquence ordonnée d’actions.';
  const profile = {
    id:'scenario-model-v1',
    world:'worlds/runtime.wbt',
    brief:{visible:true,title:'Mission',mission},
    pedagogy:{objective},
    toolbox:['takeoff'],
    parameterBounds:{},
    fieldOptions:{},
    hardware:[],
    timer:{enabled:false},
    evaluation:{type:'mission-state-v1',oracle:'scenario-model-v1'},
    runtime:{allowedStatementKinds:['takeoff'],rangeDirections:[],moveDirections:[],verticalDirections:[]}
  };

  assert.strictEqual(Profiles.validateProfile(profile, catalog), true,
    'a redesigned activity must accept a distinct student mission plus internal pedagogical objective');
  const resolved = Profiles.resolveProfile(profile, catalog);
  assert.strictEqual(resolved.brief.mission, mission);
  assert.strictEqual(resolved.pedagogy.objective, objective);
  assert.notStrictEqual(resolved.brief.mission, resolved.pedagogy.objective,
    'student mission must not collapse into the internal pedagogical objective');
  assert.strictEqual(resolved.brief.goal, mission,
    'legacy Robot Window presentation must receive only the student mission compatibility projection');
  assert.strictEqual(profile.brief.goal, undefined,
    'resolving a redesigned profile must not mutate the declarative source by inserting a legacy goal');

  const missingObjective = JSON.parse(JSON.stringify(profile));
  delete missingObjective.pedagogy;
  assert.throws(() => Profiles.validateProfile(missingObjective, catalog), /pedagogy must be an object/,
    'a student mission without a separate internal objective must fail closed');

  const mismatchedProjection = JSON.parse(JSON.stringify(profile));
  mismatchedProjection.brief.goal = 'Objectif interne exposé par erreur';
  assert.throws(() => Profiles.validateProfile(mismatchedProjection, catalog), /brief.goal must match brief.mission/,
    'a legacy presentation field must not diverge from the student mission');

  const legacy = JSON.parse(JSON.stringify(profile));
  delete legacy.brief.mission;
  delete legacy.pedagogy;
  legacy.brief.goal = 'Exercice existant';
  legacy.evaluation = {type:'training-objective'};
  assert.strictEqual(Profiles.validateProfile(legacy, catalog), true,
    'legacy activity profiles must remain valid until redesigned one by one');
  assert.strictEqual(Profiles.resolveProfile(legacy, catalog).brief.goal, 'Exercice existant');
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

  const stale = backend.readActivityOutcome(evaluation);
  assert.strictEqual(sent[1], 'WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 OUTCOME world-observation-v1');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR STALE_OUTCOME');
  await assert.rejects(stale, error => error && error.code === 'STALE_OUTCOME');

  const invalidState = backend.readActivityOutcome(evaluation);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 STATE mystery');
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

async function provePendingMissionOutcomeKeepsActionsGated() {
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

  context.runtimeProfile = {evaluation:{type:'mission-state-v1', oracle:'world-observation-v1'}};
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
  assert.strictEqual(element('runtimeState').textContent, 'EN VOL', 'public runtime state must stay in the locked execution state until mission outcome settles');
  assert.strictEqual(element('resetSimulation').disabled, true, 'Reset must stay disabled while the mission outcome provider is pending');
  assert.strictEqual(element('submit').textContent, 'Arrêter le vol', 'primary action must not reopen as Lancer while mission outcome is pending');

  await element('submit').click();
  await element('resetSimulation').click();
  assert.strictEqual(executeCalls, 1, 'pending mission outcome allowed a second program execution');
  assert.strictEqual(resetCalls, 0, 'pending mission outcome allowed a simulation reset');

  pendingOutcome.resolve({status:'achieved'});
  await run;
  assert.strictEqual(element('runtimeState').textContent, 'MISSION RÉUSSIE');
  assert.strictEqual(element('runtimeDetail').textContent, 'Mission accomplie');
  assert.strictEqual(element('resetSimulation').disabled, false, 'Reset should reopen only after the mission outcome is presented');
}

function proveRealWebotsOutcomeFreshness() {
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
  assert.deepStrictEqual(Outcome.classifyMission('not-achieved'), {
    status:'not-achieved', state:'MISSION NON RÉUSSIE', detail:'Mission non accomplie'
  });
  assert.deepStrictEqual(Outcome.classifyMission({status:'interrupted'}), {
    status:'interrupted', state:'MISSION INTERROMPUE', detail:'Mission interrompue'
  });

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

  proveScenarioMissionObjectiveSeparation();
  proveOverlappingResetFreshnessContract();
  await proveWwiOutcomeTransport();
  await provePendingMissionOutcomeKeepsActionsGated();
  proveRealWebotsOutcomeFreshness();
  console.log('PASS backend-neutral activity mission outcome contract, scenario mission/objective separation, overlapping Reset freshness, attempt-scoped live-world transport, real-Webots freshness, Runtime-v2 completion wiring, and pending-outcome action gating');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
