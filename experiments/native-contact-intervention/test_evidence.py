#!/usr/bin/env python3
"""Adversarial evidence checks against the retained native acquisition."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from analyze import analyze

RAW = Path(__file__).resolve().parent/'evidence/acquisition-03'

class Evidence(unittest.TestCase):
    def test_original_native_evidence(self):
        self.assertEqual(len(analyze(RAW)['cases']),4)

    def mutate(self, relative, fn, reseal=False):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'copy'
            shutil.copytree(RAW,target)
            path=target/relative
            fn(path)
            if reseal:
                import hashlib
                files={str(f.relative_to(target)):hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in target.rglob('*') if f.is_file() and f.name!='sha256.json'}
                (target/'sha256.json').write_text(json.dumps(files))
            with self.assertRaises(ValueError):
                analyze(target)

    def test_modified_raw_result(self):
        self.mutate('one-contact/result.json',lambda p:p.write_text('{}'))

    def test_deleted_native_log(self):
        self.mutate('one-contact/controller.log',lambda p:p.unlink())

    def test_foreign_unmanifested_file(self):
        self.mutate('foreign.txt',lambda p:p.write_text('unbound'))

    def test_forged_aggregate_even_if_resealed(self):
        def edit(p):
            rows=json.loads(p.read_text());rows[0]['after']['time_s']=.064
            p.write_text(json.dumps(rows))
        self.mutate('results.json',edit,reseal=True)

    def test_completion_marker_alone_even_if_resealed(self):
        self.mutate('one-contact/controller.log',lambda p:p.write_text('COMPLETE\n'),reseal=True)

    def test_changed_physics_even_if_resealed(self):
        self.mutate('worlds/one-contact.wbt',lambda p:p.write_text(p.read_text().replace('gravity 9.81','gravity 0')),reseal=True)

if __name__=='__main__':
    unittest.main()
