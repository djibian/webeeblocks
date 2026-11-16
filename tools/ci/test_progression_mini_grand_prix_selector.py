#!/usr/bin/env python3
"""Compiled C++ adversarial A7 native selector gate and source contracts.

The fake Webots nodes falsify the classroom A7 gate deterministically; the
Draft workflow separately runs real Webots R2025a imported scenes L/R/L.
Neither proof is a motorized Blockly flight or a student PASS.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "controllers/crazyflie_classroom_v2/mini_gp_scene_gate.h"
SCHOOL = ROOT / "controllers/crazyflie_classroom_v2/classroom_scene.cpp"
PHYSICAL = ROOT / "controllers/crazyflie_runtime_v2/activity_scene.cpp"
RUNNER = ROOT / "tools/ci/run_classroom_mini_gp_scene_selector.py"

API = r"""
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
typedef void *WbNodeRef;
typedef void *WbFieldRef;
WbNodeRef wb_supervisor_node_get_from_def(const char *);
const char *wb_supervisor_node_get_type_name(WbNodeRef);
WbFieldRef wb_supervisor_node_get_field(WbNodeRef,const char *);
int wb_supervisor_field_get_count(WbFieldRef);
WbNodeRef wb_supervisor_field_get_mf_node(WbFieldRef,int);
const char *wb_supervisor_field_get_sf_string(WbFieldRef);
int wb_supervisor_field_get_sf_bool(WbFieldRef);
WbNodeRef wb_supervisor_field_get_sf_node(WbFieldRef);
const double *wb_supervisor_field_get_sf_vec3f(WbFieldRef);
const double *wb_supervisor_node_get_position(WbNodeRef);
const double *wb_supervisor_node_get_orientation(WbNodeRef);
#ifdef __cplusplus
}
#endif
"""

DRIVER = r"""
#include "mini_gp_scene_gate.h"
#include <cassert>
#include <cstring>
#include <list>
#include <map>
#include <string>
#include <vector>
#include <iostream>

struct Node {
  std::string type, def, name, controller;
  double pos[3] = {0,0,0};
  double size[3] = {0,0,0};
  double rot[9] = {1,0,0,0,1,0,0,0,1};
  std::vector<Node*> children;
  Node *bounding = nullptr;
  bool sup = true, sync = true;
};
struct Field {Node *node; std::string name;};
std::list<Node> nodes;
std::list<Field> fields;
std::map<std::string, Node*> refs;
Node *add(const char *type, const std::string &def = "") {
  nodes.emplace_back();
  Node *n = &nodes.back();
  n->type = type;
  n->def = def;
  if(!def.empty()) refs[def] = n;
  return n;
}
static void put(double (&dst)[3], double x,double y,double z) {
  dst[0]=x;dst[1]=y;dst[2]=z;
}
extern "C" WbNodeRef wb_supervisor_node_get_from_def(const char *d) {
  auto it=refs.find(d);
  return it==refs.end()?nullptr:it->second;
}
extern "C" const char *wb_supervisor_node_get_type_name(WbNodeRef r) {
  return static_cast<Node*>(r)->type.c_str();
}
extern "C" WbFieldRef wb_supervisor_node_get_field(WbNodeRef r,const char*key) {
  if(!r) return nullptr;
  Node*n=static_cast<Node*>(r);
  std::string f(key);
  const bool allowed =
    (f=="children" && (n->type=="Group"||n->type=="Pose")) ||
    (f=="boundingObject" && n->type=="Solid") ||
    (f=="size" && n->type=="Box") ||
    ((f=="controller"||f=="name"||f=="supervisor"||f=="synchronization") &&
      n->type=="Robot");
  if(!allowed) return nullptr;
  fields.push_back(Field{n,f});
  return &fields.back();
}
extern "C" int wb_supervisor_field_get_count(WbFieldRef f) {
  return (int)static_cast<Field*>(f)->node->children.size();
}
extern "C" WbNodeRef wb_supervisor_field_get_mf_node(WbFieldRef f,int i) {
  auto &v=static_cast<Field*>(f)->node->children;
  return i>=0 && i<(int)v.size()?v[(size_t)i]:nullptr;
}
extern "C" const char* wb_supervisor_field_get_sf_string(WbFieldRef f) {
  Field*x=static_cast<Field*>(f);
  return (x->name=="controller"?x->node->controller:x->node->name).c_str();
}
extern "C" int wb_supervisor_field_get_sf_bool(WbFieldRef f) {
  Field*x=static_cast<Field*>(f);
  return x->name=="supervisor"?x->node->sup:x->node->sync;
}
extern "C" WbNodeRef wb_supervisor_field_get_sf_node(WbFieldRef f) {
  return static_cast<Field*>(f)->node->bounding;
}
extern "C" const double*wb_supervisor_field_get_sf_vec3f(WbFieldRef f) {
  return static_cast<Field*>(f)->node->size;
}
extern "C" const double*wb_supervisor_node_get_position(WbNodeRef n) {
  return static_cast<Node*>(n)->pos;
}
extern "C" const double*wb_supervisor_node_get_orientation(WbNodeRef n) {
  return static_cast<Node*>(n)->rot;
}

struct Scene {
  Node *group,*observer;
  Node *solids[9],*boxes[9];
  Node *pose0;
};
Scene create(char v) {
  Scene sc{};
  sc.group=add("Group",v=='L'?"WEBEEBLOCKS_MINI_GP_L_SCENE":
                              "WEBEEBLOCKS_MINI_GP_R_SCENE");
  for(int i=0;i<20;i++) {
    Node *pose=add("Pose");
    pose->children.push_back(add("Shape"));
    if(i==0) {
      sc.pose0=pose;
      sc.observer=add("Robot");
      sc.observer->name="Mini Grand Prix native evaluator";
      sc.observer->controller="progression_mini_grand_prix_v1";
      pose->children.push_back(sc.observer);
    }
    sc.group->children.push_back(pose);
  }
  const double h=v=='L'?-.750:-.450;
  const double x=v=='L'?.200:.500;
  const double side=v=='L'?1.0:-1.0;
  const char *names[9]={
    "OPEN_LEFT","OPEN_RIGHT","OPEN_BAR","CORNER_FRONT","CORNER_SIDE",
    "CLOSED_LEFT","CLOSED_RIGHT","CLOSED_BAR","CLOSED_PANEL"
  };
  const double p[9][3]={
    {h,.300,.500},{h,-.300,.500},{h,0,.740},{x+.220,0,.550},
    {x,-side*.320,.550},{x-.300,side*1.420,.650},
    {x+.300,side*1.420,.650},{x,side*1.420,.900},
    {x,side*1.420,.650}
  };
  const double dims[9][3]={
    {.070,.065,1.00},{.070,.065,1.00},{.070,.570,.240},
    {.080,.640,1.10},{.480,.080,1.10},
    {.065,.080,1.30},{.065,.080,1.30},{.570,.080,.300},
    {.570,.080,1.30}
  };
  for(int i=0;i<9;i++){
    sc.solids[i]=add("Solid",std::string("ACTIVITY7_")+v+"_"+names[i]);
    put(sc.solids[i]->pos,p[i][0],p[i][1],p[i][2]);
    sc.boxes[i]=add("Box");
    put(sc.boxes[i]->size,dims[i][0],dims[i][1],dims[i][2]);
    sc.solids[i]->bounding=sc.boxes[i];
    sc.group->children.push_back(sc.solids[i]);
  }
  return sc;
}
int main() {
  using webeeblocks_a7_gate::valid;
  assert(!valid('L')&&!valid('R')&&!valid('?'));
  Node *world=add("WorldInfo","WEBEEBLOCKS_CLASSROOM_START_WORLD");
  Scene a=create('L'), b=create('R');
  assert(valid('L')&&valid('R'));
  b.boxes[3]->size[2]+=.02;
  assert(valid('L')&&!valid('R'));b.boxes[3]->size[2]-=.02;
  b.solids[5]->pos[1]+=.021;
  assert(!valid('R'));b.solids[5]->pos[1]-=.021;
  a.observer->controller="wrong";
  assert(!valid('L')&&valid('R'));
  a.observer->controller="progression_mini_grand_prix_v1";
  a.observer->sup=false;assert(!valid('L'));a.observer->sup=true;
  a.observer->sync=false;assert(!valid('L'));a.observer->sync=true;
  a.observer->type="Shape";assert(!valid('L'));a.observer->type="Robot";
  a.observer->name="wrong";assert(!valid('L'));
  a.observer->name="Mini Grand Prix native evaluator";
  assert(valid('L'));
  a.pose0->children.pop_back();assert(!valid('L'));
  a.pose0->children.push_back(a.observer);assert(valid('L'));
  a.group->children.pop_back();assert(!valid('L'));
  a.group->children.push_back(a.solids[8]);assert(valid('L'));
  a.group->children[19]->type="Solid";assert(!valid('L'));
  a.group->children[19]->type="Pose";assert(valid('L'));
  a.solids[0]->rot[0]=.99;assert(!valid('L'));
  a.solids[0]->rot[0]=1;
  a.solids[1]->bounding=nullptr;assert(!valid('L'));
  a.solids[1]->bounding=a.boxes[1];
  a.boxes[2]->type="Cylinder";assert(!valid('L'));
  a.boxes[2]->type="Box";
  refs.erase("ACTIVITY7_L_OPEN_LEFT");assert(!valid('L'));
  refs["ACTIVITY7_L_OPEN_LEFT"]=a.solids[0];
  for(const char* foreign : {"WEBEEBLOCKS_DECISION_A_SCENE",
                             "WEBEEBLOCKS_DECISION_B_SCENE"}) {
    add("Group",foreign);
    assert(!valid('L')&&!valid('R'));
    refs.erase(foreign);
    assert(valid('L')&&valid('R'));
  }
  world->type="Group";assert(!valid('L')&&!valid('R'));
  world->type="WorldInfo";assert(valid('L')&&valid('R'));
  std::cout<<"PASS compiled A7 school scene gate: L/R, 29 children, "
           <<"genuine observer, 9 collider boxes, malformed provenance refused\n";
}

"""

class MiniGpSelectorTests(unittest.TestCase):
    def test_compiled_cxx_gate_falsifies_wrong_observer_and_colliders(self):
        cxx=shutil.which("g++")
        self.assertIsNotNone(cxx,"real C++ compiler required")
        with tempfile.TemporaryDirectory(prefix="wb-a7-scene-gate-") as tmp:
            root=Path(tmp)
            for rel in ("webots/robot.h","webots/supervisor.h"):
                path=root/rel
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(API,encoding="utf-8")
            src=root/"test.cpp"
            src.write_text(DRIVER,encoding="utf-8")
            exe=root/"test"
            cmd=[cxx,"-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(root),"-I",str(GATE.parent),str(src),"-o",str(exe)]
            out=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
            self.assertEqual(out.returncode,0,out.stdout+out.stderr)
            check=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
            self.assertEqual(check.returncode,0,check.stdout+check.stderr)
            self.assertIn("PASS compiled A7 school scene gate:",check.stdout)

    def test_real_selector_is_school_only_and_uses_two_strict_native_scenes(self):
        source=SCHOOL.read_text(encoding="utf-8")
        gate=GATE.read_text(encoding="utf-8")
        runner=RUNNER.read_text(encoding="utf-8")
        self.assertIn('mini_gp_scene_gate.h',source)
        self.assertIn('webeeblocks_a7_gate::valid(variant)',source)
        for name in ("mini-grand-prix-l-v1","mini-grand-prix-r-v1"):
            self.assertIn(name,source)
            self.assertIn(name + ".wbo",source)
        for proof in ("WEBEEBLOCKS_MINI_GP_L_SCENE",
                      "WEBEEBLOCKS_MINI_GP_R_SCENE",
                      "progression_mini_grand_prix_v1"):
            self.assertIn(proof,source)
            self.assertIn(proof,gate)
            self.assertNotIn(proof,PHYSICAL.read_text(encoding="utf-8"))
        for token in ("progression_mini_gp_scene_probe",
                      "WEBEEBLOCKS_A7_SCENE_SELECTOR_NATIVE_PASS",
                      "A7_SELECTOR_NATIVE_PASS",
                      '"motorized_flight": False',
                      '"same_pupil_wbb": False'):
            self.assertIn(token,runner)
        self.assertNotIn("wb_motor_set_",gate)
        self.assertNotIn('controller "crazyflie_runtime_v2"',runner.split("def compose():",1)[0])

if __name__=="__main__":
    unittest.main()
