#!/usr/bin/env python3
"""Run the integrated native collision baseline with output-only RESET locals."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from instrument import instrument
ROOT = Path(__file__).resolve().parents[2]
C = ROOT / 'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'
if __name__ == '__main__':
    args = sys.argv[1:]
    after_impact = '--after-impact' in args
    if after_impact: args.remove('--after-impact')
    env = os.environ.copy()
    if env.get('NODE_OPTIONS'):
        raise ValueError('use --after-impact, with no ambient NODE_OPTIONS')
    if after_impact:
        env['NODE_OPTIONS'] = '--require ' + str(Path(__file__).with_name('after-impact.cjs'))
    if '--mode' in args:
        raise ValueError('this experiment uses only the native collision baseline')
    out = Path(args[args.index('--output') + 1]).resolve()
    if out.exists():
        raise ValueError('new output directory required')
    original = C.read_bytes()
    integrated = subprocess.check_output(['git', 'show', 'HEAD:controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'], cwd=ROOT)
    if original != integrated:
        raise ValueError('uncommitted production source; refuse overwrite')
    modified = instrument(original.decode()).encode()
    try:
        C.write_bytes(modified)
        result = subprocess.run([sys.executable, str(ROOT/'experiments/runtime-reset-contact/run.py'),
                                 '--mode', 'baseline', *args], cwd=ROOT, env=env)
    finally:
        C.write_bytes(original)
        if out.is_dir():
            (out/'runtime-original.c').write_bytes(original)
            (out/'runtime-instrumented.c').write_bytes(modified)
            (out/'phase-config.json').write_text(json.dumps({'after_impact':after_impact,'node_options':env.get('NODE_OPTIONS'),'scope':'diagnostic-only-no-health-claim'},indent=2)+'\n')
            (out/'after-impact.cjs').write_bytes(Path(__file__).with_name('after-impact.cjs').read_bytes())
            (out/'instrument.py').write_bytes(Path(__file__).with_name('instrument.py').read_bytes())
            (out/'phase-run.py').write_bytes(Path(__file__).read_bytes())
            (out/'sha256.json').write_text(json.dumps({str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in out.rglob('*') if p.is_file() and p.name != 'sha256.json'}, indent=2)+'\n')
    sys.exit(result.returncode)
