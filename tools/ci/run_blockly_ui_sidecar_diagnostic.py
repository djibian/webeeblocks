#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("run_blockly_ui_sidecar_test.py")
spec = importlib.util.spec_from_file_location("blockly_ui_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

_original_injected_harness = module.injected_harness


def injected_harness():
    source = _original_injected_harness()

    # main.js appends a <style> child to every saved-project <a>. That CSS text
    # is therefore part of anchor.textContent, even though the historical
    # restore() handler correctly uses this.innerText. Match the stable title
    # attribute set by main.js instead of treating CSS text as the project name.
    project_lookup = 'Array.from(list.querySelectorAll("a")).find(a=>a.textContent===name)'
    if project_lookup not in source:
        raise RuntimeError("unable to patch saved-project lookup")
    source = source.replace(
        project_lookup,
        'Array.from(list.querySelectorAll("a")).find(a=>a.title===name)',
        1,
    )

    needle = 'ws.addEventListener("error",()=>{result.websocketEvents.push("error");void post("/__ci_progress",{stage:result.stage,websocket:"error"});});'
    addition = needle + '\n      ws.addEventListener("message",e=>{const kind=(e.data&&e.data.constructor&&e.data.constructor.name)||typeof e.data;const preview=typeof e.data==="string"?e.data.slice(0,160):String(e.data);result.websocketEvents.push("message:"+String(currCommand)+":"+kind+":"+preview);void post("/__ci_progress",{stage:result.stage,websocket:"message",currCommand:String(currCommand),payloadType:kind,payloadPreview:preview});});'
    if needle not in source:
        raise RuntimeError("unable to inject WebSocket message diagnostics")
    return source.replace(needle, addition, 1)


module.injected_harness = injected_harness

# The old TCP readiness probe intentionally opens a non-WebSocket connection,
# which makes blocklyServer log "Transport endpoint is not connected". The real
# browser flow already waits for WebSocket.OPEN, so suppress that misleading
# probe in this diagnostic run.
module.wait_for_port = lambda port, timeout=5: None

if __name__ == "__main__":
    raise SystemExit(module.main())
