"""Ensure installed-campaign evidence never turns incomplete execution into PASS."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_grand_prix_windows_native import engine_environment, validate
from tools.grand_prix.layout_u import generate


class EvidenceTests(unittest.TestCase):
    def test_real_windows_uppercase_copy_and_mixed_case_inputs(self):
        for root_key in ('SYSTEMROOT', 'SystemRoot'):
            ambient = {root_key: '/Windows', 'Path': '/ambient',
                       'qt_qpa_platform_plugin_path': '/foreign-qt'}
            env = engine_environment(Path('/Webots'), ambient)
            self.assertEqual(env['SYSTEMROOT'], '/Windows')
            self.assertNotIn('/ambient', env['PATH'])
            self.assertIn(str(Path('/Windows') / 'System32'), env['PATH'])
            self.assertNotIn('QT_QPA_PLATFORM_PLUGIN_PATH', env)
            self.assertEqual(env['QT_ENABLE_HIGHDPI_SCALING'], '1')
            self.assertIn('qt_qpa_platform_plugin_path', ambient)
        with self.assertRaises(ValueError):
            engine_environment(Path('/Webots'), {'PATH': '/ambient'})

    def fixture(self, root):
        layout = generate(0)
        result = dict(status='achieved', configuration=layout.identifier, attempt=1,
                      crossings=1, seconds=100, reason=None)
        rows = [dict(event='program', detail={'program': []}),
                dict(event='outcome', detail={'status': 'achieved'})]
        (root / 'native_trace.csv').write_text('time,attempt,x,y,z\n' + '1,1,0,0,0\n' * 20, encoding='utf-8')
        (root / 'native-diagnostic-1.json').write_text(json.dumps(dict(crossings=1,
            landing_target=layout.landing_target(1))), encoding='utf-8')
        self.write(root, rows, result)
        return rows, result

    def write(self, root, rows, result, logged=None):
        (root / 'events.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        (root / 'native-result-1.json').write_text(json.dumps(result), encoding='utf-8')
        (root / 'webots.stdout.log').write_text('GP_U_RESULT ' + json.dumps(result if logged is None else logged) + '\n', encoding='utf-8')

    def test_missing_failed_wrong_subject_or_ambiguous_evidence_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows, result = self.fixture(root)
            self.assertEqual(validate(root, 0)['status'], 'achieved')
            for field, bad in [('status', 'not-achieved'), ('configuration', 'foreign'),
                               ('attempt', 2), ('crossings', 2), ('seconds', 210),
                               ('seconds', float('nan'))]:
                with self.subTest(field=field, bad=bad):
                    changed = dict(result, **{field: bad})
                    self.write(root, rows, changed)
                    with self.assertRaises(ValueError): validate(root, 0)
            for event in ('error', 'transport-error', 'wall-timeout'):
                self.write(root, rows + [dict(event=event, detail={})], result)
                with self.assertRaises(ValueError): validate(root, 0)
            for changed in (rows[:1], rows[1:], rows + [copy.deepcopy(rows[0])]):
                self.write(root, changed, result)
                with self.assertRaises(ValueError): validate(root, 0)
            self.write(root, rows, result, dict(result, seconds=101))
            with self.assertRaises(ValueError): validate(root, 0)
            self.write(root, rows, result)
            (root / 'webots.stderr.log').write_text('ERROR: controller failed\n', encoding='utf-8')
            with self.assertRaises(ValueError): validate(root, 0)
            (root / 'webots.stderr.log').unlink()
            (root / 'native_trace.csv').unlink()
            with self.assertRaises(ValueError): validate(root, 0)


if __name__ == '__main__':
    unittest.main()
