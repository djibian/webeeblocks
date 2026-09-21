'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');

const mainSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');
assert.match(mainSource,
  /runtimeRunning = false;\s*runtimeTerminal = true;\s*updateRuntimeActions\(\);\s*var missionOutcome = await WebeeBlocksRuntimeOutcome\.evaluateMission\(runtimeProfile, runtimeBackend\);/,
  'Runtime-v2 completion must evaluate the active declarative mission only after program execution becomes terminal');
assert.match(mainSource,
  /if \(missionOutcome\)\s*setRuntimeStatus\(missionOutcome\.state, missionOutcome\.detail\);\s*else\s*setRuntimeStatus\('TERMINÉ', 'Programme exécuté'\);/,
  'mission outcome presentation must preserve the existing non-mission completion path');

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

  console.log('PASS backend-neutral activity mission outcome contract and Runtime-v2 completion wiring');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
