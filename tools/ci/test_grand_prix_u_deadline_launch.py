"""Fail-closed host proof for every deadline/pose R2025a startup command."""
import ast
import inspect
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_grand_prix_u_deadline_native as deadline


class NativeLaunchTests(unittest.TestCase):
    def test_exact_native_launch_has_minimize_but_not_no_rendering(self):
        home = Path('/qualified/webots')
        target = Path('/workspace/worlds/probe.wbt')
        env = {'WEBOTS_HOME': str(home)}
        log = io.StringIO()
        with patch.object(deadline.subprocess, 'run') as run:
            deadline.launch_native_case(home, target, env, log)
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0], [
            str(home/'webots'), '--batch', '--mode=fast', '--stdout',
            '--stderr', '--minimize', str(target)])
        self.assertEqual(args[0].count('--minimize'), 1)
        self.assertNotIn('--no-rendering', args[0])
        self.assertEqual(kwargs, {
            'cwd': deadline.ROOT, 'env': env, 'stdout': log,
            'stderr': deadline.subprocess.STDOUT, 'timeout': 45, 'check': True})

    def test_both_native_campaigns_use_the_same_qualified_launcher(self):
        for func in (deadline.run_native, deadline.run_pose_native):
            with self.subTest(function=func.__name__):
                tree = ast.parse(inspect.getsource(func))
                calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
                self.assertEqual(sum(isinstance(call.func, ast.Name) and
                                     call.func.id == 'launch_native_case'
                                     for call in calls), 1)
                self.assertFalse(any(isinstance(call.func, ast.Attribute) and
                                     call.func.attr == 'run' and
                                     any(isinstance(arg, ast.List) and
                                         any(isinstance(item, ast.Constant) and
                                             item.value == '--batch' for item in arg.elts)
                                         for arg in call.args)
                                     for call in calls))


if __name__ == '__main__':
    unittest.main()
