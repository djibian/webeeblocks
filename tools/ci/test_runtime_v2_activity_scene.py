#!/usr/bin/env python3
"""Run the production scene switch with Webots node and project-path injection."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
HEADER=r'''
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
typedef void *WbNodeRef;typedef void *WbFieldRef;
const char *wb_robot_get_project_path(void);
WbNodeRef wb_supervisor_node_get_root(void);
WbNodeRef wb_supervisor_node_get_from_def(const char *);
const char *wb_supervisor_node_get_type_name(WbNodeRef);
const char *wb_supervisor_node_get_def(WbNodeRef);
const char *wb_supervisor_node_export_string(WbNodeRef);
void wb_supervisor_node_remove(WbNodeRef);
WbFieldRef wb_supervisor_node_get_field(WbNodeRef,const char *);
int wb_supervisor_field_get_count(WbFieldRef);
WbNodeRef wb_supervisor_field_get_mf_node(WbFieldRef,int);
const double *wb_supervisor_field_get_sf_vec3f(WbFieldRef);
const double *wb_supervisor_field_get_sf_rotation(WbFieldRef);
void wb_supervisor_field_set_sf_vec3f(WbFieldRef,const double *);
void wb_supervisor_field_set_sf_rotation(WbFieldRef,const double *);
void wb_supervisor_field_import_mf_node_from_string(WbFieldRef,int,const char *);
#ifdef __cplusplus
}
#endif
'''
PROBE=r'''
#include "activity_scene.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#include <webots/supervisor.h>
extern "C" int restarted_ready();
extern "C" int restarted_select(const char *);
struct Node{std::string def,type,text;bool alive=true;};
Node root{"root","Group",""},view{"","Viewpoint",""},legacy{"WEBEEBLOCKS_LEGACY_SCENE","Group","DEF WEBEEBLOCKS_LEGACY_SCENE Group { children [] }"},evaluators{"WEBEEBLOCKS_LEGACY_EVALUATORS","Group","DEF WEBEEBLOCKS_LEGACY_EVALUATORS Group { children [] }"},extra7{"ACTIVITY7_REFERENCE","Solid",""},extra8{"ACTIVITY8_REFERENCE","Solid",""},sequence{"WEBEEBLOCKS_SEQUENCE_SCENE","Group","",false};
std::vector<Node*> nodes{&view,&legacy,&evaluators,&extra7,&extra8,&sequence};
Node dedicated{"WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD","WorldInfo","",false};
std::vector<std::string> removals;
int legacyChildren=32,evaluatorChildren=6,sequenceChildren=18;
bool rootOnly=false,partialEvaluators=false,partialLegacy=false;
int missingChild=-1;void *missingField=nullptr;
std::string project;
int children=0,position=0,orientation=0;
double p[3]={-2,-2,2},o[4]={0,0,1,1};
bool refuseImport=false;
extern "C" const char *wb_robot_get_project_path(void){return project.c_str();}
extern "C" void *wb_supervisor_node_get_root(void){return &root;}
extern "C" void *wb_supervisor_node_get_from_def(const char *d){for(auto*n:nodes)if(n->alive&&n->def==d)return n;return nullptr;}
extern "C" const char *wb_supervisor_node_get_type_name(void *n){return static_cast<Node*>(n)->type.c_str();}
extern "C" const char *wb_supervisor_node_get_def(void *n){return static_cast<Node*>(n)->def.c_str();}
extern "C" const char *wb_supervisor_node_export_string(void *n){return static_cast<Node*>(n)->text.c_str();}
extern "C" void wb_supervisor_node_remove(void *n){auto*node=static_cast<Node*>(n);assert(node->alive);node->alive=false;removals.push_back(node->def);}
extern "C" void *wb_supervisor_node_get_field(void *n,const char *name){if(n==&root&&!std::strcmp(name,"children"))return &children;if(n==&legacy&&!std::strcmp(name,"children"))return &legacyChildren;if(n==&evaluators&&!std::strcmp(name,"children"))return &evaluatorChildren;if(n==&sequence&&!std::strcmp(name,"children"))return &sequenceChildren;if(n==&view&&!std::strcmp(name,"position"))return &position;if(n==&view&&!std::strcmp(name,"orientation"))return &orientation;return nullptr;}
extern "C" int wb_supervisor_field_get_count(void*f){if(f!=&children)return *static_cast<int*>(f);int count=0;for(auto*n:nodes)if(n->alive)count++;return count;}
extern "C" void *wb_supervisor_field_get_mf_node(void*f,int index){if(f==missingField && index==missingChild)return nullptr;if(f!=&children)return index>=0&&index<*static_cast<int*>(f)?&view:nullptr;for(auto*n:nodes)if(n->alive&&index--==0)return n;return nullptr;}
extern "C" const double *wb_supervisor_field_get_sf_vec3f(void*){return p;}
extern "C" const double *wb_supervisor_field_get_sf_rotation(void*){return o;}
extern "C" void wb_supervisor_field_set_sf_vec3f(void*,const double *v){std::memcpy(p,v,sizeof(p));}
extern "C" void wb_supervisor_field_set_sf_rotation(void*,const double *v){std::memcpy(o,v,sizeof(o));}
extern "C" void wb_supervisor_field_import_mf_node_from_string(void*,int,const char *s){if(refuseImport)return;std::string text=s;for(auto*n:nodes)if(!n->def.empty()&&text.find("DEF "+n->def+" ")!=std::string::npos)n->alive=true; if(text.find("DEF WEBEEBLOCKS_SEQUENCE_SCENE ")!=std::string::npos)sequenceChildren=rootOnly?0:18; if(text.find("DEF WEBEEBLOCKS_LEGACY_SCENE ")!=std::string::npos)legacyChildren=partialLegacy?0:32; if(text.find("DEF WEBEEBLOCKS_LEGACY_EVALUATORS ")!=std::string::npos)evaluatorChildren=partialEvaluators?0:6;}
int main(int argc,char**argv){
 assert(argc==2 || argc==3);std::string valid=argv[1];project=valid+"/missing";
 nodes.push_back(&dedicated);
 if(argc==3){
   const std::string mode=argv[2];
   const bool partial=mode=="partial-scene"||mode=="partial-evaluators"||mode=="partial-null";
   if(partial) {
     sequence.alive=false;dedicated.alive=false;
     if(mode=="partial-scene")legacyChildren=31;
     if(mode=="partial-evaluators")evaluatorChildren=5;
     if(mode=="partial-null"){missingField=&evaluatorChildren;missingChild=5;}
   } else {
     legacy.alive=evaluators.alive=sequence.alive=false;
     dedicated.alive=mode!="missing";
     if(mode=="wrong-type")dedicated.type="Group";
   }
   const bool expected=mode=="dedicated";
   assert(bool(webeeblocks_activity_scene_ready())==expected);
   // A second module starts with fresh statics on the identical live world.
   assert(bool(restarted_ready())==expected);
   assert(!restarted_select("legacy-v1"));
   assert(!restarted_select("sequence-v1"));
   assert(bool(restarted_ready())==expected);
   if(expected){dedicated.alive=false;assert(!restarted_ready());}
   std::cout<<"PASS fresh/restarted scene identity "<<mode<<" ready="<<expected<<"\n";
   return 0;
 }
 assert(webeeblocks_select_activity_scene("legacy-v1"));
 assert(!webeeblocks_select_activity_scene("sequence-v1"));assert(webeeblocks_activity_scene_ready());assert(legacy.alive);
 project=valid; // Official Webots getProjectPath() has NO trailing separator.
 assert(webeeblocks_select_activity_scene("sequence-v1"));assert(webeeblocks_activity_scene_ready());
 assert(sequence.alive&&!legacy.alive&&!evaluators.alive&&!extra7.alive&&!extra8.alive);
 // A second linked instance has fresh process statics but the SAME live world.
 // This is distinct from constructing a new JS Robot Window/backend instance.
 assert(!restarted_ready());
 assert(!restarted_select("legacy-v1"));assert(!restarted_ready());
 assert(!restarted_select("sequence-v1"));assert(!restarted_ready());
 assert(sequence.alive&&!legacy.alive&&!evaluators.alive);
 assert(removals[0]=="WEBEEBLOCKS_LEGACY_EVALUATORS");assert(removals[1]=="WEBEEBLOCKS_LEGACY_SCENE");
 assert(p[0]==-.9);assert(!webeeblocks_select_activity_scene("unknown"));assert(sequence.alive);
 assert(webeeblocks_select_activity_scene("legacy-v1"));assert(legacy.alive&&evaluators.alive&&!sequence.alive);assert(p[0]==-2);
 rootOnly=true;assert(!webeeblocks_select_activity_scene("sequence-v1"));assert(sequence.alive);assert(!webeeblocks_activity_scene_ready());
 rootOnly=false;assert(webeeblocks_select_activity_scene("legacy-v1"));
 assert(webeeblocks_select_activity_scene("sequence-v1"));partialEvaluators=true;
 assert(!webeeblocks_select_activity_scene("legacy-v1"));assert(evaluators.alive);assert(!webeeblocks_activity_scene_ready());
 partialEvaluators=false;assert(webeeblocks_select_activity_scene("legacy-v1"));
 // Keep the expected count but omit the first/last actual node reference.
 for(int index : {0,17}){missingField=&sequenceChildren;missingChild=index;
 assert(!webeeblocks_select_activity_scene("sequence-v1"));assert(!webeeblocks_activity_scene_ready());
 missingField=nullptr;assert(webeeblocks_select_activity_scene("legacy-v1"));}
 sequence.type="Pose";assert(!webeeblocks_select_activity_scene("sequence-v1"));assert(!webeeblocks_activity_scene_ready());
 sequence.type="Group";assert(webeeblocks_select_activity_scene("legacy-v1"));
 // Cached identity cannot attest a live group after its content disappears.
 assert(webeeblocks_select_activity_scene("sequence-v1"));
 sequenceChildren=0;
 assert(!webeeblocks_activity_scene_ready());
 rootOnly=true;assert(!webeeblocks_select_activity_scene("sequence-v1"));
 assert(!webeeblocks_activity_scene_ready());
 rootOnly=false;assert(webeeblocks_select_activity_scene("legacy-v1"));
 assert(webeeblocks_select_activity_scene("sequence-v1"));partialLegacy=true;
 assert(!webeeblocks_select_activity_scene("legacy-v1"));assert(!evaluators.alive);assert(!webeeblocks_activity_scene_ready());
 partialLegacy=false;assert(webeeblocks_select_activity_scene("legacy-v1"));
 for(void *field : {static_cast<void*>(&legacyChildren),static_cast<void*>(&evaluatorChildren)}){
 assert(webeeblocks_select_activity_scene("sequence-v1"));missingField=field;missingChild=*static_cast<int*>(field)-1;
 assert(!webeeblocks_select_activity_scene("legacy-v1"));assert(!webeeblocks_activity_scene_ready());
 if(field==&legacyChildren)assert(!evaluators.alive);
 missingField=nullptr;assert(webeeblocks_select_activity_scene("legacy-v1"));}
 refuseImport=true;assert(!webeeblocks_select_activity_scene("sequence-v1"));assert(!webeeblocks_activity_scene_ready());
 refuseImport=false;assert(webeeblocks_select_activity_scene("legacy-v1"));assert(webeeblocks_activity_scene_ready());assert(legacy.alive&&evaluators.alive);
 std::cout<<"PASS scene switch: official project path, file failure, evaluator-first removal, dynamic objects, camera restoration and partial-import takeoff veto\n";
}
'''
def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for file in ['webots/robot.h','webots/supervisor.h']:
            path=root/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(HEADER)
        scenes=root/'worlds/scenes';scenes.mkdir(parents=True);(scenes/'sequence-v1.wbo').write_bytes((ROOT/'worlds/scenes/sequence-v1.wbo').read_bytes())
        (root/'probe.cpp').write_text(PROBE)
        compiler=['g++','-std=c++17','-Wall','-Wextra','-I',str(root),'-I',str(ROOT/'controllers/crazyflie_runtime_v2')]
        production=str(ROOT/'controllers/crazyflie_runtime_v2/activity_scene.cpp')
        subprocess.run(compiler+['-Dwebeeblocks_activity_scene_ready=restarted_ready',
            '-Dwebeeblocks_select_activity_scene=restarted_select','-c',production,'-o',str(root/'restarted.o')],check=True)
        subprocess.run(compiler+[production,str(root/'probe.cpp'),str(root/'restarted.o'),'-o',str(root/'probe')],check=True)
        subprocess.run([str(root/'probe'),str(root)],check=True)
        for mode in ('missing','wrong-type','dedicated','partial-scene','partial-evaluators','partial-null'):
            subprocess.run([str(root/'probe'),str(root),mode],check=True)
        source=(ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c').read_text()
        types=source[source.index('typedef enum {'):source.index('static double clip(')]
        parser=source[source.index('static int extract_id('):source.index('static void trace_range(')]
        (root/'framing.c').write_text('#include <assert.h>\n#include <stdio.h>\n#include <string.h>\n'
            '#define PREFIX "WEBEEBLOCKS_RUNTIME_V2"\n'+types+parser+r'''
int main(void) {
  const char *nonce="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
  char message[256];
  snprintf(message,sizeof(message),PREFIX " REQUEST 1 SCENE legacy-v1 %s",nonce);
  request_t r=parse_request(message);
  assert(r.kind==REQUEST_SCENE && r.id==1 && !strcmp(r.scene_nonce,nonce));
  assert(!strcmp(r.direction,"legacy-v1"));
  const char *invalid[]={"short","0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdeF",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef extra"};
  for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);i++) {
    snprintf(message,sizeof(message),PREFIX " REQUEST 1 SCENE legacy-v1 %s",invalid[i]);
    assert(parse_request(message).kind==REQUEST_INVALID);
  }
  r=parse_request(PREFIX " REQUEST 1 SCENE legacy-v1");
  assert(r.kind==REQUEST_SCENE && !r.scene_nonce[0]);
}
''')
        subprocess.run(['gcc','-std=c11','-Wall','-Wextra',str(root/'framing.c'),'-o',str(root/'framing')],check=True)
        subprocess.run([str(root/'framing')],check=True)
if __name__=='__main__':main()
