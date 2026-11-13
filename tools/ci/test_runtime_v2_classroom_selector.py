#!/usr/bin/env python3
"""Compile and falsify the distinct school-only scene selector.

The test executes the actual standalone C++ selector against bounded fake
Webots node/scene failures, without touching the locked production executable.
No Webots R2025a or Windows product PASS is claimed by this mock.
"""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[2]
CPP = ROOT / "controllers/crazyflie_classroom_v2/classroom_scene.cpp"
MAKE = ROOT / "controllers/crazyflie_classroom_v2/Makefile"
PHYSICAL = ROOT / "controllers/crazyflie_runtime_v2/activity_scene.cpp"

spec = importlib.util.spec_from_file_location(
    "webeeblocks_scene_harness",
    ROOT / "tools/ci/test_runtime_v2_activity_scene.py"
)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

DRIVER = r"""
#include "activity_scene.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#include <webots/supervisor.h>
struct Node {std::string def,type,text;bool alive;int count;};
Node root{"","Group","",true,0};
Node viewpoint{"","Viewpoint","",true,0};
Node legacy{"WEBEEBLOCKS_LEGACY_SCENE","Group",
 "DEF WEBEEBLOCKS_LEGACY_SCENE Group { children [] }",true,32};
Node evaluators{"WEBEEBLOCKS_LEGACY_EVALUATORS","Group",
 "DEF WEBEEBLOCKS_LEGACY_EVALUATORS Group { children [] }",true,6};
Node sequence{"WEBEEBLOCKS_SEQUENCE_SCENE","Group","",false,18};
Node altitude{"WEBEEBLOCKS_ALTITUDE_SCENE","Group","",false,21};
Node barrier{"ACTIVITY2_LOW_BARRIER","Solid","",false,0};
Node left{"ACTIVITY2_LEFT_WALL","Solid","",false,0};
Node right{"ACTIVITY2_RIGHT_WALL","Solid","",false,0};
Node barrierBox{"","Box","",true,0};
Node leftBox{"","Box","",true,0};
Node rightBox{"","Box","",true,0};
double barrierPosition[3]={0.62,0.0,0.31},leftPosition[3]={0.68,0.51,0.425},rightPosition[3]={0.68,-0.51,0.425};
double barrierSize[3]={0.12,0.84,0.62},leftSize[3]={1.65,0.08,0.85},rightSize[3]={1.65,0.08,0.85};
std::vector<Node*> all{&viewpoint,&legacy,&evaluators,&sequence,&altitude,&barrier,&left,&right};
int rootChildren=0, position=0, orientation=0;
double pos[3]={-2,-2,2},rot[4]={0,0,1,1};
double colliderIdentity[9]={1,0,0,0,1,0,0,0,1};
double colliderTurned[9]={0,-1,0,1,0,0,0,0,1};
std::string project;
bool partial=false,missingCollider=false;
bool missingBounds=false,badShape=false,badPosition=false,badDimensions=false,badRotation=false;
std::vector<std::string> removals;
extern "C" const char* wb_robot_get_project_path(void){return project.c_str();}
extern "C" void* wb_supervisor_node_get_root(void){return &root;}
extern "C" void* wb_supervisor_node_get_from_def(const char *def){
 for (Node *n : all) {
  if (n->alive && n->def == def) return n;
 }
 return nullptr;
}
extern "C" const char* wb_supervisor_node_get_type_name(void*n){return static_cast<Node*>(n)->type.c_str();}
extern "C" const char* wb_supervisor_node_get_def(void*n){return static_cast<Node*>(n)->def.c_str();}
extern "C" const char* wb_supervisor_node_export_string(void*n){return static_cast<Node*>(n)->text.c_str();}
extern "C" void wb_supervisor_node_remove(void*n){
 Node*p=static_cast<Node*>(n);assert(p->alive);p->alive=false;
 removals.push_back(p->def);
 if(p==&altitude){barrier.alive=left.alive=right.alive=false;}
}
extern "C" void* wb_supervisor_node_get_field(void*n,const char*field){
 if(n==&root && !std::strcmp(field,"children"))return &rootChildren;
 if(n==&viewpoint && !std::strcmp(field,"position"))return &position;
 if(n==&viewpoint && !std::strcmp(field,"orientation"))return &orientation;
 Node*p=static_cast<Node*>(n);
 if(!std::strcmp(field,"children")&&p->type=="Group")return &p->count;
 if(!std::strcmp(field,"boundingObject")) {
  if(p==&barrier)return missingBounds?nullptr:&barrierBox;
  if(p==&left)return &leftBox;
  if(p==&right)return &rightBox;
 }
 if(!std::strcmp(field,"size")) {
  if(p==&barrierBox)return barrierSize;
  if(p==&leftBox)return leftSize;
  if(p==&rightBox)return rightSize;
 }
 return nullptr;
}
extern "C" int wb_supervisor_field_get_count(void*f){
 if(f!=&rootChildren)return *static_cast<int*>(f);
 int n=0;
 for (Node *p : all) {
  if (p->alive) ++n;
 }
 return n;
}
extern "C" void* wb_supervisor_field_get_mf_node(void*f,int index){
 if(f==&rootChildren){
  for (Node *p : all) {
   if (p->alive && index-- == 0) return p;
  }
  return nullptr;
 }
 return index>=0&&index<*static_cast<int*>(f)?&viewpoint:nullptr;
}
extern "C" const double* wb_supervisor_field_get_sf_vec3f(void*f){
 if(f==barrierSize)return barrierSize;
 if(f==leftSize)return leftSize;
 if(f==rightSize)return rightSize;
 return pos;
}
extern "C" void* wb_supervisor_field_get_sf_node(void*f){return f;}
extern "C" const double* wb_supervisor_node_get_position(void*n){
 if(n==&barrier)return barrierPosition;
 if(n==&left)return leftPosition;
 if(n==&right)return rightPosition;
 return nullptr;
}
extern "C" const double* wb_supervisor_node_get_orientation(void*n){
 if(n==&right && badRotation)return colliderTurned;
 if(n==&barrier || n==&left || n==&right)return colliderIdentity;
 return nullptr;
}
extern "C" const double* wb_supervisor_field_get_sf_rotation(void*){return rot;}
extern "C" void wb_supervisor_field_set_sf_vec3f(void*,const double*p){std::memcpy(pos,p,sizeof(pos));}
extern "C" void wb_supervisor_field_set_sf_rotation(void*,const double*p){std::memcpy(rot,p,sizeof(rot));}
extern "C" void wb_supervisor_field_import_mf_node_from_string(void*,int,const char*data){
 const std::string src=data;
 if(src.find("DEF WEBEEBLOCKS_ALTITUDE_SCENE Group {")!=std::string::npos){
  altitude.alive=true;altitude.count=partial?20:21;
  barrier.alive=true;left.alive=true;right.alive=!missingCollider;
 } else if(src.find("DEF WEBEEBLOCKS_LEGACY_SCENE Group {")!=std::string::npos){
  legacy.alive=true;
 } else if(src.find("DEF WEBEEBLOCKS_LEGACY_EVALUATORS Group {")!=std::string::npos){
  evaluators.alive=true;
 } else if(src.find("DEF WEBEEBLOCKS_SEQUENCE_SCENE Group {")!=std::string::npos){
  sequence.alive=true;sequence.count=18;
 }
}
int main(int argc,char**argv){
 assert(argc==3);project=argv[1];std::string mode=argv[2];
 missingBounds=mode=="missing-bounds";
 badShape=mode=="wrong-box-type";
 badPosition=mode=="wrong-box-position";
 badDimensions=mode=="wrong-box-size";
 badRotation=mode=="wrong-box-rotation";
 if(badShape)barrierBox.type="Sphere";
 if(badPosition)barrierPosition[0]=0.81;
 if(badDimensions)barrierSize[0]=0.30;
 assert(webeeblocks_activity_scene_ready());
 assert(!webeeblocks_select_activity_scene("nonexistent-v1"));
 assert(!webeeblocks_select_activity_scene(""));
 assert(!webeeblocks_select_activity_scene(nullptr));
 assert(removals.empty());
 if(mode=="missing" || mode=="malformed"){
  assert(!webeeblocks_select_activity_scene("altitude-v1"));
  assert(webeeblocks_activity_scene_ready());
  assert(removals.empty());assert(legacy.alive && evaluators.alive);
  std::cout<<"PASS fail-closed unknown/missing/malformed asset\n";
  return 0;
 }
 partial=mode=="partial"; missingCollider=mode=="missing-collider";
 const bool valid=mode=="valid";
 assert(bool(webeeblocks_select_activity_scene("altitude-v1"))==valid);
 assert(!legacy.alive && !evaluators.alive);
 assert(altitude.alive);
 assert(bool(webeeblocks_activity_scene_ready())==valid);
 assert(pos[0]==-1.8);
 if(!valid){
  assert(!webeeblocks_select_activity_scene("altitude-v1"));
  assert(!webeeblocks_activity_scene_ready());
 }
 // The stateful classroom runtime can always restore the saved legacy
 // scene after a failed partial import, without reusing a stale Ready.
 assert(webeeblocks_select_activity_scene("legacy-v1"));
 assert(webeeblocks_activity_scene_ready());
 assert(legacy.alive&&evaluators.alive&&!altitude.alive);
 assert(pos[0]==-2);
 if(valid){
  assert(webeeblocks_select_activity_scene("sequence-v1"));
  assert(webeeblocks_activity_scene_ready());
  assert(!altitude.alive && sequence.alive);
  assert(webeeblocks_select_activity_scene("legacy-v1"));
  assert(webeeblocks_activity_scene_ready());
  assert(webeeblocks_select_activity_scene("altitude-v1"));
  assert(webeeblocks_activity_scene_ready());
  assert(!legacy.alive && !sequence.alive);
 }
 std::cout<<"PASS classroom-only selector: "<<mode<<"\n";
}
"""


class ClassroomRuntimeSelectorTest(unittest.TestCase):
    def test_school_adapter_has_no_physical_mutation_or_implicit_student_activation(self):
        mk = MAKE.read_text()
        cpp = CPP.read_text()
        phys = PHYSICAL.read_text()
        self.assertIn("CXX_SOURCES = ../crazyflie_runtime_v2/file_broker.cpp", mk)
        self.assertIn("classroom_scene.cpp", mk)
        self.assertNotIn(" activity_scene.cpp", mk)
        self.assertIn("altitude-v1", cpp)
        self.assertIn("kAltitudeSceneChildren = 21", cpp)
        self.assertIn("WEBEEBLOCKS_ALTITUDE_SCENE", cpp)
        self.assertNotIn('"altitude-v1"', phys)
        self.assertIn("constexpr int kLegacySceneChildren = 32", cpp)
        self.assertIn("constexpr int kLegacyEvaluatorChildren = 6", cpp)

    def test_real_r2025a_native_build_is_enforced_by_progression_ci(self):
        # A mock-only green cannot substitute for a Webots-linked executable.
        runner = (ROOT / "tools/ci/run_progression_sequence_mission.py").read_text()
        self.assertIn("make -C ../crazyflie_classroom_v2 clean", runner)
        self.assertIn("make -C ../crazyflie_classroom_v2 && test -s", runner)
        self.assertIn("../crazyflie_classroom_v2/crazyflie_classroom_v2", runner)
        # The school executable must come from the ORIGINAL C source, before
        # legacy diagnostic instrumentation. Merely compiling after the
        # monkeypatch does not attest the shipped classroom binary.
        self.assertIn("classroom-original-build.log", runner)
        self.assertIn("classroom_built = run([", runner)
        self.assertLess(runner.index("classroom_built = run(["),
                        runner.index("controller.write_bytes(diagnostic)"))
        self.assertNotIn("crazyflie_classroom_v2", PHYSICAL.read_text())
        make = MAKE.read_text()
        self.assertIn("C_SOURCES = ../crazyflie_runtime_v2/crazyflie_runtime_v2.c", make)
        self.assertIn("CXX_SOURCES = ../crazyflie_runtime_v2/file_broker.cpp", make)

    def test_real_cpp_selector_accepts_only_complete_typed_scene(self):
        gpp = shutil.which("g++")
        self.assertIsNotNone(gpp, "C++17 compiler required for CI qualification")
        with tempfile.TemporaryDirectory(prefix="wb-classroom-select-") as tmp:
            root = Path(tmp)
            for file in ("webots/robot.h","webots/supervisor.h"):
                p=root/file;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(harness.HEADER.replace(
                    "void wb_supervisor_node_remove(WbNodeRef);",
                    "void wb_supervisor_node_remove(WbNodeRef);\n"
                    "WbNodeRef wb_supervisor_field_get_sf_node(WbFieldRef);\n"
                    "const double *wb_supervisor_node_get_position(WbNodeRef);\n"
                    "const double *wb_supervisor_node_get_orientation(WbNodeRef);"
                ))
            scenes=root/"worlds/scenes"
            scenes.mkdir(parents=True)
            (scenes/"legacy-scene-v1.wbo").write_text(
                "DEF WEBEEBLOCKS_LEGACY_SCENE Group { children [] }")
            (scenes/"legacy-evaluators-v1.wbo").write_text(
                "DEF WEBEEBLOCKS_LEGACY_EVALUATORS Group { children [] }")
            (scenes/"sequence-v1.wbo").write_text(
                "DEF WEBEEBLOCKS_SEQUENCE_SCENE Group { children [] }")
            (root/"test.cpp").write_text(DRIVER)
            out=root/"test"
            cmd=[gpp,"-std=c++17","-Wall","-Wextra","-Werror",
                 "-I",str(root),
                 "-I",str(ROOT/"controllers/crazyflie_runtime_v2"),
                 str(CPP),str(root/"test.cpp"),"-o",str(out)]
            built=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,timeout=45)
            self.assertEqual(built.returncode,0,built.stdout)
            cases={
                "missing":None,
                "malformed":"DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] }",
                "valid": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
                "partial": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
                "missing-collider": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
                "missing-bounds": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
                "wrong-box-type": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
                "wrong-box-position": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
                "wrong-box-size": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
                "wrong-box-rotation": 'DEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] controller "progression_altitude_v1" }',
            }
            for name,scene in cases.items():
                with self.subTest(case=name):
                    target=scenes/"altitude-v1.wbo"
                    if target.exists():target.unlink()
                    if scene is not None:target.write_text(scene)
                    run=subprocess.run([str(out),str(root),name],
                                       text=True,stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,timeout=30)
                    self.assertEqual(run.returncode,0,run.stdout)
                    self.assertIn("PASS ",run.stdout)


if __name__=="__main__":
    unittest.main()
