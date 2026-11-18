#!/usr/bin/env python3
"""A6-B second PRIVATE holdout: challenge fixed coordinates AND 8-cm sampling.

These source-only tests do NOT demonstrate real Multi-ranger detectability,
a pilot's stop error, motorized traversal, a pupil PASS or native mission
success. Keep the oracle and original student-facing scenes unchanged.
"""
from __future__ import annotations

from pathlib import Path
import unittest

from tools.ci.test_a6_b_matched_tail_geometry import (
    FIXTURES, ROOT, OLD, EXPECTED, gate_centres, validate_scene,
)

SECOND = {
    1: (0.48,),
    2: (-0.80, 0.48),
    3: (-0.80, -0.16, 0.48),
}
# Exact historic checkpoints that succeeded without a state variable
# on the public A6 experiment; first family had its own two candidate spots.
CLASSIFIER_POSTS = (0.0, 0.85, -0.85, -0.31)
TAKEOFF_X = -1.40
GATE_HALF_X = 0.035


def ideal_lattice_error(x, step):
    # Exact arithmetic is confined to a static falsification model.
    # A real 3D Multi-ranger beam/PID may behave differently.
    steps = (x - TAKEOFF_X) / step
    return abs(x - (TAKEOFF_X + round(steps) * step))


class A6SecondSamplingHoldout(unittest.TestCase):
    def test_six_holdouts_have_shared_tails_and_true_collision_volumes(self):
        for n in (1, 2, 3):
            with self.subTest(variant=n):
                initial = (FIXTURES / f"count-h-{n}-matched-tail-private.wbo"
                           ).read_text(encoding="utf-8")
                alternate = (FIXTURES /
                             f"count-h-{n}-sampling-holdout-private.wbo"
                             ).read_text(encoding="utf-8")
                validate_scene(initial, n)
                validate_scene(
                    alternate, n, expected_positions=SECOND[n],
                    checked_checkpoints=CLASSIFIER_POSTS,
                    terminal_h=0.48,
                )
                self.assertIn("PRIVATE A6 CHOICE B", alternate)
                self.assertIn("SAMPLING HOLDOUT", alternate)
                self.assertEqual(gate_centres(initial, n), EXPECTED[n])
                self.assertEqual(gate_centres(alternate, n), SECOND[n])
                self.assertNotEqual(gate_centres(initial, n)[-1],
                                    gate_centres(alternate, n)[-1])
                self.assertEqual(len(gate_centres(alternate, n)), n)
                # Preserve student-facing original variant unchanged.
                original = (ROOT / f"worlds/scenes/count-h-{n}-v1.wbo"
                            ).read_text(encoding="utf-8")
                self.assertEqual(gate_centres(original, n), OLD[n])

    def test_two_families_defeat_the_same_hardcoded_gate_posts(self):
        for n in SECOND:
            with self.subTest(n=n):
                for x in SECOND[n]:
                    self.assertTrue(all(abs(x-post) > GATE_HALF_X
                                        for post in CLASSIFIER_POSTS))
                self.assertGreaterEqual(
                    min((right-left for left, right in
                         zip(SECOND[n], SECOND[n][1:])), default=10),
                    .50,
                )

    def test_ideal_8cm_lattice_can_miss_all_second_family_h(self):
        # Every second-family H is exactly in the middle of two 8-cm
        # nominal sample positions: 4.0 cm > 3.5-cm longitudinal half-box.
        # In contrast, the 4-cm lattice hits each nominal centre exactly.
        for n, xs in SECOND.items():
            for gate_x in xs:
                with self.subTest(n=n, x=gate_x):
                    self.assertAlmostEqual(
                        ideal_lattice_error(gate_x, .08), .04, places=8)
                    self.assertGreater(
                        ideal_lattice_error(gate_x, .08), GATE_HALF_X)
                    self.assertAlmostEqual(
                        ideal_lattice_error(gate_x, .04), 0., places=8)
        self.assertLess(.04, .08)
        # This is a discrete point-ray bound, NOT an observation of Webots.

    def test_negative_mutants_fail_even_in_second_family(self):
        original = (
            FIXTURES / "count-h-3-sampling-holdout-private.wbo"
        ).read_text(encoding="utf-8")
        mutations = (
            ("translation -0.160 0 0.74", "translation 0.000 0 0.74"),
            ("boundingObject Box { size 0.07 0.57 0.24 }",
             "boundingObject Box { size 0.07 0.57 0.00 }"),
            ("boundingObject Box { size 0.07 1.48 0.24 }",
             "boundingObject Box { size 0.07 1.48 0.00 }"),
            ("geometry Box { size 0.06 1.48 1.10 }",
             "geometry Box { size 0.06 1.48 0.00 }"),
        )
        for before, after in mutations:
            with self.subTest(mutant=before):
                self.assertIn(before, original)
                broken = original.replace(before, after, 1)
                self.assertNotEqual(broken, original)
                with self.assertRaises(AssertionError):
                    validate_scene(
                        broken, 3, expected_positions=SECOND[3],
                        checked_checkpoints=CLASSIFIER_POSTS,
                        terminal_h=0.48,
                    )


if __name__ == "__main__":
    unittest.main()
