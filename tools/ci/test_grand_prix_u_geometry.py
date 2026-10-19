"""Geometric counterexamples, independent of any reference solution."""
import csv
import dataclasses
from io import StringIO
import json
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.grand_prix.layout_u import generate, world_text, local, RADIUS
from tools.ci.run_grand_prix_u_prototype import without_checker_cells
from tools.grand_prix.contact_trace import encode_contact_points


def gap(p, b):
    return math.sqrt(sum(max(abs(x-c)-s/2, 0)**2 for x,c,s in
                         zip(p, (b.x,b.y,b.z), (b.sx,b.sy,b.sz))))


class Tests(unittest.TestCase):
    def test_configurations_preserve_fixed_geometry_and_have_no_low_obstacle(self):
        first = generate(0)
        seen = set()
        for seed in range(1024):
            layout = generate(seed)
            self.assertEqual(layout.walls, first.walls)
            self.assertEqual(layout.polygon, first.polygon)
            self.assertEqual(layout.final_gates, first.final_gates)
            self.assertTrue(1 <= len(layout.gates) <= 3)
            self.assertEqual(len({g.side for g in layout.gates}), len(layout.gates))
            seen.add(len(layout.gates))
            for b in layout.boxes:
                # Every collider either reaches the full wall height or is
                # a suspended H crossbar. There is no knee-height collider.
                self.assertAlmostEqual(b.z+b.sz/2, 1.3)
            text = world_text(layout)
            self.assertEqual(text.count('DEF GP_U_BAND_'), 2*len(layout.gates))
            self.assertNotIn('candidate_points', text)
        self.assertEqual(seen, {1,2,3})

    def test_low_gate_envelope_and_high_collision_are_discriminated(self):
        for seed in range(32):
            layout = generate(seed)
            for g in layout.gates:
                self.assertGreater(min(gap((g.x,g.y,.4), b) for b in layout.boxes), RADIUS)
                self.assertLess(min(gap((g.x,g.y,.8), b) for b in layout.boxes), RADIUS)
                self.assertEqual(local(g, (g.x,g.y,.4)), (0.,0.))

    def test_terminal_targets_fit_and_closed_barrier_cannot_be_bypassed(self):
        layout = generate(0)
        for count in (1,2,3):
            x,y = layout.landing_target(count)
            self.assertGreater(min(gap((x,y,.4),b) for b in layout.boxes), RADIUS)
        for y_mm in range(1100,2901,10):
            # Even the full widened terminal cross-section is blocked.
            self.assertLess(gap((0.,y_mm/1000,.4),layout.gate_boxes[-1]),RADIUS)
        self.assertEqual(layout.landing_target(2), (.7,1.5))
        self.assertEqual(layout.landing_target(3), (.7,2.5))

    def test_three_checkered_targets_have_visible_border_without_collisions(self):
        # Three independent 4x4 grids, same green margin and contrasts as
        # sequence-v1; visual markers must not add physical collisions.
        for seed in (0, 1, 2, 5, 65535):
            layout = generate(seed)
            world = world_text(layout)
            for count in (1, 2, 3):
                x, y = layout.landing_target(count)
                self.assertIn(
                    f'DEF GP_U_TARGET_{count} Pose {{ translation {x:.6f} {y:.6f} .002',
                    world)
                markers = [line for line in world.splitlines()
                           if line.startswith(f'DEF GP_U_TARGET_{count}_CELL_')]
                self.assertEqual(len(markers), 16)
                self.assertTrue(all('boundingObject' not in line for line in markers))
                self.assertEqual(sum('baseColor .06 .06 .06' in line for line in markers), 8)
                self.assertEqual(sum('baseColor .96 .96 .96' in line for line in markers), 8)
                self.assertTrue(all('geometry Box { size .0625 .0625 .0002 }' in line
                                    for line in markers))
            self.assertEqual(len(layout.gate_boxes), len(generate(seed).gate_boxes))


    def test_native_contact_manifold_trace_is_ordered_lossless_and_explicit(self):
        # Trace metadata only. The oracle still consumes the original points.
        class Contact:
            def __init__(self, point):
                self.point = point

        contacts = [Contact((0.2, -0.4, 0.015)),
                    Contact((0.12, -0.41, 0.011)),
                    Contact((-0.08, 0.3, 0.017))]
        self.assertEqual(encode_contact_points(None), '')
        self.assertEqual(encode_contact_points([]), '[]')
        encoded = encode_contact_points(contacts)
        self.assertEqual(json.loads(encoded), [list(c.point) for c in contacts])
        out = StringIO()
        writer = csv.writer(out)
        writer.writerow(['contact_count', 'contact_points_xyz'])
        writer.writerow([len(contacts), encoded])
        writer.writerow([0, encode_contact_points([])])
        out.seek(0)
        rows = list(csv.DictReader(out))
        self.assertEqual(len(rows), 2)
        self.assertEqual(int(rows[0]['contact_count']), len(json.loads(rows[0]['contact_points_xyz'])))
        self.assertEqual(json.loads(rows[1]['contact_points_xyz']), [])
        for bad in [(1, 2), (1, float('nan'), 3), (0, float('inf'), 3)]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                encode_contact_points([Contact(bad)])

    def test_visual_landing_contrast_preserves_every_non_checker_node(self):
        for seed in (0, 3, 14):
            world = world_text(generate(seed), evaluator=True)
            flat = without_checker_cells(world)
            self.assertEqual(world.count('_CELL_'), 48)
            self.assertNotIn('_CELL_', flat)
            self.assertEqual(
                [line for line in world.splitlines() if '_CELL_' not in line],
                flat.splitlines())
            for marker in ('GP_U_TARGET_1 Pose', 'GP_U_TARGET_2 Pose',
                           'GP_U_TARGET_3 Pose', 'boundingObject',
                           'DEF GP_U_EVALUATOR', 'DEF GP_U_BAND_'):
                self.assertIn(marker, flat)
            with self.assertRaises(RuntimeError):
                without_checker_cells(flat)
            with self.assertRaises(RuntimeError):
                without_checker_cells(world.replace(
                    'DEF GP_U_TARGET_1_CELL_0_0 Pose',
                    'DEF GP_U_TARGET_1_CELL_0_0 Pose boundingObject'))

    def test_bad_inputs_and_nonrepresentable_deadline_step(self):
        for seed in (-1,65536,True,1.5):
            with self.assertRaises(ValueError): generate(seed)
        for length in (1.99,6.1,True,math.nan,2.0001):
            with self.assertRaises(ValueError): generate(0,length)
        self.assertNotEqual(210000 % 32, 0)
        self.assertEqual(210000 % 8, 0)
        self.assertIn('basicTimeStep 8',world_text(generate(0)))


if __name__ == '__main__': unittest.main()
