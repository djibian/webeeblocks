"""Falsify bootstrap path isolation without pretending to run Windows DLLs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BootstrapTests(unittest.TestCase):
    def test_packaged_modules_and_original_argv_without_ambient_python(self):
        with tempfile.TemporaryDirectory(prefix='gp closure ') as temp:
            base = Path(temp)
            package = base / 'package with spaces'
            controller = package / 'controllers/grand_prix_u_evaluator'
            controller.mkdir(parents=True)
            entry = controller / 'grand_prix_u_evaluator.py'
            shutil.copyfile(ROOT / 'packaging/windows/grand_prix_evaluator_bootstrap.py', entry)
            tools = package / 'tools/grand_prix'
            tools.mkdir(parents=True)
            for name in ('layout_u.py', 'oracle_u.py', 'simulation_time.py'):
                shutil.copyfile(ROOT / 'tools/grand_prix' / name, tools / name)
            api = base / 'Webots/lib/controller/python/controller'
            api.mkdir(parents=True)
            # Only the native API is injected; product modules remain exact.
            (api / '__init__.py').write_text('class Supervisor: pass\n')
            poison = base / 'ambient'
            poison.mkdir()
            (poison / 'controller.py').write_text("raise RuntimeError('ambient controller')\n")
            env = {**os.environ, 'WEBOTS_HOME': str(base / 'Webots'), 'PYTHONPATH': str(poison)}
            command = [sys.executable, '-I', '-S', str(entry)]
            result = subprocess.run(command + ['--verify-imports'], env=env, cwd=poison,
                                    capture_output=True, text=True, check=True)
            record = json.loads(result.stdout)
            self.assertEqual(Path(record['layout']), tools / 'layout_u.py')
            self.assertEqual(Path(record['oracle_module']), tools / 'oracle_u.py')
            self.assertEqual(Path(record['controller']), api / '__init__.py')
            self.assertEqual((record['gates'], record['milliseconds']), (3, 210000))
            # runpy must retain both world arguments and execute the implementation.
            (controller / 'evaluator_impl.py').write_text(
                "import json,sys\nprint(json.dumps({'args':sys.argv[1:],'file':__file__}))\n")
            result = subprocess.run(command + ['17', '2.000'], env=env, cwd=poison,
                                    capture_output=True, text=True, check=True)
            record = json.loads(result.stdout)
            self.assertEqual(record['args'], ['17', '2.000'])
            self.assertEqual(Path(record['file']), controller / 'evaluator_impl.py')
            # Removing the exact API must fail, even with an ambient namesake.
            (api / '__init__.py').unlink()
            result = subprocess.run(command + ['--verify-imports'], env=env, cwd=poison,
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Webots R2025a Python controller API missing', result.stderr)


if __name__ == '__main__':
    unittest.main()
