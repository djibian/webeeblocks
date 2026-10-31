#!/usr/bin/env python3
"""Experiment-only T1/T3 native Robot Window probe; no product file changes committed."""
from pathlib import Path

html = Path("plugins/robot_windows/blockly_v2/blockly_v2.html")
source = html.read_text(encoding="utf-8")
assert source.count("</body>") == 1 and "WEBEEBLOCKS_R3_SESSIONS_CI" not in source

probe = r"""
<!-- WEBEEBLOCKS_R3_SESSIONS_CI -->
<script>
(async function () {
  const endpoint = 'http://127.0.0.1:8765';
  const nap = ms => new Promise(r => setTimeout(r, ms));
  async function request(path, data) {
    const response = await fetch(endpoint + path, data === undefined ?
      {cache:'no-store'} : {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)});
    if (!response.ok) throw new Error(path + ' http ' + response.status);
    return response.status === 204 ? null : response.json();
  }
  async function report(event, detail) { await request('/event', {event, detail}); }
  async function until(test, label, ms=40000) {
    const start = Date.now();
    while (Date.now() - start < ms) {
      if (test()) return;
      await nap(50);
    }
    throw new Error(label + ' timeout');
  }
  function ws() { return JSON.stringify(Blockly.serialization.workspaces.save(workspace)); }
  function ast() { return JSON.stringify(WebeeBlocksSemanticAst.compileWorkspace(workspace)); }
  function hex64() {
    const b = new Uint8Array(32); crypto.getRandomValues(b);
    return Array.from(b, x=>x.toString(16).padStart(2,'0')).join('');
  }
  async function rejectedNative(command) {
    const id = runtimeBackend.nextId++;
    const want = 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + id + ' ERR AUTH_DENIED';
    let handler, timer;
    const ack = new Promise((resolve,reject) => {
      handler = ev => {
        if (ev.detail === want) resolve();
        else if (String(ev.detail).startsWith('WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + id + ' '))
          reject(new Error('unexpected C answer, id=' + id));
      };
      window.addEventListener('webeeblocks-wwi',handler);
      timer = setTimeout(()=>reject(new Error('C denial timeout id=' + id)),12000);
    });
    try {
      robotWindow.send('WEBEEBLOCKS_RUNTIME_V2 REQUEST ' + id + ' ' + command);
      await ack;
    } finally {
      clearTimeout(timer);
      window.removeEventListener('webeeblocks-wwi',handler);
    }
  }
  try {
    const initialPhase = (await request('/phase')).phase;
    if (initialPhase !== 1 && initialPhase !== 2) throw new Error('phase');
    await until(() => window.runtimeBackend && runtimeBackend.ready &&
      runtimeBackend.authorized === true && !runtimeRecoveryPending &&
      document.getElementById('runtimeState').textContent === 'PRÊT' &&
      !document.getElementById('submit').disabled, 'native AUTH_CLAIM and PRÊT');
    const beforeW = ws(), beforeAst = ast();
    if (robotWindow.socket.readyState !== WebSocket.OPEN) throw new Error('no WWI socket');
    if (initialPhase === 1) {
      // The bearer is held only by the disposable HTTP server in volatile RAM.
      await request('/old-capability', {key:runtimeBackend.authorityKey});
      await runtimeBackend.setLight('red');
      if (ws() !== beforeW || ast() !== beforeAst) throw new Error('session1 Blockly mutated');
      await report('T1_SESSION1_EFFECT', {ready:true,led:'red',blocklyUnchanged:true,
        astUnchanged:true, currentEpoch:runtimeBackend.authorityKey.slice(0,32)});
      const timer = setInterval(async () => {
        try {
          if ((await request('/phase')).phase !== 2) return;
          clearInterval(timer);
          // Deliberately invoke the first document's original backend.
          let result = 'UNEXPECTED_ACCEPTANCE';
          try {
            await Promise.race([runtimeBackend.setLight('green'),
              nap(8000).then(()=>{throw new Error('timeout');})]);
          } catch (e) { result = 'REJECTED_OR_DISCONNECTED'; }
          await report('T3_OLD_DOCUMENT_ATTEMPT', {result,
            staleDocumentAuthorized:runtimeBackend.authorized,
            oldSocketOpen:robotWindow.socket.readyState === WebSocket.OPEN});
        } catch (e) { clearInterval(timer); }
      }, 900);
    } else {
      const old = (await request('/old-capability')).key;
      if (!/^[0-9a-f]{64}$/.test(old)) throw new Error('old key unavailable');
      if (old.slice(0,32) === runtimeBackend.authorityKey.slice(0,32))
        throw new Error('C epoch did not rotate across native processes');
      await runtimeBackend.setLight('blue');
      await rejectedNative('AUTH_CLAIM ' + old + ' ' + hex64());
      await rejectedNative('AUTH ' + old + ' LIGHT green');
      await rejectedNative('AUTH ' + old + ' STOP');
      await runtimeBackend.setLight('red');
      if (ws() !== beforeW || ast() !== beforeAst) throw new Error('session2 Blockly mutated');
      await report('T1_T3_SESSION2_EFFECT', {ready:true,blueAccepted:true,
        secondRedAccepted:true,oldClaimDenied:true,oldLightDenied:true,
        oldStopDenied:true,freshEpoch:true,blocklyUnchanged:true,astUnchanged:true,
        socketOpen:robotWindow.socket.readyState === WebSocket.OPEN});
    }
  } catch (error) {
    await report('T1_T3_ERROR', {message:String(error),stack:String(error && error.stack || '')});
  }
})();
</script>
"""
html.write_text(source.replace("</body>", probe + "\n</body>"), encoding="utf-8")
print("R3_T1_T3_NATIVE_PROBE_INJECTED")
