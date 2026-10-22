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


def baseline():
    rows = []
    for number in range(1, 8):
        if number == 7:
            rows.append({'event': 'response', 'detail': 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 67 ERR UNSAFE_OR_TIMEOUT'})
        event = ('integrated-' + str(number - 1) if number <= 4 else
                 {5: 'fixed-negative', 6: 'memory-negative', 7: 'front-negative'}[number])
        detail = {'status': 'achieved' if number <= 4 else 'not-achieved'}
        if number == 7:
            detail['runtime_code'] = 'UNSAFE_OR_TIMEOUT'
        rows.extend([{'event': event, 'detail': detail},
                     {'event': 'request', 'detail': f'WEBEEBLOCKS_RUNTIME_V2 REQUEST {number * 10} RESET'},
                     {'event': 'response', 'detail': f'WEBEEBLOCKS_RUNTIME_V2 RESPONSE {number * 10} OK'}])
    rows.extend([{'event': 'front-reset', 'detail': {'code': 'OUTCOME_UNAVAILABLE'}},
                 {'event': 'COMPLETE', 'detail': {}}])
    text = ('WEBEEBLOCKS_RUNTIME_V2 TRACE RESET x=0\n' * 7
            + 'WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=7 x=.75 y=-2.2 z=.5\n'
            + 'WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=7 status=not-achieved\n')
    return rows, text


class EvidenceTests(unittest.TestCase):
    def test_real_collision_baseline_and_missing_collision_refutation(self):
        rows, text = baseline()
        self.assertTrue(runner.validate_events('baseline', rows, text)['collision_attempt7_observed'])
        for altered in (text.replace('WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=7 ', ''),
                        text.replace('COLLISION attempt=7 ', 'COLLISION attempt=8 '),
                        text.replace('RESULT attempt=7 status=not-achieved', 'RESULT attempt=7 status=achieved')):
            with self.assertRaises(ValueError):
                runner.validate_events('baseline', rows, altered)

    def test_collision_requires_native_runtime_failure_and_fresh_reset_order(self):
        rows, text = baseline()
        front = next(index for index, row in enumerate(rows) if row['event'] == 'front-negative')
        altered = copy.deepcopy(rows)
        del altered[front]['detail']['runtime_code']
        with self.assertRaises(ValueError):
            runner.validate_events('baseline', altered, text)
        altered = copy.deepcopy(rows)
        altered[front], altered[front + 1] = altered[front + 1], altered[front]
        with self.assertRaises(ValueError):
            runner.validate_events('baseline', altered, text)
        altered = [row for row in rows if not (row['event'] == 'response' and 'UNSAFE_OR_TIMEOUT' in row['detail'])]
        with self.assertRaises(ValueError):
            runner.validate_events('baseline', altered, text)

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
