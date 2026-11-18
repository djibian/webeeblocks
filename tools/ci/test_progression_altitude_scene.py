#!/usr/bin/env python3
"""Static falsification for the independent Activity 2 altitude scene asset.

This intentionally does not claim Webots R2025a contacts, flight feasibility,
scene import/reset safety or pupil acceptance: those require a later native
integration and independent tests. No AST-shape oracle is authorized here.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "worlds/scenes/altitude-v1.wbo"
CRAFT_HALF_SPAN_M = 0.09  # conservative XY margin for safe corridor/pad
# Pinned R2025a Crazyflie.proto: Cylinder boundingObject height 0.030 m,
# z-axis aligned, so the actual native collider half-height is 0.015 m.
CRAFT_NATIVE_HALF_HEIGHT_M = 0.015
NOMINAL_TAKEOFF_M = 0.45


def solid(source: str, name: str):
    pattern = (
        rf"DEF {re.escape(name)} Solid \{{"
        rf"[\s\S]*?translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
        rf"[\s\S]*?boundingObject Box \{{ size ([0-9.]+) ([0-9.]+) ([0-9.]+) \}}"
    )
    match = re.search(pattern, source)
    if match is None:
        raise AssertionError(f"missing physical collider {name}")
    return tuple(map(float, match.groups()))


def assert_visual_box_matches_collider(source: str, name: str) -> None:
    """A2 pupil-visible obstacle and native collision box must coincide in size.

    Fail closed if the direct visual Shape or boundingObject changes form:
    an apparently empty passage must never contain an unseen collider, and
    a painted obstacle must not silently become smaller than its collision.
    """
    marker = f"DEF {name} Solid {{"
    start = source.find(marker)
    if start < 0:
        raise AssertionError(f"missing named native obstacle {name}")
    # Bound the parser to this Solid. Otherwise deleting its visible Shape
    # could accidentally pair the next obstacle's two matching boxes.
    next_solid = source.find("\n    DEF ", start + len(marker))
    block = source[start:next_solid if next_solid >= 0 else len(source)]
    pattern = (
        rf"^DEF {re.escape(name)} Solid \{{"
        r"[\s\S]*?children \[\s*Shape \{"
        r"[\s\S]*?geometry Box \{ size ([0-9.]+) ([0-9.]+) ([0-9.]+) \}"
        r"\s*\}\s*\]\s*boundingObject Box \{ size ([0-9.]+) ([0-9.]+) ([0-9.]+) \}"
    )
    match = re.search(pattern, block)
    if match is None:
        raise AssertionError(f"missing direct visual Box or native collider for {name}")
    visible = tuple(map(float, match.groups()[:3]))
    physical = tuple(map(float, match.groups()[3:]))
    if visible != physical:
        raise AssertionError(
            f"visual/collision mismatch for {name}: visual={visible}, physical={physical}")


class AltitudeSceneStaticProof(unittest.TestCase):
    def setUp(self):
        self.source = SCENE.read_text(encoding="utf-8")

    def test_a2_adds_vertical_without_premature_sensor_or_logic_blocks(self):
        # Guard the cumulative A1 -> A2 learning contract; geometry and
        # success remain decided by Webots native physical observations.
        activity_file = ROOT / "plugins/robot_windows/blockly/webeeblocks/activities.js"
        entries = activity_file.read_text(encoding="utf-8")
        for activity_id in ("progression-sequence-v1", "progression-altitude-v1",
                            "progression-precise-movement-v1"):
            self.assertEqual(entries.count(f"id: '{activity_id}'"), 1)
        first = entries.split("id: 'progression-sequence-v1',", 1)[1].split(
            "id: 'progression-altitude-v1',", 1)[0]
        second = entries.split("id: 'progression-altitude-v1',", 1)[1].split(
            "id: 'progression-precise-movement-v1',", 1)[0]

        # First lesson remains a tiny sequence; second introduces relative up,
        # not sensing, conditional behavior, loops or state variables.
        for block in ("'webeeblocks_v2_takeoff'", "'webeeblocks_v2_move'",
                      "'webeeblocks_v2_land'"):
            self.assertIn(block, first)
            self.assertIn(block, second)
        self.assertNotIn("'webeeblocks_v2_vertical'", first)
        self.assertIn("'webeeblocks_v2_vertical'", second)
        self.assertIn("verticalDirections: [ 'up' ]", second)
        self.assertIn("moveDirections: [ 'forward' ]", second)
        for forbidden in ("'webeeblocks_v2_range'", "'controls_if'",
                          "'controls_repeat_ext'", "'controls_whileUntil'",
                          "'variables_set'", "'variables_get'", "'math_change'"):
            self.assertNotIn(forbidden, second)
        self.assertIn("scene: 'sequence-v1'", first)
        self.assertIn("scene: 'altitude-v1'", second)
        self.assertIn("oracle: 'progression-sequence-3d-v1'", first)
        self.assertIn("oracle: 'progression-altitude-3d-v1'", second)

    def test_isolated_versioned_scene_with_four_explicit_colliders(self):
        self.assertTrue(self.source.startswith("DEF WEBEEBLOCKS_ALTITUDE_SCENE Group {"))
        self.assertEqual(self.source.count(" Pose {"), 18)
        self.assertEqual(self.source.count(" Solid {"), 4)
        self.assertEqual(self.source.count("boundingObject Box"), 4)
        for name in ("ACTIVITY2_START_CANOPY", "ACTIVITY2_LOW_BARRIER", "ACTIVITY2_LEFT_WALL", "ACTIVITY2_RIGHT_WALL"):
            self.assertIn(f"DEF {name} Solid", self.source)
        self.assertNotIn("TouchSensor", self.source)
        self.assertEqual(self.source.count(" Robot {"), 1,
                         "only one dedicated native evaluator may exist")
        self.assertIn('controller "progression_altitude_v1"', self.source)
        self.assertIn("supervisor TRUE", self.source)
        self.assertNotIn('controller "python"', self.source)

    def test_known_low_barrier_forces_vertical_clearance_in_corridor(self):
        x, y, z, sx, sy, sz = solid(self.source, "ACTIVITY2_LOW_BARRIER")
        self.assertAlmostEqual(x, 0.62)
        self.assertAlmostEqual(y, 0.0)
        self.assertAlmostEqual(z + sz / 2, 0.62)
        self.assertGreater(z + sz / 2, NOMINAL_TAKEOFF_M + CRAFT_NATIVE_HALF_HEIGHT_M)
        self.assertLess(z + sz / 2 + CRAFT_NATIVE_HALF_HEIGHT_M, 0.85)
        self.assertLess(sx, 0.20)
        self.assertGreater(sy, 0.6)

        left = solid(self.source, "ACTIVITY2_LEFT_WALL")
        right = solid(self.source, "ACTIVITY2_RIGHT_WALL")
        self.assertAlmostEqual(left[0], right[0])
        self.assertAlmostEqual(left[2], right[2])
        self.assertAlmostEqual(left[1], -right[1])
        self.assertAlmostEqual(left[4], right[4])
        # Remaining gap at either end of the barrier must not allow a
        # body-width horizontal bypass at nominal altitude.
        wall_inner = left[1] - left[4] / 2
        barrier_outer = y + sy / 2
        self.assertGreater(wall_inner, barrier_outer)
        self.assertLess(wall_inner - barrier_outer, CRAFT_HALF_SPAN_M)
        self.assertGreater(left[5], sz)

    def test_relative_ascent_is_needed_for_every_feasible_takeoff_height(self):
        # A constant-height A1-style path must not solve A2 simply by
        # selecting a larger takeoff value. The real craft has finite size:
        # it must leave the start *below* the canopy, yet traverse the
        # corridor *above* the physical barrier. No Blockly syntax is tested.
        canopy = solid(self.source, "ACTIVITY2_START_CANOPY")
        barrier = solid(self.source, "ACTIVITY2_LOW_BARRIER")
        canopy_bottom = canopy[2] - canopy[5] / 2
        barrier_top = barrier[2] + barrier[5] / 2
        highest_clear_start = canopy_bottom - CRAFT_NATIVE_HALF_HEIGHT_M
        lowest_clear_crossing = barrier_top + CRAFT_NATIVE_HALF_HEIGHT_M

        self.assertAlmostEqual(highest_clear_start, 0.565)
        self.assertAlmostEqual(lowest_clear_crossing, 0.635)
        self.assertGreater(lowest_clear_crossing - highest_clear_start, 0.06)
        # Both physical height bands intersect the profile's general
        # 0.4..0.8 m takeoff range. The distinction is geometric, not an
        # arbitrary AST ban on high takeoff.
        self.assertGreater(highest_clear_start, 0.4)
        self.assertLess(lowest_clear_crossing, 0.8)

        # There is physical room to climb between clearing the canopy
        # and encountering the barrier. Otherwise we would prove only an
        # impossible exercise rather than a meaningful new learning goal.
        canopy_exit = canopy[0] + canopy[3] / 2 + CRAFT_HALF_SPAN_M
        barrier_entry = barrier[0] - barrier[3] / 2 - CRAFT_HALF_SPAN_M
        self.assertGreater(barrier_entry - canopy_exit, 0.15)

    def test_start_canopy_blocks_high_takeoff_but_leaves_a_climb_window(self):
        canopy = solid(self.source, "ACTIVITY2_START_CANOPY")
        barrier = solid(self.source, "ACTIVITY2_LOW_BARRIER")
        left = solid(self.source, "ACTIVITY2_LEFT_WALL")
        # The learner may launch low under the canopy; a launch at 0.80 m
        # would intersect its native Box in the departure footprint.
        cx, cy, cz, w, depth, height = canopy
        lower = cz - height / 2
        upper = cz + height / 2
        self.assertAlmostEqual((cx, cy, cz)[0], 0.0)
        self.assertAlmostEqual(cy, 0.0)
        self.assertAlmostEqual(lower, 0.58)
        self.assertAlmostEqual(upper, 0.66)
        self.assertGreater(lower - (NOMINAL_TAKEOFF_M + CRAFT_NATIVE_HALF_HEIGHT_M), 0.08)
        self.assertLess(lower, 0.80)
        self.assertGreater(cx + w / 2, 0.0)
        self.assertGreater(depth / 2, 0.4)
        # Escape forward first, then ascend *before* entering the barrier
        # envelope: the interval must be positive, not an AST requirement.
        canopy_clear_x = cx + w / 2 + CRAFT_HALF_SPAN_M
        barrier_first_x = barrier[0] - barrier[3] / 2 - CRAFT_HALF_SPAN_M
        self.assertGreater(barrier_first_x - canopy_clear_x, 0.15)
        # Lateral detours through the small slit beside the roof must
        # remain narrower than the conservative footprint.
        wall_inner = left[1] - left[4] / 2
        roof_outer = cy + depth / 2
        self.assertGreater(wall_inner, roof_outer)
        self.assertLess(wall_inner - roof_outer, CRAFT_HALF_SPAN_M)


    def test_visible_obstacle_boxes_match_native_colliders(self):
        # Earlier geometry tests checked collision boxes only. A change to
        # visible Box dimensions alone would mislead A2 pupils, even while
        # the mission oracle and all four physical obstacle checks still pass.
        names = (
            "ACTIVITY2_START_CANOPY", "ACTIVITY2_LOW_BARRIER",
            "ACTIVITY2_LEFT_WALL", "ACTIVITY2_RIGHT_WALL",
        )
        for name in names:
            with self.subTest(obstacle=name):
                assert_visual_box_matches_collider(self.source, name)
                # Deliberately corrupt just the first *visual* dimension,
                # leaving boundingObject untouched. The guard must reject it.
                marker = re.search(
                    rf"(DEF {re.escape(name)} Solid \{{[\s\S]*?geometry Box \{{ size )([0-9.]+)",
                    self.source)
                self.assertIsNotNone(marker)
                mutated = (
                    self.source[:marker.start(2)] +
                    f"{float(marker.group(2)) + 0.01:.3f}" +
                    self.source[marker.end(2):]
                )
                with self.assertRaisesRegex(AssertionError, "visual/collision mismatch"):
                    assert_visual_box_matches_collider(mutated, name)

    def test_start_and_target_are_separate_noncolliding_marks(self):
        self.assertIn("Pose { translation 0 0 0.002", self.source)
        self.assertRegex(self.source, r"Pose \{ translation 1\.35 0 0\.002[\s\S]*?size 0\.34 0\.34 0\.004")
        self.assertEqual(self.source.count("0.0042 children"), 16)
        # Landing zone is beyond the barrier's far face and body clearance.
        barrier = solid(self.source, "ACTIVITY2_LOW_BARRIER")
        self.assertGreater(1.35 - 0.34 / 2, barrier[0] + barrier[3] / 2 + CRAFT_HALF_SPAN_M)


if __name__ == "__main__":
    unittest.main()
