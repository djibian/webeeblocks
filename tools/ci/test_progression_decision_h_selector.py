#!/usr/bin/env python3
"""Falsify the exact A4 classroom-only C++ admission gate with real compiled C++.

This bounded fake-Webots test checks world/observer/collider provenance; it
does NOT replace Webots R2025a compilation or native pupil/Blockly validation.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "controllers/crazyflie_classroom_v2/decision_h_scene_gate.h"
SCHOOL = ROOT / "controllers/crazyflie_classroom_v2/classroom_scene.cpp"
PHYSICAL = ROOT / "controllers/crazyflie_runtime_v2/activity_scene.cpp"

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
#include "decision_h_scene_gate.h"
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
  Node *group, *observer;
  Node *solids[6];
  Node *boxes[6];
};
Scene create(char letter) {
  const std::string stem=letter=='a'?"WEBEEBLOCKS_DECISION_A_SCENE":
                                    "WEBEEBLOCKS_DECISION_B_SCENE";
  Scene sc{};
  sc.group=add("Group",stem);
  for(int i=0;i<23;++i) {
    Node*pose=add("Pose");
    pose->children.push_back(add("Shape"));
    if(i==0){
      sc.observer=add("Robot");
      sc.observer->name="Progression decision H native evaluator";
      sc.observer->controller="progression_decision_h_v1";
      pose->children.push_back(sc.observer);
    }
    sc.group->children.push_back(pose);
  }
  const double h=letter=='a'?.750:1.350;
  const double curb=letter=='a'?1.350:.750;
  const char* suffix[6]={"H_LEFT","H_RIGHT","H_BAR","THRESHOLD",
                         "CORRIDOR_LEFT","CORRIDOR_RIGHT"};
  const double pos[6][3]={{h,.300,.500},{h,-.300,.500},{h,0,.740},
                          {curb,0,.350},{.700,.420,.520},{.700,-.420,.520}};
  const double dim[6][3]={{.070,.065,1.00},{.070,.065,1.00},
                          {.070,.570,.240},{.100,.740,.700},
                          {1.80,.080,1.04},{1.80,.080,1.04}};
  for(int i=0;i<6;++i) {
    sc.solids[i]=add("Solid",std::string("ACTIVITY4_")+
                    (letter=='a'?"A_":"B_")+suffix[i]);
    put(sc.solids[i]->pos,pos[i][0],pos[i][1],pos[i][2]);
    sc.boxes[i]=add("Box");
    put(sc.boxes[i]->size,dim[i][0],dim[i][1],dim[i][2]);
    sc.solids[i]->bounding=sc.boxes[i];
    sc.group->children.push_back(sc.solids[i]);
  }
  return sc;
}
int main() {
  using webeeblocks_a4_gate::valid;
  assert(!valid('a') && !valid('b') && !valid('z'));
  Node *world=add("WorldInfo","WEBEEBLOCKS_CLASSROOM_START_WORLD");
  Scene a=create('a');
  Scene b=create('b');
  assert(valid('a') && valid('b'));
  a.observer->controller="wrong";
  assert(!valid('a') && valid('b'));
  a.observer->controller="progression_decision_h_v1";
  a.observer->sup=false;
  assert(!valid('a'));
  a.observer->sup=true;
  a.observer->sync=false;
  assert(!valid('a'));
  a.observer->sync=true;
  a.observer->type="Shape";
  assert(!valid('a'));
  a.observer->type="Robot";
  assert(valid('a'));
  a.group->children.pop_back();
  assert(!valid('a'));
  a.group->children.push_back(a.solids[5]);
  assert(valid('a'));
  a.solids[2]->pos[2]+=.02;
  assert(!valid('a') && valid('b'));
  a.solids[2]->pos[2]-=.02;
  a.boxes[3]->size[2]+=.02;
  assert(!valid('a'));
  a.boxes[3]->size[2]-=.02;
  a.solids[0]->rot[0]=0.99;
  assert(!valid('a'));
  a.solids[0]->rot[0]=1;
  a.solids[1]->bounding=nullptr;
  assert(!valid('a'));
  a.solids[1]->bounding=a.boxes[1];
  a.boxes[2]->type="Cylinder";
  assert(!valid('a'));
  a.boxes[2]->type="Box";
  assert(valid('a'));
  refs.erase("ACTIVITY4_A_H_LEFT");
  assert(!valid('a'));
  refs["ACTIVITY4_A_H_LEFT"]=a.solids[0];
  world->type="Group";
  assert(!valid('a') && !valid('b'));
  world->type="WorldInfo";
  assert(valid('a') && valid('b'));
  std::cout<<"PASS compiled A4 school native scene gate: A/B valid, "
              "observer impostors, all collider geometry, typed world fail closed\n";
}
"""

class DecisionHSelectorTests(unittest.TestCase):
    def test_school_scene_gate_compiled_cpp_adversaries(self):
        cxx = shutil.which("g++")
        self.assertIsNotNone(cxx, "real C++ compiler required")
        with tempfile.TemporaryDirectory(prefix="wb-a4-school-gate-") as tmp:
            root=Path(tmp)
            for rel in ("webots/robot.h", "webots/supervisor.h"):
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
            run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn("PASS compiled A4 school native scene gate:",run.stdout)

    def test_tokenized_school_only_scene_switch_without_physical_mutation(self):
        src=SCHOOL.read_text(encoding="utf-8")
        production=PHYSICAL.read_text(encoding="utf-8")
        guard=GATE.read_text(encoding="utf-8")
        self.assertIn('#include "decision_h_scene_gate.h"',src)
        self.assertIn("kDecisionSceneChildren = webeeblocks_a4_gate::kChildren",src)
        for token in ("decision-h-a-v1", "decision-h-b-v1"):
            self.assertIn('std::strcmp(scene, "'+token+'")',src)
            self.assertNotIn('"'+token+'"',production)
        for token in ("WEBEEBLOCKS_DECISION_A_SCENE","WEBEEBLOCKS_DECISION_B_SCENE"):
            self.assertIn('removeDef("'+token+'")',src)
            self.assertIn('!wb_supervisor_node_get_from_def("'+token+'")',src)
        self.assertIn("ready = webeeblocks_a4_gate::valid(variant)",src)
        self.assertIn("if (!ready) return 0;",src)
        self.assertIn("sceneFile(variantA ? \"decision-h-a-v1.wbo\"",src)
        self.assertIn("wb_supervisor_field_import_mf_node_from_string",src)
        for part in ("WB_DH", "wb_motor_set_", "radio_link"):
            self.assertNotIn(part,guard)
        for token in ("ACTIVITY4_%c_%s", "boundingObject", "Robot",
                      "supervisor", "synchronization", "WorldInfo"):
            self.assertIn(token,guard)

if __name__ == "__main__":
    unittest.main()
