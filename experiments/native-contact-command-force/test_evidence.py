#!/usr/bin/env python3
"""The original wrapper's force/torque confusion must remain a refusal."""
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('command_force_analysis',HERE/'analyze.py')
analysis=importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)

class NativeEvidence(unittest.TestCase):
    def test_fixed_native_fixture(self):
        result=analysis.analyze(HERE/'evidence/acquisition-03')
        self.assertEqual(len(result['cases']),4)

    def test_wrong_force_torque_wrapper_refused(self):
        p=json.loads((HERE/'protocol.json').read_text())
        row=json.loads((HERE/'evidence/protocol-refuted-01/no-floor-control/result.json').read_text())
        with self.assertRaisesRegex(ValueError,'force/torque balance'):
            analysis.validate_no_floor(p,row)

    def test_partial_capture_01_refused(self):
        with self.assertRaisesRegex(ValueError,'archive inventory'):
            analysis.analyze(HERE/'evidence/protocol-refuted-01')

    def test_partial_capture_02_refused(self):
        with self.assertRaisesRegex(ValueError,'archive inventory'):
            analysis.analyze(HERE/'evidence/capture-refuted-02')

    def test_unforced_protocol_not_relabelled(self):
        with self.assertRaisesRegex(ValueError,'preregistered'):
            analysis.analyze(HERE.parent/'native-contact-intervention/evidence/acquisition-03')

if __name__=='__main__':
    unittest.main()
