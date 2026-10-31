#!/usr/bin/env python3
"""Disposable T2 probe: preserve A authority while B (a real Webots) fails C lock."""
from pathlib import Path

html=Path("plugins/robot_windows/blockly_v2/blockly_v2.html")
base=html.read_text(encoding="utf-8")
assert base.count("</body>")==1 and "WEBEEBLOCKS_R3_T2_CI" not in base
script=r"""
<!-- WEBEEBLOCKS_R3_T2_CI -->
<script>
(async function() {
  const root='http://127.0.0.1:8765';
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  async function request(path,payload) {
    const r=await fetch(root+path,payload===undefined ? {cache:'no-store'} :
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!r.ok) throw new Error('r3 t2 witness HTTP '+r.status);
    return r.status===204 ? null : r.json();
  }
  async function event(name,detail) {await request('/event',{event:name,detail});}
  async function until(test,label) {
    for(let i=0;i<800;i++) { if(await test()) return; await sleep(50); }
    throw new Error('T2_TIMEOUT_'+label);
  }
  try {
    await until(()=>window.runtimeBackend && runtimeBackend.ready && runtimeBackend.authorized &&
      !runtimeRecoveryPending && document.getElementById('runtimeState').textContent==='PRÊT',
      'native owner A');
    const before=JSON.stringify(Blockly.serialization.workspaces.save(workspace));
    await runtimeBackend.setLight('red');
    await event('T2_A_BEFORE_B',{ready:true,red:true,socketOpen:robotWindow.socket.readyState===1});
    await until(async()=>(await request('/phase')).phase===3, 'B native lock rejection');
    await runtimeBackend.setLight('blue');
    if(before!==JSON.stringify(Blockly.serialization.workspaces.save(workspace))) throw new Error('workspace mutated');
    await event('T2_A_AFTER_B',{ready:true,blue:true,blocklyUnchanged:true,
      socketOpen:robotWindow.socket.readyState===1});
  } catch(e) {
    await event('T2_ERROR',{message:String(e),stack:String(e && e.stack || '')});
  }
})();
</script>
"""
html.write_text(base.replace("</body>",script+"\n</body>"),encoding="utf-8")
print("R3_T2_TWO_WEBOTS_PROBE_INJECTED")
