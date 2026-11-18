#!/usr/bin/env python3
"""A6 choice B — private geometry-only falsification of fixed checkpoints.

Fixtures are intentionally NON-PRODUCT .wbo files. This proves only their
static collider coordinates and common terminal geometry, not that R2025a
Multi-ranger rays, real flight, Blockly or the native oracle pass. NEVER claim
mission readiness from this test. Keep the current A6 product scenes intact.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tools/ci/fixtures/a6-b"
EXPECTED = {
    1: (0.36,),
    2: (-0.85, 0.36),
    3: (-0.85, -0.31, 0.36),
}
OLD = {1: (-0.85,), 2: (-0.85, 0.0), 3: (-0.85, 0.0, 0.85)}
PARTS = ("LEFT", "RIGHT", "BAR")
# Exact two posts exploited by the physically successful zero-variable
# private Blockly candidate on the OLD three scenes; not a theorem about
# every sensor pose or a prohibition on conditional branches.
OLD_CHECKPOINTS = (0.0, 0.85)
GATE_X_HALF = 0.035
CRAFT_MARGIN = 0.090


def gate_centres(source: str, count: int) -> tuple[float, ...]:
    centres = []
    for i in range(1, count + 1):
        xs = []
        for part in PARTS:
            pattern = (
                rf"DEF ACTIVITY6_{count}_H_{i}_{part} Solid \{{\s*"
                rf"translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
            )
            match = re.search(pattern, source)
            if not match:
                raise AssertionError(f"missing true H collider n={count} i={i} {part}")
            x, y, z = map(float, match.groups())
            if abs(y - (0.0 if part == "BAR" else
                        0.3 if part == "LEFT" else -0.3)) > 1e-9:
                raise AssertionError("H pillar shifted laterally")
            if abs(z - (0.74 if part == "BAR" else 0.50)) > 1e-9:
                raise AssertionError("H height altered")
            xs.append(x)
        if max(xs) - min(xs) > 1e-9:
            raise AssertionError(f"the three pieces of H{i} do not coincide")
        centres.append(xs[0])
    return tuple(centres)


def validate_scene(source: str, count: int) -> None:
    xs = gate_centres(source, count)
    expected = EXPECTED[count]
    if any(abs(a - b) > 1e-8 for a, b in zip(xs, expected)):
        raise AssertionError(f"unexpected H positions n={count}: {xs}")
    if len(xs) != count or any(b - a < 0.50
                               for a, b in zip(xs, xs[1:])):
        raise AssertionError("incorrect cardinality/order/gate separation")
    if xs[0] <= -1.40 + 0.20:
        raise AssertionError("first H too close to blue takeoff origin")
    if xs[-1] + GATE_X_HALF + CRAFT_MARGIN + 0.30 >= 1.235:
        raise AssertionError("last H too close to cyan terminal screen")
    if source.count(" Solid {") != count * 3 + 2:
        raise AssertionError("missing or extra collision solids")
    if source.count("boundingObject Box") != count * 3 + 2:
        raise AssertionError("a collision box vanished")
    if source.count("0.0042 children") != 12:
        raise AssertionError("all three checkerboard landings must be present")
    for y in (0.0, 0.55, -0.55):
        if f"Pose {{ translation 1.48 {y:.3f} 0.002" not in source:
            raise AssertionError("one destination disappeared")
    if not re.search(
        rf"DEF ACTIVITY6_{count}_FINISH_SCREEN Solid \{{\s*"
        r"translation 1\.235 0 0\.76", source,
    ):
        raise AssertionError("common terminal occlusion moved")
    if not re.search(
        rf"DEF ACTIVITY6_{count}_TERMINAL Solid \{{\s*"
        r"translation 1\.86 0 0\.55", source,
    ):
        raise AssertionError("shared terminal marker moved")
    # Confirm true collision volumes, not merely the number of named solids.
    # In particular a zero-thickness BAR must fail a negative mutation.
    for i in range(1, count + 1):
        for part in PARTS:
            key = f"ACTIVITY6_{count}_H_{i}_{part}"
            match = re.search(
                rf"DEF {key} Solid \\{{[\\s\\S]*?boundingObject Box "
                rf"\\{{ size ([0-9.]+) ([0-9.]+) ([0-9.]+) \\}}",
                source,
            )
            if not match:
                raise AssertionError(f"missing collision box for {key}")
            expected_box = ((0.07, 0.57, 0.24) if part == "BAR"
                            else (0.07, 0.065, 1.00))
            if tuple(map(float, match.groups())) != expected_box:
                raise AssertionError(f"invalid collision volume for {key}")
    for checkpoint in OLD_CHECKPOINTS:
        if any(abs(gate - checkpoint) <= 0.13 for gate in xs):
            raise AssertionError(
                f"old physical classifier checkpoint {checkpoint} still matches H"
            )
    # All scenes finish under the same last H. Varying gate count changes
    # the earlier route, NOT the arrival geometry / final H's presence.
    if abs(xs[-1] - 0.36) > 1e-9:
        raise AssertionError("the common final H is not at x=0.36")


class MatchedTailDesignBTests(unittest.TestCase):
    def test_all_three_private_holdout_worlds_preserve_physical_structure(self):
        for n in EXPECTED:
            with self.subTest(n=n):
                file = FIXTURES / f"count-h-{n}-matched-tail-private.wbo"
                content = file.read_text(encoding="utf-8")
                self.assertIn("PRIVATE A6 CHOICE B", content)
                validate_scene(content, n)

    def test_product_scenes_stay_original_and_not_replaced_by_fixtures(self):
        for n in EXPECTED:
            with self.subTest(n=n):
                real = (ROOT / f"worlds/scenes/count-h-{n}-v1.wbo"
                        ).read_text(encoding="utf-8")
                self.assertEqual(gate_centres(real, n), OLD[n])
                self.assertNotIn("PRIVATE A6 CHOICE B", real)

    def test_adversarial_geometry_changes_fail_closed(self):
        original = (FIXTURES / "count-h-3-matched-tail-private.wbo"
                    ).read_text(encoding="utf-8")
        for damaged in (
            original.replace(
                "translation -0.310 0 0.74",
                "translation 0.000 0 0.74", 1),
            original.replace(
                "boundingObject Box { size 0.07 0.57 0.24 }",
                "boundingObject Box { size 0.07 0.57 0.00 }", 1),
            original.replace(
                "translation 1.86 0 0.55",
                "translation 1.95 0 0.55", 1),
        ):
            with self.subTest(mutant=damaged.count(" Solid {")):
                with self.assertRaises(AssertionError):
                    validate_scene(damaged, 3)

    def test_information_scope_is_not_a_universal_memory_proof(self):
        # The experiment only kills the two previous sample points;
        # an adversary can always devise another decision tree for finitely
        # many known worlds. No compulsory variables_set AST rule is allowed.
        self.assertEqual(OLD_CHECKPOINTS, (0.0, 0.85))
        self.assertEqual([len(x) for x in EXPECTED.values()], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
