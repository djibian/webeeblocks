"""Read-only composition checks for the minimal Grand Prix pilot candidate.

These tests do NOT assert a physical simulation PASS or authorize CI Gate.
All real dynamic claims require native R2025a and independent V5 review.
"""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

from tools.grand_prix.prepare_u_runtime import prepare
from tools.grand_prix.route_vertical_product import compose_route_vertical_product


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"


def margin(vz: float, upward_m: float) -> float:
    positive = max(0.0, vz)
    return (0.095 + 0.30 * upward_m if upward_m > 0 else 0.080) + (
        0.064 * positive + positive ** 2 / 0.50)


class RouteVerticalProductTests(unittest.TestCase):
    def test_only_route_generated_composition(self):
        original_sha = hashlib.sha256(SHARED.read_bytes()).hexdigest()
        with TemporaryDirectory() as temp:
            route = Path(temp) / "route"
            legacy = Path(temp) / "legacy"
            prepare(output_dir=route, legacy_worlds=False, route_observations=True)
            prepare(output_dir=legacy, legacy_worlds=False, route_observations=False)
            flight = (route / "runtime_u.c").read_text()
            unchanged = (legacy / "runtime_u.c").read_text()
        self.assertEqual(hashlib.sha256(SHARED.read_bytes()).hexdigest(),
                         original_sha, "shared original C must not be changed")
        self.assertNotIn("GP_CEILING_PREFLIGHT_V1", unchanged)
        self.assertNotIn("gp_route_upward_headroom(", unchanged)
        self.assertNotIn("gp_land_contact_since", unchanged)
        self.assertIn("land_touchdown && gp_land_contact_since >= 0.0", flight)
        self.assertIn("now - gp_land_contact_since >= STOP_WINDOW", flight)
        self.assertIn("if (!gp_contact_now) gp_land_contact_since = -1.0", flight)
        for marker in (
            "GP_CEILING_PREFLIGHT_V1 command=TAKEOFF",
            "GP_CEILING_PREFLIGHT_V1 command=VERTICAL",
            "gp_route_upward_headroom(vz, request.value)",
            "gp_route_takeoff_next(&gp_route_takeoff,",
            "gp_u_deadline(now, gp_pose_confirmed)",
            "gp_route_observe_native(",
            "if (command == CMD_LAND && land_touchdown)",
        ):
            self.assertIn(marker, flight)
        self.assertEqual(flight.count('const double corrected_u = 55.368085898'), 1)
        self.assertNotIn("all_active_vertical_up_governed", flight)
        self.assertEqual(flight.count('GP_CEILING_PREFLIGHT_V1 command='), 2)
        # The legacy U retains its single monolithic controller call. The
        # route pilot now has one cascade, with one call to each PID and mixer.
        self.assertEqual(unchanged.count('pid_velocity_fixed_height_controller(actual,'), 1)
        self.assertNotIn('gp_multirate_pid(', unchanged)
        self.assertNotIn('pid_velocity_fixed_height_controller(actual,', flight)
        self.assertEqual(flight.count('gp_multirate_pid(&gp_xy,'), 1)
        calls = (
            'pid_horizontal_velocity_controller(actual, desired, gains, elapsed);',
            'pid_fixed_height_controller(actual, desired, gains, dt, &commands);',
            'pid_attitude_controller(actual, desired, gains, dt, &commands);',
            'motor_mixing(commands, power);',
        )
        for call in calls:
            self.assertEqual(flight.count(call), 1)
        positions = [flight.index(call) for call in calls]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('command == CMD_LAND || command == CMD_TAKEOFF || failsafe_latched, &power);', flight)
        # The TAKEOFF refusal must be truly side-effect-free, not the late
        # experimental refusal after active_id had already been assigned.
        takeoff = flight.split("if (request.kind == REQUEST_TAKEOFF) {", 1)[1].split(
            "if (request.kind == REQUEST_MOVE) {", 1)[0]
        self.assertLess(takeoff.index('code=INVALID_TAKEOFF'),
                        takeoff.index("active_id = request.id;"))
        vertical = flight.split("if (request.kind == REQUEST_VERTICAL) {", 1)[1].split(
            "if (request.kind == REQUEST_TURN) {", 1)[0]
        self.assertLess(vertical.index('code=VERTICAL_LIMIT'),
                        vertical.index("active_id = request.id;"))
        self.assertTrue('CMD_LAND' in flight and 'land_touchdown' in flight)
        # Inspect the complete generated control ordering, not a hand-written
        # approximation of the route state machine.
        early = flight.index('if (command == CMD_LAND && !land_touchdown && land_has_ground_contact')
        self.assertLess(early, flight.index('if (gp_u_deadline(now, gp_pose_confirmed))'))
        self.assertLess(early, flight.index('if (request.kind == REQUEST_STOP)'))
        self.assertIn('if (land_touchdown) {\n      // Latch through loss of contact', flight)
        self.assertIn('if (active_id >= 1 && now - stable_since >= STOP_WINDOW', flight)
        self.assertIn('if (command == CMD_LAND && active_id != 2147483646)', flight)
        self.assertIn('if (active_id >= 1) gp_route_stop_land();', flight)
        self.assertEqual(flight.count('land_touchdown = 0;'), 3)
        self.assertIn('land_touchdown = 0; /* Qualified RESET only. */', flight)
        self.assertIn('land_touchdown = 0; /* New admitted TAKEOFF only. */', flight)
        self.assertNotIn('gp_route_stop_land(', unchanged)
        self.assertNotIn('if (land_touchdown) {\n      // Latch through loss of contact', unchanged)

    def test_fail_closed_on_changed_source(self):
        with self.assertRaises(RuntimeError):
            compose_route_vertical_product("fake arbitrary C")
        with TemporaryDirectory() as temp:
            route = Path(temp) / "route"
            prepare(output_dir=route, legacy_worlds=False, route_observations=True)
            source = (route / "runtime_u.c").read_text()
        with self.assertRaises(RuntimeError):
            compose_route_vertical_product(source)

    def test_margin_is_monotone_and_preserves_takeoff(self):
        for amplitude in (0.1, 0.2, 0.3, 0.5):
            values = [margin(v, amplitude) for v in (-.10, 0, .04, .10, .14)]
            self.assertEqual(values, sorted(values))
        for vz in (-.1, 0, .08, .13):
            values = [margin(vz, dz) for dz in (.1, .2, .3, .5)]
            self.assertEqual(values, sorted(values))
        self.assertAlmostEqual(margin(0, 0), .080)
        self.assertAlmostEqual(margin(0, .1), .125)
        self.assertAlmostEqual(margin(0, .3), .185)
        self.assertAlmostEqual(margin(.1, .1), .1514)
        self.assertAlmostEqual(margin(.2, .1), .2178)
        self.assertTrue(1.056789215 + .1 > 1.164995095 - margin(-.03378, .1))
        self.assertTrue(.837186283 + .3 > 1.164995095 - margin(-.04979, .3))


if __name__ == "__main__":
    unittest.main()
