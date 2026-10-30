#!/usr/bin/env python3
"""CI-only A/B mutation. Never change physical reset/scene acceptance or C code."""
import argparse
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser()
p.add_argument('--mode',choices=['control','renewal'],required=True)
mode=p.parse_args().mode
subprocess.run([sys.executable,str(root/'tools/ci/prepare_runtime_v2_reset.py')],check=True)
html=root/'plugins/robot_windows/blockly_v2/blockly_v2.html'
source=html.read_text()
assert '<script src="main.js"></script>' in source
if mode=='control':
    # Controlled ablation: everything else, including the real native guardian,
    # unchanged, except the already-demonstrated browser document renewal.
    disabled="""<script>
window.WebeeBlocksWindowRenewal = Object.freeze({
  arm:function(){return true;}, begin:function(){return true;},
  onTransportClose:function(){return false;}, disarm:function(){}
});
</script>
"""
    source=source.replace('<script src="main.js"></script>',disabled+'<script src="main.js"></script>',1)
marker="  window.addEventListener('webeeblocks-runtime-v2', event => report('STATE', event.detail));"
assert marker in source
source=source.replace(marker,
    "  window.addEventListener('webeeblocks-window-renewal', event => report('SAME_TAB_RENEWAL', event.detail));\n"+marker,1)
html.write_text(source)
print('PREPARED_WINDOW_RENEWAL_CAUSAL_CONTRAST',mode,flush=True)
