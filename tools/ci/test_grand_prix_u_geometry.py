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
            self.assertEqual(layout.polygon, first.polygon)
            self.assertEqual(layout.final_gates, first.final_gates)
            self.assertTrue(1 <= len(layout.gates) <= 3)
            self.assertEqual(len({g.side for g in layout.gates}), len(layout.gates))
            seen.add(len(layout.gates))
            # All pre-terminal colliders retain their full upper envelope;
            # only the deliberately visible terminal H crossbar ends lower.
            for b in layout.boxes[:-4]:
                self.assertAlmostEqual(b.z+b.sz/2, 1.3)
            for b in (layout.gate_boxes[-4], layout.gate_boxes[-3],
                      layout.gate_boxes[-1]):
                self.assertAlmostEqual(b.z+b.sz/2, 1.3)
            self.assertAlmostEqual(layout.gate_boxes[-2].z+layout.gate_boxes[-2].sz/2, .81)
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
        terminal = layout.gate_boxes[-4:]
        self.assertEqual(len(terminal), 4)
        self.assertEqual([round(b.y-layout.side,2) for b in terminal],
                         [-.87,.87,0.,0.])
        # Whole-width closure remains physical at low, normal and high flight
        # altitudes: making an H silhouette must never open a bypass.
        for z in (.10, .40, .75, 1.20):
            for y_mm in range(1100,2901,10):
                self.assertLess(min(gap((0.,y_mm/1000,z),b) for b in terminal),
                                RADIUS)
        world = world_text(layout)
        boxes = [line for line in world.splitlines()
                 if line.startswith('DEF GP_U_BOX_')]
        self.assertEqual(len(boxes), len(layout.boxes))
        self.assertTrue(all('boundingObject Box' in line for line in boxes))
        self.assertEqual(sum('transparency .65' in line for line in boxes), 1)
        self.assertIn('transparency .65', boxes[-1])
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
