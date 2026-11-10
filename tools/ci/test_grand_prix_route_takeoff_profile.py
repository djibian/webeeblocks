"""C-level fail-closed trajectory contract; not native Webots flight proof."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

C_PROBE = r'''
#include <math.h>
#include <assert.h>
#include <stdio.h>
#include "controllers/grand_prix_route_flight/gp_route_takeoff_profile.h"

static void valid_target(double height) {
  const double origin = .015;
  const double target = origin + height;
  gp_route_takeoff_profile_t profile;
  gp_route_takeoff_begin(&profile, origin);
  double z = origin;
  double vz = 0.0;
  double last_reference = origin;
  double last_speed = 0.0;
  const double dt = .032;
  int complete = 0;
  for (int tick = 0; tick < 850; ++tick) {
    const double reference = gp_route_takeoff_next(&profile,target,z,vz,dt);
    assert(isfinite(reference));
    assert(reference >= last_reference - 1e-12);
    assert(reference <= target + 1e-12);
    assert(profile.speed >= -1e-12 && profile.speed <= .32+1e-12);
    assert(fabs(profile.speed-last_speed) <= .55*dt+1e-10);
    if (reference >= target-0.002) complete = 1;
    // Conservative synthetic first-order tracking, not a Webots model.
    const double nextvz = .7*(reference-z) + .85*vz;
    vz = nextvz;
    z += vz*dt;
    last_speed = profile.speed;
    last_reference = reference;
  }
  assert(complete);
  assert(fabs(profile.reference_z-target) <= .002);
}

int main(void) {
  for (int i = 2; i <= 11; ++i) valid_target(i*.1);
  valid_target(.25); valid_target(.8); valid_target(1.15);
  gp_route_takeoff_profile_t profile;
  gp_route_takeoff_begin(&profile,.015);
  double r0=gp_route_takeoff_next(&profile,.815,.015,0,.032);
  assert(r0 > .015 && r0 < .016); // no initial 0.8m PID setpoint step
  assert(!isfinite(gp_route_takeoff_next(&profile,.815,NAN,0,.032)));
  assert(!isfinite(gp_route_takeoff_next(&profile,.815,.015,0,0)));
  assert(!isfinite(gp_route_takeoff_next(&profile,.815,.015,0,.064)));
  gp_route_takeoff_begin(&profile,.015);
  assert(fabs(profile.speed)<1e-12 && fabs(profile.reference_z-.015)<1e-12);
  // A large measured upward velocity must request braking earlier than rest.
  gp_route_takeoff_profile_t fast, slow;
  gp_route_takeoff_begin(&fast,.015);
  gp_route_takeoff_begin(&slow,.015);
  for(int i=0;i<15;i++) {
    gp_route_takeoff_next(&fast,.815,.015,.9,.032);
    gp_route_takeoff_next(&slow,.815,.015,0,.032);
  }
  assert(fast.reference_z < slow.reference_z);
  printf("PASS route-only continuous ascent reference (host C, not Webots)\n");
}
'''


class TestRouteTakeoffProfile(unittest.TestCase):
    def test_compiled_reference_for_variable_targets(self):
        with tempfile.TemporaryDirectory() as td:
            src, exe = Path(td) / 'probe.c', Path(td) / 'probe'
            src.write_text(C_PROBE, encoding='utf-8')
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT), str(src), '-lm', '-o', str(exe)],
                           check=True, capture_output=True, text=True)
            p = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
            self.assertIn('PASS route-only', p.stdout)

    def test_route_only_native_composition_and_historical_u_unchanged(self):
        from tools.grand_prix.prepare_u_runtime import prepare
        with tempfile.TemporaryDirectory() as td:
            route, historical = Path(td) / 'route', Path(td) / 'historical'
            prepare(route, route_observations=True, legacy_worlds=False)
            prepare(historical, route_observations=False, legacy_worlds=False)
            route_source = (route / 'runtime_u.c').read_text()
            u_source = (historical / 'runtime_u.c').read_text()
            self.assertIn('gp_route_takeoff_next(&gp_route_takeoff', route_source)
            self.assertIn('gp_route_takeoff_begin(&gp_route_takeoff, z)', route_source)
            self.assertNotIn('gp_route_takeoff_next', u_source)
            self.assertNotIn('gp_route_takeoff_profile.h', u_source)
            self.assertIn('desired.altitude = target_z;', u_source)
            # Safety/failsafe/deadline structure stays in both compositions.
            for source in (route_source, u_source):
                self.assertIn('gp_u_deadline(now, gp_pose_confirmed)', source)
                self.assertIn('GP_U_LAND_GROUND_READY', source)
                self.assertIn('gp_u_reset_complete()', source)
            self.assertIn('wb_robot_step(gp_u_next_step(step))', route_source)


if __name__ == '__main__':
    unittest.main()
