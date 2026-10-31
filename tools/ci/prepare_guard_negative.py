#!/usr/bin/env python3
"""Native R2025a negative fixture: real controller and browser, never a mock ACK."""
import argparse
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[2]
html = root / "plugins/robot_windows/blockly_v2/blockly_v2.html"
parser = argparse.ArgumentParser()
parser.add_argument("--mode", required=True, choices=["lost_profile", "lost_checkpoint", "corrupt_checkpoint", "stale_witness", "early_clear", "semantic_tamper"])
args = parser.parse_args()

# The deliberately stale native witness is injected BEFORE Webots starts.
if args.mode in ("stale_witness", "early_clear"):
    world = "/workspace/worlds/crazyflie_runtime_v2.wbt"
    h = 14695981039346656037
    for b in world.encode():
        h = ((h ^ b) * 1099511628211) & ((1 << 64) - 1)
    out = Path(os.environ["WEBEEBLOCKS_RECOVERY_STATE_DIR"]) / f".webeeblocks-recovery-{h:016x}.state"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("WEBEEBLOCKS_RECOVERY_V2 " + "b" * 64 + " " + "c" * 64 + "\n")
    print("PRESEEDED_NATIVE_STALE_WITNESS", out.name, flush=True)

prelude = """
<script>
window.__guardFaultMode = __MODE__;
window.__guardCheckpointCorrupt = false;
window.__guardSemanticTampered = false;
if (window.__guardFaultMode === 'semantic_tamper') {
  const key = 'webeeblocks-world-recovery-v1';
  const raw = localStorage.getItem(key);
  if (raw !== null) {
    const checkpoint = JSON.parse(raw);
    const before = checkpoint.workspace;
    const after = before.replace(/"NUM":1(?=[,}])/, '"NUM":2');
    if (after === before) throw new Error('semantic tamper fixture NUM:1 missing');
    checkpoint.workspace = after;
    localStorage.setItem(key, JSON.stringify(checkpoint));
    window.__guardSemanticTampered = true;
    window.__guardSemanticContrast = {before:1, after:2};
  }
}
if (window.__guardFaultMode === 'lost_checkpoint' || window.__guardFaultMode === 'corrupt_checkpoint') {
  const key = 'webeeblocks-world-recovery-v1';
  if (localStorage.getItem(key)) {
    if (window.__guardFaultMode === 'lost_checkpoint') localStorage.removeItem(key);
    else { localStorage.setItem(key, '{bad checkpoint'); window.__guardCheckpointCorrupt = true; }
  }
}
</script>
""".replace("__MODE__", json.dumps(args.mode))

script = r"""
<script>
(async function() {
  const mode = window.__guardFaultMode;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  let seq = 0;
  function report(event, detail) {
    return fetch('http://127.0.0.1:8765/event', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({event, detail, seq:seq++, wall_ms:Date.now()})
    });
  }
  async function waitFor(fn, label, ms) {
    const until = Date.now() + ms;
    while (Date.now() < until) { if (fn()) return; await sleep(50); }
    throw new Error('timeout ' + label);
  }
  function evidence() {
    const submit = document.getElementById('submit');
    const state = document.getElementById('runtimeState');
    return {mode, browserCheckpoint: !!localStorage.getItem('webeeblocks-world-recovery-v1'),
      state:state && state.textContent, detail:document.getElementById('runtimeDetail').textContent,
      submitDisabled:submit.disabled, recoveryPending:window.runtimeRecoveryPending,
      terminal:window.runtimeTerminal, backendReady:!!(window.runtimeBackend && runtimeBackend.ready)};
  }
  try {
    await waitFor(() => window.workspace && window.WebeeBlocksSimulationRecovery, 'Blockly', 20000);
    if (window.__guardCheckpointCorrupt) {
      await waitFor(() => window.runtimeRecoveryPending &&
        document.getElementById('submit').disabled &&
        document.getElementById('runtimeState').textContent !== 'PRÊT', 'corrupt blocked', 10000);
      await report('NEGATIVE_LOCKED', evidence());
      return;
    }
    await waitFor(() => window.runtimeBackend && runtimeBackend.ready, 'native READY', 25000);
    const guardian = await runtimeBackend.readRecoveryStatus();
    if (guardian.state === 'NONE') {
      if (mode === 'stale_witness') throw new Error('stale native witness not detected');
      await waitFor(() => !window.runtimeRecoveryPending &&
        !document.getElementById('submit').disabled, 'initial authorization', 10000);
      // A genuine unsaved student program, not a project-file round-trip.
      const xml = mode === 'semantic_tamper' ? __BLOCKED_NUMBER__ : __BLOCKED__;
      workspace.clear();
      Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml), workspace);
      const saved = JSON.stringify(Blockly.serialization.workspaces.save(workspace));
      runtimeTerminal = true;
      runtimeNeedsRebuild = true;
      updateRuntimeActions();
      const button = document.getElementById('resetSimulation');
      if (button.disabled || button.textContent !== 'Reconstruire')
        throw new Error('reconstruction UI unavailable');
      await report('NEGATIVE_BEFORE_RELOAD', {mode, serializedBytes:saved.length});
      button.click();
      if (!document.getElementById('submit').disabled)
        throw new Error('old world unlocked after reload request');
      return;
    }
    if (guardian.state !== 'PENDING' && guardian.state !== 'INVALID')
      throw new Error('unexpected native witness: ' + guardian.state);
    if (mode === 'early_clear') {
      try {
        await runtimeBackend.clearRecoveryWitness('b'.repeat(64), 'c'.repeat(64));
        throw new Error('native witness cleared without physical RESET/scene evidence');
      } catch (error) {
        if (!error || error.code !== 'RECOVERY_LOCKED') throw error;
      }
      await report('EARLY_CLEAR_DENIED', evidence());
    }
    await waitFor(() => runtimeRecoveryPending && document.getElementById('submit').disabled &&
      document.getElementById('runtimeState').textContent !== 'PRÊT' &&
      document.getElementById('runtimeDetail').textContent.includes('Récupération non vérifiée'),
      'native recovery fail-closed', 10000);
    if (mode === 'semantic_tamper') {
      if (!window.__guardSemanticTampered) throw new Error('semantic NUM field not mutated on new document');
      await report('SEMANTIC_TAMPER_APPLIED', window.__guardSemanticContrast);
    }
    await report('NEGATIVE_LOCKED', {guardian:guardian.state, ...evidence()});
  } catch (error) {
    await report('NEGATIVE_ERROR', String(error.stack || error));
  }
})();
</script>
""".replace("__BLOCKED__", json.dumps("""<xml xmlns="https://developers.google.com/blockly/xml">
<block type="webeeblocks_v2_takeoff" id="native_guard_takeoff" x="20" y="20">
<field name="HEIGHT">0.5</field><next>
<block type="webeeblocks_v2_move" id="native_guard_move">
<field name="DIRECTION">forward</field><field name="DISTANCE">2</field>
<next><block type="webeeblocks_v2_land" id="native_guard_land"/></next>
</block></next></block></xml>""")).replace("__BLOCKED_NUMBER__", json.dumps("""<xml xmlns="https://developers.google.com/blockly/xml">
<block type="webeeblocks_v2_takeoff" id="native_guard_takeoff" x="20" y="20">
<field name="HEIGHT">0.5</field><next>
<block type="webeeblocks_v2_move" id="native_guard_move">
<field name="DIRECTION">forward</field><field name="DISTANCE">2</field>
<next><block type="webeeblocks_v2_land" id="native_guard_land"/></next>
</block></next></block>
<block type="math_number" id="r2_semantic_number" x="400" y="300">
<field name="NUM">1</field></block></xml>"""))

source = html.read_text()
if "<head>" not in source or "</body>" not in source:
    raise SystemExit("unexpected Robot Window HTML")
source = source.replace("<head>", "<head>\n" + prelude, 1)
source = source.replace("</body>", script + "\n</body>", 1)
html.write_text(source)
print("PREPARED_NATIVE_GUARD_NEGATIVE", args.mode, flush=True)
