#!/usr/bin/env python3

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from localize_webots_world import LOCAL_PREFIX, REMOTE_PREFIX, localize
from run_crazyflie_primitive_matrix import (
    REQUIRED_PROJECT_ASSETS,
    WEBOTS_CHECKOUT,
    WEBOTS_SHA,
    build_webots_command,
    prepare_generated_world,
)


class LocalizeWebotsWorldTests(unittest.TestCase):
    def test_localizes_only_the_pinned_prefix(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wbt"
            target = root / "target.wbt"
            source.write_text(
                f'EXTERNPROTO "{REMOTE_PREFIX}projects/objects/Foo.proto"\n'
                "WorldInfo { basicTimeStep 16 }\n",
                encoding="utf-8",
            )

            self.assertEqual(localize(source, target, 1), 1)
            localized = target.read_text(encoding="utf-8")
            self.assertIn(f"{LOCAL_PREFIX}projects/objects/Foo.proto", localized)
            self.assertEqual(localized.replace(LOCAL_PREFIX, REMOTE_PREFIX), source.read_text(encoding="utf-8"))

    def test_refuses_an_unexpected_dependency_count(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wbt"
            source.write_text("WorldInfo {}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "expected exactly 1"):
                localize(source, root / "target.wbt", 1)

    def test_primitive_matrix_localizes_before_deterministic_instrumentation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wbt"
            target = root / "target.wbt"
            refs = "".join(
                f'EXTERNPROTO "{REMOTE_PREFIX}projects/test/{index}.proto"\n'
                for index in range(4)
            )
            source.write_text(
                refs
                + 'WorldInfo {\n  title "WebeeBlocks Crazyflie square experiment"\n}\n'
                + 'Crazyflie {\n  name "Crazyflie"\n  controller "crazyflie_square"\n}\n',
                encoding="utf-8",
            )

            prepare_generated_world(
                source, target, "crazyflie_square", "turn", "45", "A Y-small"
            )
            generated = target.read_text(encoding="utf-8")
            self.assertEqual(generated.count(LOCAL_PREFIX), 4)
            self.assertNotIn("raw.githubusercontent.com/cyberbotics/webots/", generated)
            self.assertIn("randomSeed 1", generated)
            self.assertIn("optimalThreadCount 1", generated)
            self.assertIn('controllerArgs [\n    "turn"\n    "45"\n  ]', generated)
            self.assertIn("synchronization TRUE", generated)
            self.assertIn("experiment — A Y-small", generated)

    def test_active_l_course_proto_binding_matches_webots_declaration(self) -> None:
        root = Path(__file__).resolve().parents[2]
        world_path = root / "worlds" / "crazyflie_l_course.wbt"
        world = world_path.read_text(encoding="utf-8")
        relative_proto = "../tools/physical/QualificationCrazyflieR2025a.proto"
        self.assertEqual(world.count(f'EXTERNPROTO "{relative_proto}"'), 1)
        self.assertNotIn("raw.githubusercontent.com/cyberbotics/webots/", world)
        self.assertNotIn("webots://", world)

        proto_path = (world_path.parent / relative_proto).resolve()
        self.assertTrue(proto_path.is_file())
        self.assertEqual(proto_path.name, "QualificationCrazyflieR2025a.proto")
        proto = proto_path.read_text(encoding="utf-8")
        self.assertIn(f"PROTO {proto_path.stem} [", proto)

        canonical = root / "tools" / "physical" / "qualification_crazyflie_r2025a.proto"
        self.assertEqual(proto_path.read_bytes(), canonical.read_bytes())

    def test_primitive_matrix_runtime_is_pinned_and_offline(self) -> None:
        self.assertEqual(WEBOTS_SHA, "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b")
        self.assertEqual(WEBOTS_CHECKOUT, ".ci-webots-r2025a")
        self.assertEqual(
            set(REQUIRED_PROJECT_ASSETS),
            {
                "projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto",
                "projects/objects/backgrounds/protos/TexturedBackground.proto",
                "projects/objects/backgrounds/protos/TexturedBackgroundLight.proto",
                "projects/objects/floors/protos/Floor.proto",
            },
        )
        command = build_webots_command(
            Path("/repo"), Path("/repo/.ci-webots-r2025a/projects"), "worlds/test.wbt"
        )
        network_index = command.index("--network")
        self.assertEqual(command[network_index + 1], "none")
        self.assertIn(
            "/repo/.ci-webots-r2025a/projects:/usr/local/webots/projects:ro", command
        )
        self.assertIn("timeout -k 5s 90s", command[-1])
        self.assertIn("/workspace/worlds/test.wbt", command[-1])


if __name__ == "__main__":
    unittest.main()
