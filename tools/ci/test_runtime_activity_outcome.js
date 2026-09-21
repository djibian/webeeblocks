'use strict';
const assert = require('assert');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');

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

  console.log('PASS backend-neutral activity mission outcome contract');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
