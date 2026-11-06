"""File ownership/cleanup of the manual L-ray witness: mocks, NOT R2025a proof.

The required Grand Prix geometry suite runs these tests to ensure host Actions
can read an invocation made by the root-owned Webots container, without
reusing another invocation's summary or leaving hidden Webots project files.
"""
import json
from pathlib import Path
from stat import S_IMODE
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from tools.ci import run_grand_prix_v2_l_native as runner


def fake_install(root):
    home = root / "webots"
    (home / "resources").mkdir(parents=True)
    (home / "resources" / "version.txt").write_text("R2025a\n")
    executable = home / "webots"
    executable.write_text("stub, not Webots")
    executable.chmod(0o755)
    (root / "worlds").mkdir()
    return home


class NativeLArtifactFileTests(unittest.TestCase):
    def test_zero_exit_without_native_bytes_cleans_owned_hidden_project(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            home = fake_install(root)
            artifacts = root / "evidence"

            def spawn(command, **kwargs):
                world = Path(command[-1])
                # Webots actually uses the dot-prefixed per-world project name.
                world.with_name("." + world.stem + ".wbproj").write_text("stub")
                process = Mock()
                process.wait.return_value = 0
                process.poll.return_value = 0
                return process

            with patch.object(runner, "ROOT", root), \
                 patch.object(runner, "OUT", artifacts), \
                 patch.object(runner.subprocess, "Popen", side_effect=spawn):
                with self.assertRaisesRegex(RuntimeError, "no native output"):
                    runner.native_run(home, (5,))
            folders = list(artifacts.glob("invocation-*"))
            self.assertEqual(len(folders), 1)
            self.assertEqual(S_IMODE(folders[0].stat().st_mode), 0o755)
            self.assertFalse(list(artifacts.rglob("summary.json")),
                             "zero exit cannot recycle old native success")
            self.assertFalse(list((root / "worlds").iterdir()),
                             "only this invocation's world and hidden project may be removed")

    def test_mock_success_manifest_is_readable_without_native_pass(self):
        # These API-shaped rays only exercise atomic file publication. No
        # student/sensor/physics qualification can be derived from this test.
        with TemporaryDirectory() as directory:
            root = Path(directory)
            home = fake_install(root)
            artifacts = root / "evidence"
            from tools.grand_prix.route_courses_v2 import reference_course
            course = reference_course(5)
            near = {"front": .20, "back": 2., "left": 2., "right": 2.}
            far = {"front": .60, "back": 2., "left": 2., "right": 2.}
            record = {
                "claim": "L-only-native-teleport-perception-not-flight",
                "configuration": course.identifier,
                "webots": "R2025a",
                "timestep_ms": 8,
                "samples": [
                    {"box": f"GP_V2_L_{i}_{part}", "near": near, "far": far}
                    for i in range(2) for part in range(2)
                ]
            }

            def spawn(command, **kwargs):
                output = Path(kwargs["env"]["GP_V2_L_NATIVE_OUT"])
                output.write_text(json.dumps(record))
                kwargs["stdout"].write("GP_V2_L_NATIVE " +
                                       json.dumps(record, sort_keys=True) + "\n")
                process = Mock()
                process.wait.return_value = 0
                process.poll.return_value = 0
                return process

            with patch.object(runner, "ROOT", root), \
                 patch.object(runner, "OUT", artifacts), \
                 patch.object(runner.subprocess, "Popen", side_effect=spawn):
                runner.native_run(home, (5,))
            folders = list(artifacts.glob("invocation-*"))
            self.assertEqual(len(folders), 1)
            self.assertEqual(S_IMODE(folders[0].stat().st_mode), 0o755)
            summary = folders[0] / "summary.json"
            self.assertTrue(summary.is_file())
            self.assertEqual(S_IMODE(summary.stat().st_mode), 0o644)
            data = json.loads(summary.read_text())
            self.assertEqual([x["configuration"] for x in data["results"]],
                             [course.identifier])
            self.assertFalse(list(artifacts.rglob(".summary-*.tmp")))
            self.assertFalse(list((root / "worlds").iterdir()))


if __name__ == "__main__":
    unittest.main()
