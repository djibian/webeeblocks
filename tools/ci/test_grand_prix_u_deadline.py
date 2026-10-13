"""Compile the real native deadline hook against controlled Webots channels.
No simulation trajectory or hardware claim follows from these interleavings.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class DeadlineTests(unittest.TestCase):
    def test_exact_boundary_terminal_filter_and_new_attempt(self):
        compiler = shutil.which('c++')
        self.assertIsNotNone(compiler, 'C++ compiler required for real deadline source')
        with tempfile.TemporaryDirectory(prefix='gp-u-deadline-') as tmp:
            base = Path(tmp)
            (base/'webots/plugins/robot_window').mkdir(parents=True)
            (base/'webots/robot.h').write_text('extern "C" double wb_robot_get_time();\nextern "C" void wb_robot_wwi_send_text(const char*);\n')
            (base/'webots/plugins/robot_window/default.h').write_text('')
            (base/'webots/supervisor.h').write_text('''typedef void* WbNodeRef; typedef void* WbFieldRef;
extern "C" WbNodeRef wb_supervisor_node_get_from_def(const char*);
extern "C" WbNodeRef wb_supervisor_node_get_self();
extern "C" WbFieldRef wb_supervisor_node_get_field(WbNodeRef,const char*);
extern "C" void wb_supervisor_field_set_sf_string(WbFieldRef,const char*);
extern "C" const char* wb_supervisor_field_get_sf_string(WbFieldRef);
''')
            test = base/'test.cpp'
            test.write_text('''#include <cassert>
#include <string>
#include "grand_prix_u_hook.h"
std::string vehicle, evaluator, reply; double now=0; bool present=true;
extern "C" double wb_robot_get_time(){return now;}
extern "C" void wb_robot_wwi_send_text(const char* s){reply=s;}
extern "C" void* wb_supervisor_node_get_self(){return &vehicle;}
extern "C" void* wb_supervisor_node_get_from_def(const char*){return present?&evaluator:nullptr;}
extern "C" void* wb_supervisor_node_get_field(void* n,const char*){return n;}
extern "C" const char* wb_supervisor_field_get_sf_string(void* f){return static_cast<std::string*>(f)->c_str();}
extern "C" void wb_supervisor_field_set_sf_string(void* f,const char* v){*static_cast<std::string*>(f)=v;}
extern "C" const char* webeeblocks_file_broker_receive_text(){return nullptr;}
extern "C" void webeeblocks_file_broker_send(const char*,int){}
int main(){
 vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1";
 assert(gp_u_start(2.112)==1);
 now=212.096; assert(gp_u_next_step(32)==16);
 assert(gp_u_deadline(212.111,0)==0);
 assert(gp_u_deadline(212.112,0)==1);
 assert(evaluator=="GP_U_START attempt=1 start_ms=2112 state=deadline");
 assert(vehicle=="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-u-v1 status=not-achieved");
 for(const char* cmd:{"MOVE forward 0.1","LAND","STOP","RESET","COMPLETE grand-prix-u-v1","FAILURE grand-prix-u-v1"}){
  std::string m=std::string("WEBEEBLOCKS_RUNTIME_V2 REQUEST 17 ")+cmd;
  assert(gp_u_filter_raw(m.c_str())==0);assert(reply=="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 17 ERR TIME_LIMIT");
 }
 assert(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 18 OUTCOME grand-prix-u-v1")==1);
 assert(gp_u_deadline(212.120,0)==0); // one LAND trigger, no second effect
 assert(gp_u_deadline(220,1)==0);
 assert(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 19 RESET")==1);
 gp_u_reset_complete(); assert(evaluator.empty());
 vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2"; assert(gp_u_start(230)==1);
 assert(gp_u_deadline(230,0)==0);
 vehicle="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-u-v1 status=achieved";
 assert(gp_u_deadline(440,1)==1); // stale prior result cannot rescue attempt 2
 gp_u_reset_complete();vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 3";assert(gp_u_start(500)==1);
 vehicle="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=3 oracle=grand-prix-u-v1 status=achieved";
 assert(gp_u_deadline(709.999,1)==0);assert(gp_u_deadline(710,1)==0); // already completed before cap
 gp_u_reset_complete();present=false;vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 4";
 assert(gp_u_start(800)==0); // missing independent evaluator refuses TAKEOFF
}
''')
            binary=base/'test'
            subprocess.run([compiler,'-std=c++17','-I'+str(base),'-I'+str(ROOT/'controllers/grand_prix_u_flight'),
                str(test),str(ROOT/'controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp'),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True,timeout=10)

if __name__ == '__main__': unittest.main()
