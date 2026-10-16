'use strict';
const assert = require('assert');
const Backend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const evaluation = {type:'mission-state-v1', oracle:'progression-sequence-v1'};

function transport(options, response) {
  const commands=[];
  let backend;
  backend=new Backend({send(message) {
    const parts=message.split(' '),id=parts[2],command=parts[3];
    commands.push(command);
    queueMicrotask(()=>backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+id+' '+response(command)));
  }},options);
  return {backend,commands};
}

module.exports = async function proveOutcomeSettling() {
  // The unchanged sequence oracle settles a negative at 1.5 Webots seconds.
  // At half real-time speed that valid result takes 3 wall seconds. All WWI
  // responses are immediate; this is not a lost/slow transport response.
  let completed;
  const slow=transport({timeoutMs:4000,outcomePollMs:10},command=>{
    if(command==='COMPLETE'){completed=Date.now();return 'OK';}
    const simulationSeconds=(Date.now()-completed)/2000;
    return simulationSeconds>=1.5?'STATE not-achieved':'ERR OUTCOME_UNAVAILABLE';
  });
  const result=await Outcome.evaluateMission({evaluation},slow.backend);
  assert.strictEqual(result.state,'MISSION NON RÉUSSIE');
  assert.strictEqual(slow.commands.filter(c=>c==='COMPLETE').length,1);
  assert(slow.commands.filter(c=>c==='OUTCOME').length>1);
  assert(slow.commands.every(c=>c==='COMPLETE'||c==='OUTCOME'));

  for(const code of ['STALE_OUTCOME','OUTCOME_MISMATCH','INVALID_OUTCOME']) {
    const bad=transport({timeoutMs:4000},c=>c==='COMPLETE'?'OK':'ERR '+code);
    await assert.rejects(()=>Outcome.evaluateMission({evaluation},bad.backend),e=>e.code===code);
    assert.deepStrictEqual(bad.commands,['COMPLETE','OUTCOME']);
  }
  // Permanent absence remains a technical failure, never an invented result.
  for(const options of [{timeoutMs:30,outcomePollMs:1},{timeoutMs:4000,outcomeSettleMs:30,outcomePollMs:1}]) {
    const missing=transport(options,c=>c==='COMPLETE'?'OK':'ERR OUTCOME_UNAVAILABLE');
    const start=Date.now();
    await assert.rejects(()=>Outcome.evaluateMission({evaluation},missing.backend),e=>e.code==='OUTCOME_UNAVAILABLE');
    assert(Date.now()-start<1000,'outcome observation must remain bounded');
    assert.strictEqual(missing.commands.filter(c=>c==='COMPLETE').length,1);
  }
  const fresh=transport({timeoutMs:4000},()=> 'ERR OUTCOME_UNAVAILABLE');
  await assert.rejects(()=>fresh.backend.readActivityOutcome(evaluation),e=>e.code==='OUTCOME_UNAVAILABLE');
  assert.deepStrictEqual(fresh.commands,['OUTCOME'],'no polling without causal completion');
  console.log('PASS delayed native negative outcome, bounded absence, exact-oracle errors and one causal completion');
};
if(require.main===module)module.exports().catch(e=>{console.error(e);process.exitCode=1;});
