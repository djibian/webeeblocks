#!/usr/bin/env python3
"""Native C, not Python-emulated, adversarial tests for Activity 3."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/"controllers/progression_orientation_3d"
CORE=NATIVE/"orientation_core.h"
SOURCE=NATIVE/"progression_orientation_3d.c"
SCENE=ROOT/"worlds/scenes/orientation-v1.wbo"
MAKEFILE=NATIVE/"Makefile"

DRIVER=r"""
#include "orientation_core.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static wb_orient_verdict step(wb_orient_mission*m,double t,double x,double y,
                              double z,double yaw,double vx,int completed){
 wb_orient_sample s={.time=t,.x=x,.y=y,.z=z,.yaw=yaw,.vx=vx,.vy=0,.vz=0,
                     .completed=completed};
 return wb_orient_sample_mission(m,&s);
}
static void route(wb_orient_mission*m) {
 assert(step(m,1,.45,0,.63,-WB_ORIENT_PI/2,0,0)==WB_ORIENT_WAIT);
 assert(m->stage==1 && m->airborne);
 assert(step(m,2,.45,-.45,.79,0,0,0)==WB_ORIENT_WAIT);
 assert(m->stage==2);
 assert(step(m,3,.90,-.45,.63,-WB_ORIENT_PI/2,0,0)==WB_ORIENT_WAIT);
 assert(m->stage==3);
}
int main(void) {
 wb_orient_mission m;
 wb_orient_reset(&m,1,0);
 assert(step(&m,0,0,0,0,0,0,0)==WB_ORIENT_WAIT);
 route(&m);
 assert(step(&m,4,.90,-.90,.03,0,0,1)==WB_ORIENT_ACHIEVED);
 assert(step(&m,5,5,5,5,0,0,0)==WB_ORIENT_ACHIEVED);
 // RESET does not inherit achievement, stage, flight or completion.
 wb_orient_reset(&m,2,0);
 assert(!m.stage && !m.airborne && !m.completion_seen);
 assert(step(&m,4,.9,-.9,.03,0,0,1)==WB_ORIENT_NOT_ACHIEVED);
 // Wrong cap at first beacon, with otherwise valid location.
 wb_orient_reset(&m,3,0);
 assert(step(&m,1,.45,0,.63,0,0,0)==WB_ORIENT_WAIT && m.stage==0);
 assert(step(&m,4,.9,-.9,.03,0,0,1)==WB_ORIENT_NOT_ACHIEVED);
 // Wrong order cannot satisfy A-B-C.
 wb_orient_reset(&m,4,0);
 assert(step(&m,1,.45,-.45,.79,0,0,0)==WB_ORIENT_WAIT && m.stage==0);
 assert(step(&m,2,.45,0,.63,-WB_ORIENT_PI/2,0,0)==WB_ORIENT_WAIT);
 assert(step(&m,3,.9,-.45,.63,-WB_ORIENT_PI/2,0,0)==WB_ORIENT_WAIT);
 assert(m.stage==1);
 assert(step(&m,4,.9,-.9,.03,0,0,1)==WB_ORIENT_NOT_ACHIEVED);
 // Constant height fails B.
 wb_orient_reset(&m,5,0);
 assert(step(&m,1,.45,0,.63,-WB_ORIENT_PI/2,0,0)==WB_ORIENT_WAIT);
 assert(step(&m,2,.45,-.45,.63,0,0,0)==WB_ORIENT_WAIT && m.stage==1);
 assert(step(&m,4,.9,-.9,.03,0,0,1)==WB_ORIENT_NOT_ACHIEVED);
 // Moving landing, hovering over arrival or landing elsewhere cannot pass.
 for (int kind=0;kind<3;++kind) {
  wb_orient_reset(&m,(unsigned long long)kind+6,0);
  route(&m);
  double x=kind==2?1.2:.9;
  double z=kind==1?.4:.03;
  double vx=kind==0?.5:0;
  assert(step(&m,4,x,-.9,z,0,vx,1)==WB_ORIENT_WAIT);
  assert(step(&m,6,x,-.9,z,0,vx,0)==WB_ORIENT_NOT_ACHIEVED);
 }
 // Invalid orientation/observations are fail-closed, not success.
 wb_orient_reset(&m,9,0);
 route(&m);
 assert(step(&m,4,.9,-.9,.03,NAN,0,1)==WB_ORIENT_NOT_ACHIEVED);
 const double identity[]={1,0,0,0,1,0,0,0,1};
 const double turn[]={0,1,0,-1,0,0,0,0,1};
 const double invalid[]={NAN,0,0,0,1,0,0,0,1};
 double yaw=123;
 assert(wb_orient_yaw(identity,&yaw) && fabs(yaw)<1e-9);
 assert(wb_orient_yaw(turn,&yaw) && fabs(yaw+WB_ORIENT_PI/2)<1e-9);
 assert(!wb_orient_yaw(invalid,&yaw));
 assert(!wb_orient_yaw(NULL,&yaw));
 assert(wb_orient_angular_error(WB_ORIENT_PI,-WB_ORIENT_PI)<1e-9);
 puts("PASS native Activity 3: heading, order, height, landing, fresh attempt");
 return 0;
}
"""


class NativeActivity3Oracle(unittest.TestCase):
    def test_compiled_real_c_oracle_and_negatives(self):
        cc=shutil.which("cc")
        self.assertIsNotNone(cc,"C compiler required, cannot skip")
        with tempfile.TemporaryDirectory(prefix="wb-orientation-native-") as tmp:
            source=Path(tmp)/"test.c"
            target=Path(tmp)/"test"
            source.write_text(DRIVER,encoding="utf-8")
            build=subprocess.run([cc,"-std=c11","-Wall","-Wextra","-Werror",
                                  "-pedantic","-I",str(NATIVE),str(source),
                                  "-lm","-o",str(target)],
                                 text=True,capture_output=True,timeout=30)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            result=subprocess.run([str(target)],text=True,
                                  capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("PASS native Activity 3",result.stdout)

    def test_3d_scene_and_c_constants_agree(self):
        scene=SCENE.read_text(encoding="utf8")
        core=CORE.read_text(encoding="utf8")
        self.assertIn("#define WB_ORIENT_CHILDREN 24",core)
        self.assertIn("#define WB_ORIENT_LAND_X 0.90",core)
        self.assertIn("#define WB_ORIENT_LAND_Y -0.90",core)
        self.assertEqual(scene.count("    Pose { translation "),24)
        for label,coords,angle in (
            ("A",(.45,0,.63),-1.570796),
            ("B",(.45,-.45,.79),0),
            ("C",(.90,-.45,.63),-1.570796),
        ):
            mark=re.search(rf"# CHECKPOINT {label}:[^\n]*\n\s*Pose \{{ translation "
                           rf"(-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)",scene)
            arrow=re.search(rf"# DIRECTION {label}:[^\n]*\n\s*Pose \{{ translation "
                            rf"(-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+) "
                            rf"rotation 0 0 1 (-?[0-9.]+)",scene)
            self.assertIsNotNone(mark)
            self.assertIsNotNone(arrow)
            self.assertEqual(tuple(map(float,mark.groups())),coords)
            self.assertAlmostEqual(float(arrow.group(4)),angle,places=5)

    def test_scene_only_native_executable_has_no_program_authority(self):
        src=SOURCE.read_text(encoding="utf8")
        mk=MAKEFILE.read_text(encoding="utf8")
        scene=SCENE.read_text(encoding="utf8")
        self.assertIn("C_SOURCES = progression_orientation_3d.c",mk)
        self.assertNotIn("crazyflie_runtime_v2",mk)
        for name in ("wb_supervisor_node_get_orientation",
                     "wb_orient_sample_mission",
                     "WB_ORIENT_ORACLE",
                     "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu",
                     "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
                     "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
                     "identity > last_identity"):
            self.assertIn(name,src)
        self.assertIn('controller "progression_orientation_3d"',scene)
        self.assertEqual(scene.count(" Robot {"),1)
        self.assertNotIn("wb_robot_set_mode",src)
        self.assertNotIn("allowedStatementKinds",src)
        self.assertNotIn("Blockly",src)
        self.assertNotIn("Py_Initialize",src)


if __name__=="__main__":
    unittest.main()
