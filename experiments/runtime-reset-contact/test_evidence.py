"""Refuse a completion marker backed by absent, stale or refused RESETs."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('reset_contact_run', Path(__file__).with_name('run.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def sweep():
    rows = []
    for number in range(1, 17):
        rows.extend([{'event': 'CASE', 'detail': {'input': {'id': number}}},
                     {'event': 'request', 'detail': f'WEBEEBLOCKS_RUNTIME_V2 REQUEST {number} RESET'},
                     {'event': 'response', 'detail': f'WEBEEBLOCKS_RUNTIME_V2 RESPONSE {number} OK'},
                     {'event': 'RESET_OK', 'detail': {'id': number}}])
    rows.append({'event': 'COMPLETE', 'detail': {}})
    return rows, 'WEBEEBLOCKS_RUNTIME_V2 TRACE RESET x=0\n' * 16


class EvidenceTests(unittest.TestCase):
    def test_complete_scoped_reset_evidence(self):
        rows, text = sweep()
        result = runner.validate_events('sweep', rows, text)
        self.assertEqual(result['reset_acknowledgements'], 16)
        self.assertFalse(result['collision_attempt7_observed'])

    def test_marker_alone_missing_trace_or_negative_cannot_pass(self):
        rows, text = sweep()
        for altered, native in [([rows[-1]], text), (rows, ''), (rows, text + 'RESET_TIMEOUT'),
                                (rows + [{'event': 'RESET_FAILED', 'detail': {'id': 16}}], text),
                                (rows + [rows[-1]], text)]:
            with self.assertRaises(ValueError):
                runner.validate_events('sweep', altered, native)

    def test_duplicate_or_wrong_ack_and_case_are_refused(self):
        rows, text = sweep()
        for index, replacement in [(2, 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 ERR RESET_TIMEOUT'),
                                   (2, 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 16 OK')]:
            altered = copy.deepcopy(rows)
            altered[index]['detail'] = replacement
            with self.assertRaises(ValueError):
                runner.validate_events('sweep', altered, text)
        altered = copy.deepcopy(rows)
        altered[0]['detail']['input']['id'] = 2
        with self.assertRaises(ValueError):
            runner.validate_events('sweep', altered, text)


if __name__ == '__main__':
    unittest.main()
