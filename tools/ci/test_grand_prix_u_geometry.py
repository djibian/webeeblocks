"""Geometric counterexamples, independent of any reference solution."""
import dataclasses
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.grand_prix.layout_u import generate, world_text, local, RADIUS


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
            # Corridor limits are tape, not colliding wall solids. The
            # lateral lines continue the two H side posts at +/- 0.30 m.
            self.assertEqual(layout.walls, ())
            self.assertAlmostEqual(layout.width, .60)
            self.assertAlmostEqual(layout.polygon[0][1], -layout.width/2)
            self.assertAlmostEqual(layout.polygon[-1][1], layout.width/2)
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
            red_dashes = [line for line in text.splitlines()
                           if line.startswith('DEF GP_U_BOUNDARY_')]
            self.assertGreater(len(red_dashes), 30)
            self.assertTrue(all(' Pose {' in line and
                                'boundingObject' not in line and
                                'baseColor .95 .06 .06' in line
                                for line in red_dashes))
            # The only physical boxes are gates, including the terminal H.
            self.assertEqual(text.count('DEF GP_U_BOX_'), len(layout.gate_boxes))
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

    def test_bad_inputs_and_nonrepresentable_deadline_step(self):
        for seed in (-1,65536,True,1.5):
            with self.assertRaises(ValueError): generate(seed)
        for length in (1.99,6.1,True,math.nan,2.0001):
            with self.assertRaises(ValueError): generate(0,length)
        self.assertNotEqual(210000 % 32, 0)
        self.assertEqual(210000 % 8, 0)
        self.assertIn('basicTimeStep 8',world_text(generate(0)))


if __name__ == '__main__': unittest.main()
