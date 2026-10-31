#!/usr/bin/env python3
"""EXPERIMENT ONLY: graft a late-second-window probe onto the existing native reload replay.

Run AFTER prepare_runtime_v2_reset.py, against its disposable injected HTML.
Does not modify product sources, recovery behavior, or any native safety oracle.
The runner must enable popups in its isolated experimental Chrome profile.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
html = root / "plugins/robot_windows/blockly_v2/blockly_v2.html"
text = html.read_text(encoding="utf-8")
assert "<!-- WEBEEBLOCKS_RESET_REPLAY_CI -->" in text, "run prepare_runtime_v2_reset.py first"

boot_anchor = "  try {\n    const old = localStorage.getItem(RECOVERY_STAGE);"
assert text.count(boot_anchor) == 1, "replay boot anchor changed"
boot_replacement = r"""
  // Genuine second document, opened only AFTER A reports its recovered READY.
  // B has its own RobotWindow instance and its own WebSocket, not a mock backend.
  const R3_CHANNEL = 'webeeblocks-r3-native-late-window-v1';
  async function r3TestLateWindow() {
    if (WebeeBlocksSimulationRecovery.peek() !== null || runtimeRecoveryPending ||
        document.getElementById('runtimeState').textContent !== 'PRÊT' ||
        document.getElementById('submit').disabled)
      throw new Error('R3 A not authorized after native CLEAR');
    const nonceA = crypto.randomUUID();
    const channel = new BroadcastChannel(R3_CHANNEL);
    let winB;
    try {
      const bEffect = new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('R3 B did not report native effect')), 25000);
        channel.onmessage = ev => {
          const x = ev.data;
          if (!x || x.tag !== 'R3_B_NATIVE_EFFECT') return;
          clearTimeout(timeout);
          resolve(x);
        };
      });
      // Distinct top-level Robot Window document on EXACTLY the same Webots URL.
      winB = window.open(location.href, 'webeeblocks-r3-late-b');
      if (!winB) throw new Error('R3 popup refused; no second document was created');
      await report('R3_A_OPENED_B_AFTER_CLEAR', {nonceA, href: location.href, aRequestId: runtimeBackend.nextId});
      const b = await bEffect;
      if (!b || b.nativeStatus !== 'NONE' || b.status !== 'PRÊT' || b.runDisabled)
        throw new Error('R3 B failed native status/JS authority discriminator: ' + JSON.stringify(b));
      const native = await runtimeBackend.readRecoveryStatus();
      if (!native || native.state !== 'NONE') throw new Error('R3 A native state changed');
      const aRequestId = runtimeBackend.nextId;
      await runtimeBackend.setLight('red');
      await report('R3_A_NATIVE_EFFECT', {
        nonceA, bNonce:b.nonceB, aRequestId, aStatus:document.getElementById('runtimeState').textContent,
        aRunDisabled:document.getElementById('submit').disabled,
        bRequestId:b.requestId, bNativeStatus:b.nativeStatus,
        aSocketOpen:robotWindow.socket.readyState === WebSocket.OPEN
      });
      if (document.getElementById('submit').disabled)
        throw new Error('R3 A lost UI execution after B native effect');
    } finally {
      if (winB) winB.close();
      channel.close();
    }
  }
  try {
    if (window.name === 'webeeblocks-r3-late-b') {
      const nonceB = crypto.randomUUID();
      await report('R3_B_BOOT', {nonceB, href:location.href,
        checkpointPresent:WebeeBlocksSimulationRecovery.peek() !== null});
      await waitFor(() => runtimeBackend && runtimeBackend.ready && !runtimeRecoveryPending &&
          document.getElementById('runtimeState').textContent === 'PRÊT' &&
          !document.getElementById('submit').disabled,
          'late B native authorization', 16000);
      const status = await runtimeBackend.readRecoveryStatus();
      if (!status || status.state !== 'NONE')
        throw new Error('late B did not observe native NONE: ' + JSON.stringify(status));
      if (WebeeBlocksSimulationRecovery.peek() !== null)
        throw new Error('late B unexpectedly saw checkpoint after CLEAR');
      const requestId = runtimeBackend.nextId;
      // Physical LED color change (no takeoff); confirms actual native acceptance,
      // not a mere WebSocket delivery, READY label, or forged controller ACK.
      await runtimeBackend.setLight('blue');
      const result = {tag:'R3_B_NATIVE_EFFECT', nonceB, nativeStatus:status.state,
        requestId, status:document.getElementById('runtimeState').textContent,
        runDisabled:document.getElementById('submit').disabled,
        socketOpen:robotWindow.socket.readyState === WebSocket.OPEN};
      await report('R3_B_NATIVE_EFFECT', result);
      const channel = new BroadcastChannel(R3_CHANNEL);
      channel.postMessage(result);
      await sleep(3000);
      channel.close();
      await chain;
      return;
    }
    const old = localStorage.getItem(RECOVERY_STAGE);"""
text = text.replace(boot_anchor, boot_replacement, 1)

recovered_anchor = """      document.getElementById('submit').click();
      await waitFor(() => document.getElementById('runtimeState').textContent === 'ARRÊTÉ',
        'real colliding program after full reload', 45000);"""
assert text.count(recovered_anchor) == 1, "recovered-native replay anchor changed"
text = text.replace(recovered_anchor, "      await r3TestLateWindow();\n" + recovered_anchor, 1)
html.write_text(text, encoding="utf-8")
print("R3_LATE_WINDOW_NATIVE_PROBE_INJECTED")
