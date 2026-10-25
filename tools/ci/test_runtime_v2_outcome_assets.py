#!/usr/bin/env python3
"""Falsify preparation integrity and preserve the real native proof boundary."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime_v2_outcome_assets as assets
import run_runtime_v2_outcome_freshness as runner
from localize_webots_world import LOCAL_PREFIX, REMOTE_PREFIX


class OutcomeAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.world = self.root / "source.wbt"
        self.world.write_text("".join(
            f'EXTERNPROTO "{REMOTE_PREFIX}projects/test/{i}.proto"\n'
            for i in range(4)) + 'WorldInfo { basicTimeStep 32 }\n')
        self.data = b"original pinned bytes\n"
        self.item = {
            "path": "projects/test/asset.proto", "bytes": len(self.data),
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(self.data)).encode() + b"\0" + self.data).hexdigest(),
        }
        self.lock = {"schema": 1, "source_commit": assets.SOURCE_COMMIT, "assets": [self.item]}

    def test_exact_closure_for_unchanged_world_defaults(self):
        paths = {item["path"] for item in assets.load_lock()["assets"]}
        expected = {
            "projects/robots/bitcraze/crazyflie/protos/" + suffix
            for suffix in ("Crazyflie.proto", "meshes/cf2_assembly.dae", "meshes/ccw_prop.dae")
        } | {
            "projects/objects/backgrounds/protos/TexturedBackground.proto",
            "projects/objects/backgrounds/protos/TexturedBackgroundLight.proto",
            "projects/objects/floors/protos/Floor.proto",
            "projects/appearances/protos/Parquetry.proto",
            "projects/default/protos/textures/fast_helix.png",
        } | {
            f"projects/default/worlds/textures/cubic/mountains_{side}.{ext}"
            for side in ("back", "bottom", "front", "left", "right", "top")
            for ext in ("hdr", "jpg")
        } | {
            f"projects/appearances/protos/textures/parquetry/chequered_parquetry_{kind}.jpg"
            for kind in ("base_color", "normal", "occlusion", "roughness")
        }
        self.assertEqual(paths, expected)

    def test_inventory_rejects_traversal_duplicate_bad_digest_and_unbounded_data(self):
        for changes in (
            {"path": "projects/../../escape"}, {"path": "/projects/absolute"},
            {"path": "projects\\windows"}, {"sha256": "0"},
            {"bytes": assets.MAX_FILE_BYTES + 1}, {"bytes": True},
            {"git_blob": "not-a-git-blob"},
        ):
            with self.subTest(changes=changes):
                bad = copy.deepcopy(self.lock)
                bad["assets"][0].update(changes)
                path = self.root / "lock.json"
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    assets.load_lock(path)
        for bad in (
            {**self.lock, "source_commit": "main"},
            {**self.lock, "assets": []},
            {**self.lock, "assets": [self.item, self.item]},
        ):
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                assets.load_lock(path)

    def test_verified_bytes_only_and_prefix_only_world_change(self):
        evidence = self.root / "evidence.json"
        with patch.object(assets, "load_lock", return_value=self.lock), \
                patch.object(assets, "urlopen", return_value=io.BytesIO(self.data)) as fetch:
            world, projects = assets.prepare(self.root / "assets", self.world, evidence)
        self.assertEqual((projects / "test/asset.proto").read_bytes(), self.data)
        self.assertEqual(world.read_text().replace(LOCAL_PREFIX, REMOTE_PREFIX), self.world.read_text())
        fetch.assert_called_once_with(
            f"https://raw.githubusercontent.com/cyberbotics/webots/{assets.SOURCE_COMMIT}/{self.item['path']}", timeout=30)
        record = json.loads(evidence.read_text())
        self.assertEqual(record["status"], "PREPARED")
        self.assertEqual(record["assets"], [self.item])
        self.assertEqual(record["local_world_sha256"], hashlib.sha256(world.read_bytes()).hexdigest())

    def test_truncated_oversized_corrupt_and_wrong_git_bytes_never_prepare(self):
        for index, data in enumerate((self.data[:-1], self.data + b"x", b"X" + self.data[1:], self.data)):
            lock = copy.deepcopy(self.lock)
            if index == 3:
                lock["assets"][0]["git_blob"] = "0" * 40
            evidence = self.root / f"evidence-{index}.json"
            with patch.object(assets, "load_lock", return_value=lock), \
                    patch.object(assets, "urlopen", return_value=io.BytesIO(data)):
                with self.assertRaisesRegex(ValueError, "integrity failure"):
                    assets.prepare(self.root / f"assets-{index}", self.world, evidence)
            self.assertFalse(evidence.exists())

    def test_network_failure_has_no_retry_or_prepared_evidence(self):
        evidence = self.root / "evidence.json"
        with patch.object(assets, "load_lock", return_value=self.lock), \
                patch.object(assets, "urlopen", side_effect=TimeoutError("network")) as fetch:
            with self.assertRaises(TimeoutError):
                assets.prepare(self.root / "assets", self.world, evidence)
        self.assertEqual(fetch.call_count, 1)
        self.assertFalse(evidence.exists())

    def test_existing_tree_is_refused_before_network(self):
        with patch.object(assets, "load_lock", return_value=self.lock), \
                patch.object(assets, "urlopen") as fetch:
            with self.assertRaises(FileExistsError):
                assets.prepare(self.root, self.world, self.root / "evidence.json")
        fetch.assert_not_called()

    def test_real_runner_refuses_setup_failure_before_native_execution(self):
        result = runner.subprocess.CompletedProcess([], 0, "")
        with patch.object(runner.shutil, "which", return_value="docker"), \
                patch.object(runner, "ARTIFACT_ROOT", self.root / "artifacts"), \
                patch.object(runner, "run", return_value=result), \
                patch.object(runner, "prepare_assets", side_effect=ValueError("corrupt")), \
                patch.object(runner.subprocess, "run") as native, \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(runner.main(), 1)
        native.assert_not_called()
        self.assertIn("preparation / Webots assets (no native launch)", errors.getvalue())

    def test_real_native_argv_keeps_world_perspective_rendering_and_35_seconds(self):
        result = runner.subprocess.CompletedProcess([], 0, "")
        world, projects = self.root / "local.wbt", self.root / "projects"
        class StopBeforeNative(Exception):
            pass
        with patch.object(runner.shutil, "which", return_value="docker"), \
                patch.object(runner, "ARTIFACT_ROOT", self.root / "artifacts"), \
                patch.object(runner, "run", return_value=result), \
                patch.object(runner, "prepare_assets", return_value=(world, projects)), \
                patch.object(runner.subprocess, "run", side_effect=StopBeforeNative) as native:
            with self.assertRaises(StopBeforeNative):
                runner.main()
        argv = native.call_args.args[0]
        self.assertIn(f"{projects}:/usr/local/webots/projects:ro", argv)
        self.assertIn(f"{world}:/workspace/worlds/runtime_v2_outcome_probe.wbt:ro", argv)
        self.assertIn(runner.WEBOTS_IMAGE, argv)
        inner = argv[-1]
        self.assertEqual(inner.count("timeout -k 5s 35s xvfb-run -a webots"), 1)
        self.assertIn("--batch --mode=realtime /workspace/worlds/runtime_v2_outcome_probe.wbt", inner)
        self.assertNotIn("--no-rendering", inner)
        self.assertNotIn("--minimize", inner)  # separate Qt intervention, not smuggled into asset preparation


if __name__ == "__main__":
    unittest.main()
