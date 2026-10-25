#!/usr/bin/env python3
"""Use the frozen native one-step runner with a distinct preregistered protocol."""
import importlib.util
from pathlib import Path
import hashlib
import json
import sys
import tarfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_one_step', HERE.parent/'native-contact-intervention/run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.HERE = HERE

if __name__ == '__main__':
    runner.main()
    # Seal inside this same invocation, after all native producers exited and
    # logs closed. Never combine a later mutable directory with an old manifest.
    out=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
    expected=json.loads((out/'sha256.json').read_text())
    actual={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in out.rglob('*') if f.is_file() and f.name!='sha256.json'}
    if expected!=actual:
        raise RuntimeError('capture changed before archive; retain refusal, no seal')
    archive=out.with_suffix('.tar.gz')
    with tarfile.open(archive,'x:gz') as tar:
        tar.add(out,arcname=out.name)
    with tarfile.open(archive,'r:gz') as tar:
        for name,digest in expected.items():
            if hashlib.sha256(tar.extractfile(out.name+'/'+name).read()).hexdigest()!=digest:
                raise RuntimeError('archive bytes disagree with capture')
    print('ARCHIVE_SHA256 '+hashlib.sha256(archive.read_bytes()).hexdigest(),flush=True)
