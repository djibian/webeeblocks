"""Bounded visual re-read avoidance: live physics and fail-closed invalidation.

Pure Supervisor API fakes. These tests do NOT constitute native Windows speed
evidence, physical contact qualification or any flight admission authority.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.grand_prix.native_collider_contract_v2 import (
    _read_native_root_nodes, _verify_scene_boxes, _verify_box_measurements,
)
from tools.grand_prix.native_field_lookup_v2 import NativeFieldLookup
from tools.grand_prix.native_scene_snapshot_v2 import NativeSceneSnapshot
from tools.grand_prix.route_courses_v2 import reference_course
from tools.ci.test_grand_prix_native_collider_contract_v2 import (
    _Field, _Supervisor, _plan_and_manifest,
)
from tools.ci.test_grand_prix_native_scene_snapshot_v2 import SCENE, signature


class HistoricalVisualReuseTests(unittest.TestCase):

    def test_every_visual_change_misses_exact_root_signature(self):
        baseline = signature(SCENE)
        self.assertIsNotNone(baseline)
        snapshot = NativeSceneSnapshot(reference_course(5))
        snapshot.record(baseline, 3, {}, ())
        self.assertTrue(snapshot.matches(baseline, 3))
        for old, new in (
            ('geometry Box {', 'geometry Sphere {'),
            ('size 0.6 0.04 1.3', 'size 0.6 0.04 1.31'),
            ('Shape {', 'Pose {'),
            ('translation 2 0 0.65', 'translation 2.01 0 0.65'),
        ):
            with self.subTest(change=new):
                changed = signature(SCENE.replace(old, new))
                self.assertNotEqual(changed, baseline)
                self.assertFalse(snapshot.matches(changed, 3))
        self.assertFalse(snapshot.matches(None, 3))
        self.assertFalse(snapshot.matches(baseline, 4))

    def test_fast_path_reads_every_physical_box_but_no_visual_size(self):
        plan, boxes = _plan_and_manifest()
        scene = _Supervisor(boxes)
        lookup = NativeFieldLookup()
        live = _verify_scene_boxes(plan, boxes, _read_native_root_nodes(scene), lookup)
        original = _Field.getSFVec3f
        count = []

        def observed(field):
            count.append(field.value)
            return original(field)

        with patch.object(_Field, 'getSFVec3f', observed):
            _verify_box_measurements(boxes, live, lookup)
            self.assertEqual(len(count), 2 * len(boxes))
            count.clear()
            _verify_box_measurements(boxes, live, lookup, verify_visual=False)
            self.assertEqual(len(count), len(boxes))

        # The quick path is not permitted to reuse any old physical reading.
        collider = live[boxes[0].name][1]
        collider.fields['size'] = (9., 9., 9.)
        with self.assertRaisesRegex(RuntimeError, 'physical Box dimensions mismatch'):
            _verify_box_measurements(boxes, live, lookup, verify_visual=False)
        collider.fields['size'] = boxes[0].size
        physical = live[boxes[0].name][0]
        physical.position = (99., 0., .65)
        with self.assertRaisesRegex(RuntimeError, 'world pose mismatch'):
            _verify_box_measurements(boxes, live, lookup, verify_visual=False)

    def test_full_path_still_refuses_changed_visual_box(self):
        plan, boxes = _plan_and_manifest()
        scene = _Supervisor(boxes)
        lookup = NativeFieldLookup()
        live = _verify_scene_boxes(plan, boxes, _read_native_root_nodes(scene), lookup)
        visible = live[boxes[0].name][2][0].fields['geometry']
        visible.fields['size'] = (1., 2., 3.)
        with self.assertRaisesRegex(RuntimeError, 'rendered and physical Box mismatch'):
            _verify_box_measurements(boxes, live, lookup)

    def test_snapshot_hit_only_is_allowed_to_skip_visual_recheck(self):
        from tools.grand_prix import evaluator_scene_identity_v2 as identity
        course = reference_course(5)
        opaque = SimpleNamespace(getId=lambda: 42)
        children = SimpleNamespace(getMFNode=lambda index: opaque)
        root = object()
        supervisor = SimpleNamespace(getRoot=lambda: root)
        snapshot = SimpleNamespace(
            course=course, expected_boxes=('canonical',),
            opaque_roots=((0, 42),), matches=lambda signature, count: True,
        )
        with patch.object(identity, 'read_scene_signature', return_value=('equal',)), \\
                patch.object(identity, '_root_inventory', return_value=(children, 1)), \\
                patch.object(identity, '_read_vehicle', return_value='vehicle'), \\
                patch.object(identity, '_read_scene_boxes') as traversal, \\
                patch.object(identity, '_verify_box_measurements') as check:
            self.assertEqual(identity._check_snapshot(supervisor, object(), snapshot), 'vehicle')
            traversal.assert_called_once()
            self.assertTrue(traversal.call_args.kwargs['verified_model_edges'])
            check.assert_called_once_with(
                ('canonical',), snapshot.boxes if hasattr(snapshot, 'boxes') else None,
                unittest.mock.ANY, verify_visual=False)


if __name__ == '__main__':
    unittest.main()
