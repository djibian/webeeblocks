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
        const timeout = setTimeout(() => reject(new Error('R3 B did not report native denial')), 25000);
        channel.onmessage = ev => {
          const x = ev.data;
          if (!x || x.tag !== 'R3_B_NATIVE_REFUSED') return;
          clearTimeout(timeout);
          resolve(x);
        };
      });
      // Distinct top-level Robot Window document on EXACTLY the same Webots URL.
      winB = window.open(location.href, 'webeeblocks-r3-late-b');
      if (!winB) throw new Error('R3 popup refused; no second document was created');
      await report('R3_A_OPENED_B_AFTER_CLEAR', {nonceA, href: location.href, aRequestId: runtimeBackend.nextId});
      const b = await bEffect;
      if (!b || b.nativeStatus !== 'NONE' || b.status === 'PRÊT' || !b.runDisabled || b.denial !== 'AUTH_DENIED')
        throw new Error('R3 B was not denied by C: ' + JSON.stringify(b));
      // A stays open while the CI launcher opens independent Chrome profile B2.
      await report('R3_A_WAIT_INDEPENDENT_PROFILE', {nonceA});
      await sleep(22000);
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
        throw new Error('R3 A lost authority after B native denial');
    } finally {
      if (winB) winB.close();
      channel.close();
    }
  }
  try {
    if (window.name === 'webeeblocks-r3-late-b' || location.hash === '#webeeblocks-r3-profile-b2') {
      const independentProfile = location.hash === '#webeeblocks-r3-profile-b2';
      const nonceB = crypto.randomUUID();
      await report(independentProfile ? 'R3_B2_BOOT' : 'R3_B_BOOT', {nonceB, href:location.href,
        checkpointPresent:WebeeBlocksSimulationRecovery.peek() !== null});
      await waitFor(() => runtimeBackend && runtimeBackend.ready &&
          runtimeRecoveryPending && document.getElementById('submit').disabled,
          'late B receives native denial', 16000);
      const status = await runtimeBackend.readRecoveryStatus();
      if (!status || status.state !== 'NONE')
        throw new Error('late B did not observe native NONE: ' + JSON.stringify(status));
      if (WebeeBlocksSimulationRecovery.peek() !== null)
        throw new Error('late B unexpectedly saw checkpoint after CLEAR');
      // Deliberate JS-guard bypass: the real C controller must reject the
      // unowned LIGHT and STOP even though Webots carries both WWI frames.
      async function forceNativeDenial(command) {
        const id = runtimeBackend.nextId++;
        const denied = new Promise((resolve, reject) => {
          const timer = setTimeout(() => { window.removeEventListener('webeeblocks-wwi', handler);
            reject(new Error('No native rejection for ' + command)); }, 7000);
          function handler(event) {
            const match = String(event.detail).match(new RegExp('^WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + id + ' ERR ([A-Z_]+)$'));
            if (!match) return;
            clearTimeout(timer);
            window.removeEventListener('webeeblocks-wwi', handler);
            resolve(match[1]);
          }
          window.addEventListener('webeeblocks-wwi', handler);
        });
        robotWindow.send('WEBEEBLOCKS_RUNTIME_V2 REQUEST ' + id + ' ' + command);
        return {id, reason:await denied};
      }
      const effect = await forceNativeDenial('LIGHT ' + (independentProfile ? 'green' : 'blue'));
      const stop = await forceNativeDenial('STOP');
      if (effect.reason !== 'AUTH_DENIED' || stop.reason !== 'AUTH_DENIED')
        throw new Error('Late B native request accepted: ' + JSON.stringify({effect,stop}));
      const result = {tag:'R3_B_NATIVE_REFUSED', nonceB, nativeStatus:status.state,
        requestId:effect.id, denial:effect.reason, stopDenial:stop.reason,
        status:document.getElementById('runtimeState').textContent,
        runDisabled:document.getElementById('submit').disabled,
        socketOpen:robotWindow.socket.readyState === WebSocket.OPEN};
      await report(independentProfile ? 'R3_B2_NATIVE_REFUSED' : 'R3_B_NATIVE_REFUSED', result);
      if (!independentProfile) {
        const channel = new BroadcastChannel(R3_CHANNEL);
        channel.postMessage(result);
        await sleep(3000);
        channel.close();
      }
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
