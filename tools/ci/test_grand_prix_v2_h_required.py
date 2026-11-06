"""Required CI R2025a H-ray campaign wiring; host tests prove no native PASS."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from tools.ci import run_grand_prix_v2_h_native as h_runner


class RequiredNativeHRayTests(unittest.TestCase):
    def test_required_native_h_mixed_gd_failure_refutes_geometry_digest(self):
        # A headless fake can only prove orchestration, never H sensor success.
        # Native GD H-ray acquisition is now a mandatory separate R2025a
        # witness after all legacy probes and four real contact configurations.
        from tools.ci import run_grand_prix_u_geometry as geometry
        from tools.ci import run_grand_prix_v2_contact_native as contact
        from tools.ci import run_grand_prix_v2_h_native as h_probe
        import sys
        from types import SimpleNamespace
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'bin').mkdir()
            (home / 'bin/webots-bin').write_bytes(b'host fake, not Webots')
            out = root / 'evidence'
            deadline = Mock()
            with patch.object(geometry, 'OUT', out), \
                 patch.object(geometry, 'cases', return_value=[]), \
                 patch.dict(sys.modules, {'run_grand_prix_u_deadline_native':
                            SimpleNamespace(run_native=deadline)}), \
                 patch.object(contact, 'native_run') as contacts, \
                 patch.object(h_probe, 'native_run', side_effect=RuntimeError(
                     'native H ray missing')) as rays:
                with self.assertRaisesRegex(RuntimeError, 'native H ray missing'):
                    geometry.run_native(home)
            deadline.assert_called_once_with(home)
            contacts.assert_called_once_with(home, contact.DEFAULT_INDICES)
            rays.assert_called_once_with(home, (5,), output_root=out / 'route-h-native')
            self.assertFalse((out / 'sha256.json').exists())

    def test_h_native_ci_artifact_scope_refuses_zero_exit_without_evidence(self):
        # Probe execution isolated per invocation; a zero process exit
        # without exact native JSON is not a PASS, even in the CI artifact.
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'webots').write_text('stub')
            (home / 'webots').chmod(0o755)
            evidence = root / 'geometry' / 'route-h-native'
            worlds = root / 'worlds'
            worlds.mkdir()
            unrelated = worlds / '.unrelated.wbproj'
            unrelated.write_text('preserve')
            created = []

            def spawn(command, **kwargs):
                world = Path(command[-1])
                hidden = world.with_name('.' + world.stem + '.wbproj')
                hidden.write_text('owned temporary project')
                created.append(hidden)
                process = Mock()
                process.wait.return_value = 0
                process.poll.return_value = 0
                return process

            with patch.object(h_runner, 'ROOT', root), \
                 patch.object(h_runner.subprocess, 'Popen', side_effect=spawn):
                with self.assertRaisesRegex(RuntimeError, 'no native H ray evidence'):
                    h_runner.native_run(home, (5,), output_root=evidence)
            self.assertEqual(len(created), 1)
            self.assertFalse(created[0].exists(), 'owned hidden project not removed')
            self.assertEqual(list(worlds.iterdir()), [unrelated],
                             'unrelated Webots project must be preserved')
            invocations = list(evidence.glob('invocation-*'))
            self.assertEqual(len(invocations), 1)
            self.assertFalse(list(evidence.rglob('summary.json')))
            self.assertTrue(list(evidence.rglob('native.log')))

    def test_required_native_h_contacts_reject_fake_missing_and_replayed_evidence(self):
        # Host-schema examples cannot prove a native contact. They must fail
        # when the real required runner's contact witness is absent or forged.
        from tools.grand_prix.route_courses_v2 import reference_course
        from tools.grand_prix.route_open_h_v2 import open_h_boxes
        from tools.grand_prix.route_terminal_v2 import terminal_boxes
        import copy
        course = reference_course(5)
        beams = {box.name: box for box in open_h_boxes(course)}
        bodies = [beams[f"GP_V2_H_{gate.leg_index}_BEAM"]
                  for gate in course.gates]
        bodies.append(next(box for box in terminal_boxes(course.route)
                           if box.name == "GP_V2_FINAL_PANEL"))
        now = 0
        records = []
        for index, body in enumerate(bodies):
            def samples(collision):
                nonlocal now
                values = []
                for _ in range(3):
                    now += 8
                    point = [body.x, body.y, body.z if index < len(bodies)-1 else .40]
                    values.append(dict(time_ms=now,
                        contacts=[dict(node_id=3, point=point)] if collision else [],
                        target_contacts=[dict(node_id=100+index, point=point)] if collision else []))
                return values
            passage = samples(False) if index < len(bodies)-1 else None
            records.append(dict(target=body.name, target_node_id=100+index,
                                passage=passage, free=samples(False),
                                collision=samples(True)))
        posts = {box.name: box for box in open_h_boxes(course)}
        uprights = []
        for gate in course.gates:
            for part in ("LEFT", "RIGHT"):
                body = posts[f"GP_V2_H_{gate.leg_index}_{part}"]
                post_id = 200 + len(uprights)
                def samples_for_post(collision):
                    nonlocal now
                    points = []
                    for _ in range(3):
                        now += 8
                        xyz = [body.x, body.y, .40]
                        points.append(dict(time_ms=now,
                            contacts=[dict(node_id=3, point=xyz)] if collision else [],
                            target_contacts=[dict(node_id=post_id, point=xyz)]
                            if collision else []))
                    return points
                uprights.append(dict(target=body.name, target_node_id=post_id,
                                     free=samples_for_post(False),
                                     collision=samples_for_post(True)))
        fake = dict(contact_source="Robot+Solid.getContactPoints R2025a",
                    contact_witnesses=records, post_witnesses=uprights)
        h_runner.check_contacts(fake, course)
        for mutation in ("absent", "missing", "foreign-id", "replay",
                         "missing-hit", "false-passage", "outside-panel",
                         "missing-upright", "upright-id-reuse",
                         "upright-false-passage", "upright-missing-hit"):
            with self.subTest(mutation=mutation):
                record = copy.deepcopy(fake)
                if mutation == "absent":
                    record.pop("contact_witnesses")
                elif mutation == "missing":
                    record["contact_witnesses"].pop()
                elif mutation == "foreign-id":
                    record["contact_witnesses"][0]["collision"][0]["target_contacts"][0]["node_id"] = 5
                elif mutation == "replay":
                    record["contact_witnesses"][1]["free"][0]["time_ms"] = 8
                elif mutation == "missing-hit":
                    for sample in record["contact_witnesses"][0]["collision"]:
                        sample["target_contacts"] = []
                elif mutation == "false-passage":
                    record["contact_witnesses"][0]["passage"][0]["contacts"] = [
                        dict(node_id=3, point=[0., 0., .4])]
                elif mutation == "outside-panel":
                    for sample in record["contact_witnesses"][-1]["collision"]:
                        sample["target_contacts"][0]["point"][2] = 2.
                elif mutation == "missing-upright":
                    record["post_witnesses"].pop()
                elif mutation == "upright-id-reuse":
                    record["post_witnesses"][0]["target_node_id"] = 100
                elif mutation == "upright-false-passage":
                    record["post_witnesses"][0]["free"][0]["contacts"] = [
                        dict(node_id=3, point=[0., 0., .40])]
                elif mutation == "upright-missing-hit":
                    for sample in record["post_witnesses"][0]["collision"]:
                        sample["target_contacts"] = []
                with self.assertRaises(RuntimeError):
                    h_runner.check_contacts(record, course)


if __name__ == "__main__":
    unittest.main()
