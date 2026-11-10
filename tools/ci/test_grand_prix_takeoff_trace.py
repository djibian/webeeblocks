"""Pure analyzer and route-isolation tests; NO native Webots flight oracle."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ANALYZER_PATH = ROOT / "tools/grand_prix/analyze_takeoff_trace.py"
SPEC = importlib.util.spec_from_file_location("analyze_takeoff_trace", ANALYZER_PATH)
assert SPEC is not None and SPEC.loader is not None
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def sample(t, z, vz, *, target=.815, reference=.815, phase="takeoff"):
    err = reference - z
    p = 10 * err
    i = 4.0
    d = 0.0
    u = 48.0 + p + i + d
    return (f"GP_ROUTE_TAKEOFF_TRACE_SAMPLE id=2 t={t:.6f} dt=.032000 "
            f"z0=.015000000 z={z:.9f} vz={vz:.9f} ref={reference:.9f} "
            f"target={target:.9f} error={err:.9f} p={p:.9f} i={i:.9f} "
            f"d={d:.9f} u={u:.9f} m1={-u:.9f} m2={u:.9f} "
            f"m3={-u:.9f} m4={u:.9f} phase={phase}")


class TestReadOnlyTelemetry(unittest.TestCase):
    def test_observed_overshoot_is_measured_not_assumed(self):
        lines = ["GP_ROUTE_TAKEOFF_TRACE_BEGIN id=2 t=1.000000 z0=.015 target=.815"]
        lines += [sample(1 + .032 * k, .015 + .0005 * k, .02) for k in range(20)]
        lines += [sample(1.640, .900, .502),  # exceeding request and still ascending
                  "GP_ROUTE_TAKEOFF_TRACE_ACK id=2 t=1.672000"]
        result = a.summarize(a.parse_lines(lines)[0])
        self.assertEqual(result["status"], "TRACE_WITH_ACK")
        self.assertAlmostEqual(result["maximum_observed_overshoot_m"], .085)
        self.assertAlmostEqual(result["max_observed_upward_speed_m_s"], .502)
        self.assertIsNone(result["first_vertical_stability_window_elapsed_s"])
        self.assertFalse(result["complete_3d_ack_guaranteed_by_this_trace"])

    def test_missing_ack_is_censored_not_success(self):
        lines = ["GP_ROUTE_TAKEOFF_TRACE_BEGIN id=2 t=0 z0=.015 target=.815",
                 sample(.032, .015, 0)]
        result = a.summarize(a.parse_lines(lines)[0])
        self.assertEqual(result["status"], "TRACE_CENSORED_NO_ACK")
        self.assertIsNone(result["takeoff_ack_elapsed_s"])
        self.assertIsNone(result["first_lift_2cm_proxy_elapsed_s"])

    def test_first_lift_is_only_an_elevation_proxy(self):
        lines = ["GP_ROUTE_TAKEOFF_TRACE_BEGIN id=2 t=0 z0=.015 target=.815",
                 sample(.032, .015, 0),
                 sample(.064, .036, .065)]
        result = a.summarize(a.parse_lines(lines)[0])
        self.assertEqual(result["first_lift_2cm_proxy_elapsed_s"], .064)
        self.assertIsNone(result["first_vertical_stability_window_elapsed_s"])

    def test_invalid_native_samples_fail_closed(self):
        lines = ["GP_ROUTE_TAKEOFF_TRACE_BEGIN id=2 t=0 z0=.015 target=.815",
                 sample(.032, .015, 0).replace("vz=0.000000000", "vz=nan")]
        with self.assertRaisesRegex(a.TraceError, "non-finite vz"):
            a.parse_lines(lines)
        with self.assertRaisesRegex(a.TraceError, "without matching BEGIN"):
            a.parse_lines([sample(.032, .015, 0)])
        with self.assertRaisesRegex(a.TraceError, "duplicate"):
            a.parse_lines([lines[0], lines[0]])

    def test_reference_trajectory_is_not_a_native_physics_test(self):
        from tools.grand_prix.prepare_u_runtime import prepare
        with tempfile.TemporaryDirectory() as td:
            route = Path(td) / "route"
            historical = Path(td) / "u"
            prepare(route, route_observations=True, legacy_worlds=False)
            prepare(historical, route_observations=False, legacy_worlds=False)
            route_source = (route / "runtime_u.c").read_text()
            historical_source = (historical / "runtime_u.c").read_text()
            self.assertEqual(route_source.count("gp_route_takeoff_trace_sample(now"), 1)
            self.assertIn('gp_route_takeoff_trace_begin(request.id, now', route_source)
            self.assertIn("#include \"../gp_route_takeoff_trace.h\"", route_source)
            self.assertNotIn("gp_route_takeoff_trace", historical_source)
            self.assertIn("gp_u_deadline(now, gp_pose_confirmed)", route_source)
            self.assertIn("gp_u_reset_complete()", route_source)

    def test_header_compiles_in_isolation_not_a_webots_proof(self):
        cc = "cc"
        source = r'''
#include <stddef.h>
typedef struct {double kp_z, ki_z, kd_z;} gains_pid_t;
typedef struct {double m1, m2, m3, m4;} motor_power_t;
#include "controllers/grand_prix_route_flight/gp_route_takeoff_trace.h"
double pastAltitudeError = 0.0, altitudeIntegrator = 0.0;
int main(void) {
  gains_pid_t gains = {10,5,5};
  motor_power_t power = {48,48,48,48};
  gp_route_takeoff_trace_begin(2, 1.0, .015, .815);
  gp_route_takeoff_trace_sample(1.032, .032, .015, 0, .0151,
                               .815, 0, gains, power, 1, 0);
  gp_route_takeoff_trace_complete(1.064);
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as td:
            src, exe = Path(td) / "probe.c", Path(td) / "probe"
            src.write_text(source)
            cmd = [cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                   "-I", str(ROOT), str(src), "-lm", "-o", str(exe)]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            run = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
            self.assertEqual(run.stdout, "")


if __name__ == "__main__":
    unittest.main()
