'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');

const mainSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');
assert.match(mainSource,
  /runtimeRunning = false;\s*runtimeTerminal = true;\s*var missionOutcome = await WebeeBlocksRuntimeOutcome\.evaluateMission\(runtimeProfile, runtimeBackend\);/,
  'Runtime-v2 completion must become terminal before mission evaluation without reopening actions while the outcome is pending');
assert.match(mainSource,
  /if \(missionOutcome\)\s*setRuntimeStatus\(missionOutcome\.state, missionOutcome\.detail\);\s*else\s*setRuntimeStatus\('TERMINÉ', 'Programme exécuté'\);/,
  'mission outcome presentation must preserve the existing non-mission completion path');

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

  await provePendingMissionOutcomeKeepsActionsGated();
  console.log('PASS backend-neutral activity mission outcome contract, Runtime-v2 completion wiring, and pending-outcome action gating');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
