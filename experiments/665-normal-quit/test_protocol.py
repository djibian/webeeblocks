"""Bounded host checks of retirement refusal; these are NOT native evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.ci import run_grand_prix_u_prototype as runner

class Protocol(unittest.TestCase):
    def prepare(self, root, attempts):
        (root/'events.jsonl').write_text('{}\n')
        (root/'result.json').write_text('{}')
        (root/'webots.log').write_text('GP_U_RESULT {}\n')
        for a in attempts:
            (root/f'native-result-{a}.json').write_text('{}')
            (root/f'native-diagnostic-{a}.json').write_text(json.dumps(
                dict(time=1.0,position=[0,0,0],velocity=[0,0,0])))

    def test_confirmed_exit_and_eof_after_complete_second_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.prepare(root,[1,2])
            class Child:
                pid=123;returncode=0
                def wait(self,timeout):
                    req=(root/'normal-quit.request').read_text()
                    self_request=req.split()[0]
                    assert self_request=='2'
                    (root/'normal-quit.ack').write_text(req)
            log=SimpleNamespace(finish=lambda:None)
            with patch.object(runner,'process_group',return_value=[]):
                runner.normal_quit_after_validation(root,Child(),log,[1,2])
            self.assertTrue(json.loads((root/'normal-quit.json').read_text())['normal_success'])

    def test_missing_second_diagnostic_forbids_request(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.prepare(root,[1,2]);(root/'native-diagnostic-2.json').unlink()
            with self.assertRaises(FileNotFoundError):
                runner.normal_quit_after_validation(root,None,None,[1,2])
            self.assertFalse((root/'normal-quit.request').exists())

    def test_refuses_timeout_bad_ack_crash_eof_or_changed_proof(self):
        for fault in ('timeout','exit','ack','crash','eof','mutation','survivor'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as d:
                root=Path(d);self.prepare(root,[1])
                class Child:
                    pid=123;returncode=139 if fault=='exit' else 0
                    def wait(self,timeout):
                        if fault=='timeout':raise subprocess.TimeoutExpired('webots',timeout)
                        req=(root/'normal-quit.request').read_text()
                        (root/'normal-quit.ack').write_text('wrong' if fault=='ack' else req)
                        if fault=='mutation':(root/'native-result-1.json').write_text('{"changed":true}')
                        if fault=='crash':(root/'webots.log').write_text('malloc(): corrupted\n')
                def finish():
                    if fault=='eof':raise RuntimeError('pipe still held')
                groups=[{'pid':9}] if fault=='survivor' else []
                with patch.object(runner,'process_group',return_value=groups), patch.object(
                        runner.time,'monotonic',side_effect=[0,3] if fault=='survivor' else [0]), self.assertRaises(Exception):
                    runner.normal_quit_after_validation(root,Child(),SimpleNamespace(finish=finish),[1])
                self.assertFalse(json.loads((root/'normal-quit.json').read_text())['normal_success'])

    def test_host_gate_remains_after_all_existing_oracles(self):
        source=(ROOT/'tools/ci/run_grand_prix_u_prototype.py').read_text()
        trial=source.split('def trial(',1)[1].split('\ndef retire_trial(',1)[0]
        decision=trial.index('normal_quit_after_validation(out,')
        for anchor in ('second identical program after native RESET failed',
                       'missing independent forced LAND/failure','wrong native subject',
                       "(out/'result.json').write_text"):
            self.assertLess(trial.index(anchor),decision)
        self.assertIn('children[1:] if normal_quit_confirmed else children',source)

if __name__=='__main__':unittest.main()
