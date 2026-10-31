'use strict';
// Regression for the exact native observability race.  The original
// backend.ready-only harness is deliberately NOT a valid flight gate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const src = fs.readFileSync(path.join(__dirname, 'prepare_runtime_v2_observability.py'), 'utf8');
const main = fs.readFileSync(path.join(__dirname, '../../plugins/robot_windows/blockly_v2/main.js'), 'utf8');

// This MUST fail on the historical fixture which calls runProgram() as soon
// as backend.ready becomes true.
const anchor = '    await waitFor(() => window.runtimeBackend && runtimeBackend.ready === true &&';
const start = src.indexOf(anchor);
assert(start >= 0, 'unsafe harness must have explicit student-authorization gate');
const match = src.slice(start).match(/^    await waitFor\(\(\) => ([\s\S]*?),\s*'explicit post-native execution authorization', 20000\);/);
assert(match, 'unsafe fixture must wait for exact post-native authorization, not READY only');
const gate = match[1];
for (const necessary of [
  "runtimeBackend.ready === true", "runtimeState", "PRÊT",
  "runtimeRecoveryPending", "runtimeTerminal", "runtimeResetPending",
  "runtimeScenePending", "runtimeProjectPending", "runtimeOutcomePending",
  "runtimeStopPending", "runtimeRunning", "submit", "disabled === false"
]) assert(gate.includes(necessary), 'omitted critical authorization condition: ' + necessary);

function evaluate(overrides = {}) {
  const state = {
    backendReady: true, state: 'PRÊT', submitDisabled: false,
    runtimeRecoveryPending: false, runtimeTerminal: false,
    runtimeResetPending: false, runtimeScenePending: false,
    runtimeProjectPending: false, runtimeOutcomePending: false,
    runtimeStopPending: false, runtimeRunning: false,
    ...overrides
  };
  const backend = {ready: state.backendReady};
  const context = {
    window: {runtimeBackend: backend},runtimeBackend: backend,
    document: {getElementById(id) {
      if(id==='runtimeState')return {textContent:state.state};
      if(id==='submit')return {disabled:state.submitDisabled};
      throw Error('Unexpected id '+id);
    }}
  };
  for (const k of Object.keys(state)) if(k.startsWith('runtime'))context[k]=state[k];
  return vm.runInNewContext('Boolean(' + gate + ')',context);
}
assert.equal(evaluate(),true,'fully authorized first boot may execute');
for (const [name,value] of [
  ['backendReady',false],['state','INITIALISATION'],['state','ERREUR'],
  ['submitDisabled',true],['runtimeRecoveryPending',true],
  ['runtimeTerminal',true],['runtimeResetPending',true],
  ['runtimeScenePending',true],['runtimeProjectPending',true],
  ['runtimeOutcomePending',true],['runtimeStopPending',true],
  ['runtimeRunning',true]
])assert.equal(evaluate({[name]:value}),false,'unsafe authorization under '+name+'='+value);

// Require real, non-forged native NONE before deliberately held consumer;
// a premature program produces ZERO requests; after authorization, real
// TAKEOFF request + low-level Webots UNSAFE_OR_TIMEOUT remain mandatory.
for (const marker of [
  "const result = await originalReadRecoveryStatus.call(this, token)",
  "result.state === 'NONE'", "PREAUTH_CONTROL_REFUSED",
  "runtimeBackend.nextId !== prematureRequestId", "wwiTx.length !== 0",
  "releaseNativeStatus()", "UNSAFE_ACTUAL_TAKEOFF",
  "REQUEST \\d+ TAKEOFF", "UNSAFE_SCENARIO_DONE", "unsafe.machineCode !== 'UNSAFE_OR_TIMEOUT'",
  "unsafe.studentState !== 'ARRÊTÉ'"
])assert(src.includes(marker),'regression fixture missing native oracle: '+marker);
assert.match(main,/if \(runtimeRunning \|\| runtimeTerminal \|\| runtimeOutcomePending \|\| runtimeResetPending \|\| runtimeStopPending \|\| runtimeScenePending \|\| runtimeProjectPending \|\| runtimeRecoveryPending \|\| !runtimeBackend \|\| !runtimeBackend.ready\) return;/);
console.log('PASS: deterministic READY-only control is denied, real post-witness authorization gate is explicit, native unsafe oracles unchanged.');
