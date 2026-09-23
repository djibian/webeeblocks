'use strict';
const assert = require('assert');
const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const mainSource = fs.readFileSync(path.resolve(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');

function harness(options = {}) {
  const elements = {};
  const events = [];
  const sent = [];
  let response = options.response || 'STATE not-achieved';
  const element = id => elements[id] || (elements[id] = {
    disabled:false, hidden:false, checked:false, textContent:'',
    setAttribute(){}, addEventListener(){}
  });
  const backend = new WwiBackend({send(message) {
    sent.push(message);
    const match = message.match(/^WEBEEBLOCKS_RUNTIME_V2 REQUEST (\d+) (\S+)(?: (.*))?$/);
    assert.ok(match);
    const id = match[1];
    const command = match[2];
    let payload;
    if (command === 'OUTCOME') {
      assert.strictEqual(match[3], 'progression-precise-movement-v1');
      payload = response;
    } else if (command === 'FAILURE') {
      assert.strictEqual(match[3], 'progression-precise-movement-v1');
      response = options.failureResult || 'ERR OUTCOME_UNAVAILABLE';
      payload = 'OK';
    } else if (command === 'COMPLETE') {
      assert.strictEqual(match[3], 'progression-precise-movement-v1');
      if (options.completeResult)
        response = options.completeResult;
      payload = 'OK';
    } else if (command === 'RESET') {
      response = 'ERR OUTCOME_UNAVAILABLE';
      payload = 'OK';
    } else {
      throw new Error('failure recovery must not emit ' + command);
    }
    if (!options.pending)
      Promise.resolve().then(() => backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + id + ' ' + payload));
  }}, {
    simulationReset:options.physical !== true,
    simulationStop:true,
    timeoutMs:1000,
    outcomeSettleMs:0,
    outcomePollMs:0
  });
  backend.ready = true;
  const context = {
    console:{log(){},error(){}},
    Blockly:{Theme:{defineTheme(){return{};}},Themes:{Classic:{}},
      serialization:{workspaces:{save(){return {blocks:{}};}}}},
    document:{currentScript:{src:'https://example.invalid/main.js'},getElementById:element,body:{dataset:{}}},
    window:{dispatchEvent(event){events.push(event);},addEventListener(){}},
    CustomEvent:function(type, init){this.type=type;this.detail=init && init.detail;},
    WebeeBlocksRuntimeOutcome:Outcome,
    WebeeBlocksActivityContract:{async execute(profile, workspace, compiler, interpreter, target, hooks) {
      hooks.onAst({version:1, program:[]});
      if (options.stopRequested) context.runtimeStopRequested = true;
      throw Object.assign(new Error('original execution failure'), {code:options.code || 'UNSAFE_OR_TIMEOUT'});
    }},
    WebeeBlocksSemanticAst:{}, WebeeBlocksInterpreter:{}, URL, setTimeout, clearTimeout, Promise
  };
  vm.createContext(context);
  vm.runInContext(mainSource, context, {filename:'blockly_v2/main.js'});
  context.runtimeProfile = {evaluation:{type:options.legacy ? 'training-objective' : 'mission-state-v1', oracle:'progression-precise-movement-v1'}};
  context.workspace = {};
  context.runtimeBackend = backend;
  context.updateRuntimeActions();
  return {context, backend, element, sent, events};
}

function proveNativeBrokerRetention() {
  const script = path.resolve(__dirname, 'test_runtime_mission_broker.py');
  const result = childProcess.spawnSync(process.env.PYTHON || 'python3', [script], {
    cwd:path.resolve(__dirname, '../..'), encoding:'utf8'
  });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  assert.strictEqual(result.status, 0,
    'native broker regression must preserve exact current terminal mission evidence and scope failure probes');
}

async function proveMissionFailure() {
  proveNativeBrokerRetention();

  const collision = harness();
  await collision.context.runProgram();
  assert.strictEqual(collision.element('runtimeState').textContent, 'MISSION NON RÉUSSIE',
    'production runProgram must present the exact-attempt collision negative after fail-safe');
  assert.strictEqual(collision.element('runtimeDetail').textContent, 'Mission non accomplie');
  assert.strictEqual(collision.context.runtimeTerminal, true);
  assert.strictEqual(collision.element('submit').disabled, true);
  assert.strictEqual(collision.element('resetSimulation').disabled, false);
  assert.strictEqual(collision.sent.length, 1);
  assert.match(collision.sent[0], / OUTCOME progression-precise-movement-v1$/,
    'prefer an already latched exact-oracle collision outcome without any synthetic boundary');
  const diagnostic = collision.events.find(event => event.type === 'webeeblocks-runtime-v2-diagnostic');
  assert.strictEqual(diagnostic.detail.machineCode, 'UNSAFE_OR_TIMEOUT');
  assert.strictEqual(diagnostic.detail.technicalMessage, 'original execution failure');
  assert.strictEqual(diagnostic.detail.studentState, 'MISSION NON RÉUSSIE');

  await collision.context.resetSimulation();
  assert.strictEqual(collision.element('runtimeState').textContent, 'PRÊT');
  await collision.context.runProgram();
  assert.strictEqual(collision.element('runtimeState').textContent, 'ARRÊTÉ',
    'a previous negative must not survive a reset when the new attempt has no world failure');
  assert.strictEqual(collision.sent.length, 5);
  assert.match(collision.sent[1], / RESET$/);
  assert.match(collision.sent[2], / OUTCOME progression-precise-movement-v1$/);
  assert.match(collision.sent[3], / FAILURE progression-precise-movement-v1$/);
  assert.match(collision.sent[4], / OUTCOME progression-precise-movement-v1$/);
  assert.ok(!collision.sent.some(message => / COMPLETE progression-precise-movement-v1$/.test(message)),
    'execution failure must never manufacture a mission completion boundary');

  for (const initial of ['ERR OUTCOME_UNAVAILABLE', 'ERR OUTCOME_MISMATCH']) {
    const unproven = harness({response:initial});
    await unproven.context.runProgram();
    assert.strictEqual(unproven.element('runtimeState').textContent, 'ARRÊTÉ', initial);
    assert.strictEqual(unproven.element('runtimeDetail').textContent, 'L’action n’a pas pu être terminée', initial);
    assert.strictEqual(unproven.sent.length, 3, initial);
    assert.match(unproven.sent[0], / OUTCOME progression-precise-movement-v1$/);
    assert.match(unproven.sent[1], / FAILURE progression-precise-movement-v1$/,
      'missing/mismatched evidence may only name the selected oracle through the non-completion failure probe');
    assert.match(unproven.sent[2], / OUTCOME progression-precise-movement-v1$/);
    assert.ok(!unproven.sent.some(message => / COMPLETE progression-precise-movement-v1$/.test(message)), initial);
    assert.strictEqual(unproven.events.find(event => event.type === 'webeeblocks-runtime-v2-diagnostic').detail.machineCode,
      'UNSAFE_OR_TIMEOUT', 'unproven mission failure must preserve the original execution diagnostic');
  }

  for (const initial of ['ERR OUTCOME_UNAVAILABLE', 'ERR OUTCOME_MISMATCH']) {
    const probed = harness({response:initial, failureResult:'STATE not-achieved'});
    await probed.context.runProgram();
    assert.strictEqual(probed.element('runtimeState').textContent, 'MISSION NON RÉUSSIE', initial);
    assert.strictEqual(probed.element('runtimeDetail').textContent, 'Mission non accomplie', initial);
    assert.strictEqual(probed.sent.length, 3, initial);
    assert.match(probed.sent[1], / FAILURE progression-precise-movement-v1$/);
    assert.ok(!probed.sent.some(message => / COMPLETE progression-precise-movement-v1$/.test(message)), initial);
    assert.strictEqual(probed.events.find(event => event.type === 'webeeblocks-runtime-v2-diagnostic').detail.machineCode,
      'UNSAFE_OR_TIMEOUT', 'causal world failure must preserve the original execution diagnostic');
  }

  for (const response of [
    'ERR STALE_OUTCOME', 'ERR INVALID_OUTCOME',
    'STATE achieved', 'STATE interrupted', 'STATE mystery'
  ]) {
    const unproven = harness({response});
    await unproven.context.runProgram();
    assert.strictEqual(unproven.element('runtimeState').textContent, 'ARRÊTÉ', response);
    assert.strictEqual(unproven.element('runtimeDetail').textContent, 'L’action n’a pas pu être terminée', response);
    assert.strictEqual(unproven.context.runtimeTerminal, true);
    assert.strictEqual(unproven.sent.length, 1, 'stale, malformed or non-negative evidence must fail closed without a failure probe');
    assert.strictEqual(unproven.events.find(event => event.type === 'webeeblocks-runtime-v2-diagnostic').detail.machineCode,
      'UNSAFE_OR_TIMEOUT', 'preserve the original error rather than replace it with an evidence-read error');
  }

  for (const options of [
    {legacy:true}, {physical:true}, {code:'USER_STOPPED'},
    {code:'PROGRAM_INVALID'}, {code:'UNEXPECTED_TRANSPORT_FAILURE'}, {stopRequested:true}
  ]) {
    const excluded = harness(options);
    await excluded.context.runProgram();
    assert.strictEqual(excluded.sent.length, 0, 'no failure-outcome query outside a non-voluntary simulation fail-safe');
    assert.strictEqual(excluded.element('runtimeState').textContent,
      Outcome.classify({code:options.code || 'UNSAFE_OR_TIMEOUT'}).state);
  }

  const pending = harness({pending:true});
  const running = pending.context.runProgram();
  for (let index = 0; index < 10 && pending.sent.length === 0; ++index) await Promise.resolve();
  assert.strictEqual(pending.sent.length, 1);
  assert.strictEqual(pending.element('resetSimulation').disabled, true,
    'Reset must not become available while the failure outcome is pending');
  assert.strictEqual(pending.element('runtimeState').textContent, 'EN VOL');
  const requestId = pending.sent[0].split(' ')[2];
  pending.backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + requestId + ' STATE not-achieved');
  await running;
  assert.strictEqual(pending.element('runtimeState').textContent, 'MISSION NON RÉUSSIE');
  assert.strictEqual(pending.element('resetSimulation').disabled, false);
  console.log('PASS production mission failure UI: exact latched negative fast path, non-completion failure probe, fail-closed missing/mismatch/stale/invalid/non-negative evidence, user-stop and physical boundaries, Reset freshness');
}

module.exports = proveMissionFailure;
if (require.main === module) proveMissionFailure().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
