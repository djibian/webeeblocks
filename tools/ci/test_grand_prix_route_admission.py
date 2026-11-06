"""Exercise the real route-mode C++ guard with controlled native channels.

These adversarial interleavings prove the hook's decisions, not a Webots flight.
The canonical native job additionally builds the complete route controller.
"""
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class VariableNativeAdmissionTests(unittest.TestCase):
    def test_real_guard_admission_liveness_deadline_and_reset(self):
        compiler = shutil.which('c++')
        self.assertIsNotNone(compiler, 'C++ compiler required for route admission')
        with tempfile.TemporaryDirectory(prefix='gp-route-admission-') as tmp:
            base = Path(tmp)
            (base / 'webots/plugins/robot_window').mkdir(parents=True)
            (base / 'webots/robot.h').write_text(
                'extern "C" double wb_robot_get_time();\n'
                'extern "C" void wb_robot_wwi_send_text(const char*);\n')
            (base / 'webots/plugins/robot_window/default.h').write_text('')
            (base / 'webots/supervisor.h').write_text('''typedef void* WbNodeRef; typedef void* WbFieldRef;
extern "C" WbNodeRef wb_supervisor_node_get_from_def(const char*);
extern "C" WbNodeRef wb_supervisor_node_get_self();
extern "C" WbFieldRef wb_supervisor_node_get_field(WbNodeRef,const char*);
extern "C" void wb_supervisor_field_set_sf_string(WbFieldRef,const char*);
extern "C" const char* wb_supervisor_field_get_sf_string(WbFieldRef);
extern "C" int wb_supervisor_field_get_count(WbFieldRef);
extern "C" const char* wb_supervisor_field_get_mf_string(WbFieldRef,int);
''')
            test = base / 'test.cpp'
            test.write_text(r'''#include <cassert>
#include <cmath>
#include <cstring>
#include <limits>
#include <string>
#include "grand_prix_u_hook.h"
std::string vehicle, request, evidence, config, reply, sample;
const std::string canonical="gp-route-v2-L2000-2500-3000-TGD-s17-H2";
int argsCount=1; double now=2.112; bool present=true, description=true;
extern "C" double wb_robot_get_time(){return now;}
extern "C" void wb_robot_wwi_send_text(const char* s){reply=s;}
extern "C" void* wb_supervisor_node_get_self(){return &vehicle;}
extern "C" void* wb_supervisor_node_get_from_def(const char* def){
 assert(!std::strcmp(def,"GP_ROUTE_EVALUATOR"));return present?&request:nullptr;
}
extern "C" void* wb_supervisor_node_get_field(void* node,const char* field){
 if(node==&vehicle){
  if(!std::strcmp(field,"customData"))return &vehicle;
  if(!std::strcmp(field,"controllerArgs"))return &config;
 }else if(node==&request){
  if(!std::strcmp(field,"customData"))return &request;
  if(!std::strcmp(field,"model"))return &sample;
  if(!std::strcmp(field,"description"))return description?&evidence:nullptr;
 }
 return nullptr;
}
extern "C" const char* wb_supervisor_field_get_sf_string(void* f){return static_cast<std::string*>(f)->c_str();}
extern "C" void wb_supervisor_field_set_sf_string(void* f,const char* value){
 assert(f!=&evidence); // The flight side must never overwrite evaluator evidence.
 *static_cast<std::string*>(f)=value;
}
extern "C" int wb_supervisor_field_get_count(void* f){assert(f==&config);return argsCount;}
extern "C" const char* wb_supervisor_field_get_mf_string(void* f,int index){assert(f==&config&&index==0);return config.c_str();}
extern "C" const char* webeeblocks_file_broker_receive_text(){return nullptr;}
extern "C" void webeeblocks_file_broker_send(const char*,int){}
std::string challenge;
void fresh(){
 present=true;description=true;gp_u_reset_complete();
 vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1";
 config=canonical;argsCount=1;now=2.112;evidence.clear();reply.clear();
 gp_u_file_idle(1);challenge=request;
 assert(challenge.find("GP_ROUTE_CHALLENGE_V1 attempt=1 config="+canonical+" epoch=")==0);
 assert(challenge.substr(challenge.find(" epoch=")+7).size()==32);
}
std::string response(const char* kind,const std::string& time){
 return std::string("GP_ROUTE_")+kind+"_V1"+
  challenge.substr(std::strlen("GP_ROUTE_CHALLENGE_V1"))+" time_ms="+time;
}
void ready(){evidence=response("READY","2112");}
void admit(){fresh();ready();assert(gp_u_start(now)==1);}
void alive(long long ms){now=ms/1000.0;evidence=response("ALIVE",std::to_string(ms));}
const std::string failed="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-route-v2 status=not-achieved";
const std::string achieved="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-route-v2 status=achieved";
void oneLand(){
 assert(gp_u_deadline(now,0)==1);assert(vehicle==failed);
 vehicle=achieved;assert(gp_u_deadline(now+0.032,1)==0);assert(vehicle==failed);
}
void query(int expected){
 const std::string beforeRequest=request,beforeEvidence=evidence,beforeSample=sample;
 assert(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 91 ADMISSION")==0);
 assert(reply=="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 91 VALUE "+std::to_string(expected));
 assert(request==beforeRequest && evidence==beforeEvidence && sample==beforeSample);
}
int main(){
 // ADMISSION observes only the current native READY; it never creates authority.
 fresh();query(0);assert(request==challenge);ready();query(1);query(1);
 assert(vehicle=="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
 now=2.144;query(1);now=2.145;query(0);now=2.111;query(0);
 now=std::numeric_limits<double>::quiet_NaN();query(0);now=2.112;query(1);
 present=false;query(0);present=true;description=false;query(0);description=true;
 config="gp-route-v2-L2000-2500-3000-TDG-s17-H2";query(0);config=canonical;
 vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2";query(0);
 vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1";query(1);
 assert(gp_u_start(now)==1);query(0); // peek did not consume READY or start the clock
 alive(2144);query(0);assert(gp_u_deadline(now,0)==0); // peek never consumes ALIVE
 fresh();ready();std::string peekStale=evidence;gp_u_reset_complete();gp_u_file_idle(1);
 evidence=peekStale;query(0); // old epoch is refused even at the same timestamp/attempt
 fresh();ready();gp_u_file_idle(0);query(0);
 fresh();assert(gp_u_start(now)==0);ready();query(0); // failed admission stays unavailable
 for(const char* raw:{"WEBEEBLOCKS_RUNTIME_V2 REQUEST 0 ADMISSION",
                     "WEBEEBLOCKS_RUNTIME_V2 REQUEST -1 ADMISSION",
                     "WEBEEBLOCKS_RUNTIME_V2 REQUEST 091 ADMISSION",
                     "WEBEEBLOCKS_RUNTIME_V2 REQUEST 2147483648 ADMISSION",
                     "WEBEEBLOCKS_RUNTIME_V2 REQUEST 91 ADMISSION extra"}){
  fresh();ready();reply.clear();assert(gp_u_filter_raw(raw)==1);assert(reply.empty());
 }
 // Presence, identity strings and a leftover READY never establish admission.
 fresh();assert(gp_u_start(now)==0);
 fresh();ready();present=false;assert(gp_u_start(now)==0);
 fresh();ready();description=false;assert(gp_u_start(now)==0);
 for(const char* time:{"2079","2113","+2112","02112","2112 ","2112junk","-1","9223372036854775808"}){
  fresh();evidence=response("READY",time);assert(gp_u_start(now)==0);
 }
 fresh();now=2.144;evidence=response("READY","2080");assert(gp_u_start(now)==0); // predates challenge
 for(const char* wrong:{"attempt=1","config=gp-route-v2-","epoch="}){
  fresh();ready();auto position=evidence.find(wrong)+std::strlen(wrong);
  evidence.insert(position,"0");assert(gp_u_start(now)==0);
 }
 for(const char* bad:{"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 0","WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 01",
                     "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 -1","WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1junk"}){
  fresh();ready();vehicle=bad;gp_u_file_idle(1);assert(gp_u_start(now)==0);
 }
 for(const char* bad:{"grand-prix-u-v1","gp-route-v2- with-space","gp-route-v2-\n"}){
  fresh();ready();config=bad;gp_u_file_idle(1);assert(gp_u_start(now)==0);
 }
 for(int count:{0,2}){fresh();ready();argsCount=count;gp_u_file_idle(1);assert(gp_u_start(now)==0);}
 fresh();ready();config=std::string(81,'x');gp_u_file_idle(1);assert(gp_u_start(now)==0);
 fresh();ready();config="gp-route-v2-L2000-2500-3000-TDG-s17-H2";assert(gp_u_start(now)==0);
 fresh();ready();gp_u_file_idle(0);assert(gp_u_start(now)==0);
 // RESET and lost idle each invalidate even a same-attempt, same-time response.
 fresh();ready();std::string stale=evidence;std::string old=challenge;
 gp_u_reset_complete();gp_u_file_idle(1);assert(request!=old);evidence=stale;assert(gp_u_start(now)==0);
 fresh();ready();stale=evidence;old=challenge;
 gp_u_file_idle(0);gp_u_file_idle(1);assert(request!=old);evidence=stale;assert(gp_u_start(now)==0);
 fresh();ready();stale=evidence;vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2";
 gp_u_file_idle(1);evidence=stale;assert(gp_u_start(now)==0);
 // Repeated idle polling does not destroy READY: distinct, single-writer channels.
 fresh();ready();stale=evidence;gp_u_file_idle(1);assert(evidence==stale);
 assert(gp_u_start(now)==1);assert(evidence==stale);
 assert(request.find("GP_ROUTE_START_V1 attempt=1 config="+canonical)==0);
 assert(request.find(" start_ms=2112 state=admitted")!=std::string::npos);
 assert(gp_u_start(now)==0); // a second admission cannot restart the clock
 // A new native observation is required each pilot tick, not merely a live node.
 admit();alive(2144);assert(gp_u_deadline(now,0)==0);
 now=2.176;oneLand(); // frozen ALIVE is within age budget but has already been consumed
 admit();alive(2144);evidence=response("READY","2144");oneLand();
 admit();alive(2144);evidence=response("ALIVE","2111");oneLand();
 admit();alive(2144);evidence=response("ALIVE","2112");oneLand();
 admit();alive(2144);evidence=response("ALIVE","2145");oneLand();
 admit();alive(2144);present=false;oneLand();
 admit();alive(2144);config="gp-route-v2-L2000-2500-3000-TDG-s17-H2";oneLand();
 admit();alive(2144);evidence.insert(evidence.find("epoch=")+6,"0");oneLand();
 admit();now=std::numeric_limits<double>::quiet_NaN();assert(gp_u_next_step(32)==32);oneLand();
 admit();now=2.111;oneLand();
 // Failure remains terminal, files stay fenced, RESET waits for actual landing.
 admit();alive(2144);evidence.clear();oneLand();
 assert(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 17 RESET")==1); // oneLand observed landed=1
 gp_u_deadline(now+0.064,0);
 assert(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 17 RESET")==0);
 assert(gp_u_filter_raw("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 77 OPEN")==0);
 assert(reply=="WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 77 ERR BUSY");
 vehicle=achieved;assert(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 18 OUTCOME grand-prix-route-v2")==1);
 assert(vehicle==failed);
 // Freshness does not relax the exact cap, even with an achieved outcome.
 for(int elapsed:{209999,210000,210001}){
  admit();alive(2112+elapsed);vehicle=achieved;
  assert(gp_u_deadline(now,1)==(elapsed>=210000));
  if(elapsed<210000){now=212.112;assert(gp_u_deadline(now,1)==0);}
  else {assert(vehicle==failed);assert(request.find("state=deadline")!=std::string::npos);}
 }
 // At the off-grid origin the native step is shortened to the exact 8 ms grid cap.
 admit();alive(212096);assert(gp_u_deadline(now,0)==0);assert(gp_u_next_step(32)==16);
 alive(212112);vehicle=achieved;assert(gp_u_deadline(now,1)==1);assert(vehicle==failed);
 // Airborne success cannot disarm; a later stale success cannot rescue failure.
 admit();alive(212111);vehicle=achieved;assert(gp_u_deadline(now,0)==0);
 alive(212112);assert(gp_u_deadline(now,1)==1);assert(vehicle==failed);
 // A healthy evaluator can sustain the entire native pilot interval to the cap.
 admit();
 for(long long t=2144;t<212112;t+=32){alive(t);assert(gp_u_deadline(now,0)==0);}
 alive(212112);assert(gp_u_deadline(now,0)==1);assert(vehicle==failed);
 gp_u_deadline(now+0.032,1);gp_u_reset_complete();
 assert(request.empty());assert(gp_u_filter_raw("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 77 OPEN")==0);
 vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2";gp_u_file_idle(1);
 challenge=request;evidence=response("READY","212112");assert(gp_u_start(now)==1);
 // Real snapshot writer, same compiled hook as the native flight controller.
 const double ranges[5]={0.,.2,1.234567,2.,2.001};
 fresh();gp_route_observe_native(now,1,1,ranges);
 assert(sample=="GP_ROUTE_SAMPLE_V1"+challenge.substr(std::strlen("GP_ROUTE_CHALLENGE_V1"))+
  " time_ms=2112 period_ms=32 ground=1 ranges_um=0,200000,1234567,2000000,2001000");
 std::printf("GP_ROUTE_CAPTURED %s|%s\n",challenge.c_str(),sample.c_str());
 // Sampling does not overwrite the outcome or the evaluator-owned fields.
 assert(vehicle=="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");assert(request==challenge);assert(evidence.empty());
 gp_route_observe_native(now,1,1,ranges);assert(sample.empty()); // no invented refresh
 fresh();now=2.128;gp_route_observe_native(now,1,0,ranges);assert(!sample.empty());
 assert(sample.find("time_ms=2128 period_ms=32")!=std::string::npos);
 gp_u_file_idle(0);assert(sample.empty());
 for(int fault=0;fault<11;++fault){
  fresh();gp_route_observe_native(now,1,1,ranges);assert(!sample.empty());
  double changed[5]={0.,.2,1.234567,2.,2.001};
  now=2.144;
  if(fault==0)changed[0]=std::numeric_limits<double>::quiet_NaN();
  if(fault==1)changed[1]=std::numeric_limits<double>::infinity();
  if(fault==2)changed[2]=-.001;
  if(fault==3)changed[3]=2.001001;
  if(fault==4)config="gp-route-v2-L2000-2500-3000-TDG-s17-H2";
  if(fault==5)vehicle="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2";
  if(fault==6)now=2.113; // outside the native 8-ms clock grid
  if(fault==7)now=2.080; // clock rewind
  gp_route_observe_native(now,fault==8?0:1,fault==9?2:1,fault==10?nullptr:changed);
  assert(sample.empty());
 }
 fresh();gp_route_observe_native(now,1,1,ranges);std::string previous=sample;
 gp_u_reset_complete();assert(sample.empty());gp_u_file_idle(1);challenge=request;
 gp_route_observe_native(now,1,1,ranges);assert(!sample.empty()&&sample!=previous);
 std::printf("GP_ROUTE_CAPTURED %s|%s\n",challenge.c_str(),sample.c_str());
 admit();vehicle="WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=1 oracle=grand-prix-route-v2";
 gp_u_file_idle(0);now=2.144;gp_route_observe_native(now,1,0,ranges);
 assert(!sample.empty()); // active attempt binds the private epoch, not the completion text
 std::printf("GP_ROUTE_CAPTURED %s|%s\n",request.c_str(),sample.c_str());
 admit();now=212.112;gp_route_observe_native(now,1,0,ranges);assert(sample.empty());
 assert(gp_u_deadline(now,0)==1); // snapshot publication cannot rescue exact expiry
}
''')
            binary = base / 'test'
            subprocess.run([
                compiler, '-std=c++17', '-DWEBEEBLOCKS_GP_ROUTE_MODE',
                '-I' + str(base), '-I' + str(ROOT / 'controllers/grand_prix_u_flight'),
                str(test), str(ROOT / 'controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp'),
                '-o', str(binary),
            ], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr)
            from tools.grand_prix.route_evaluator_wire_v2 import parse_flight_channel
            from tools.grand_prix.route_flight_observation_v2 import parse_flight_observation
            captures = [line.split(' ', 1)[1].split('|') for line in result.stdout.splitlines()
                        if line.startswith('GP_ROUTE_CAPTURED ')]
            self.assertEqual(len(captures), 3)
            for i, (channel, raw) in enumerate(captures):
                config = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2'
                event = parse_flight_channel(channel, config)
                observed = parse_flight_observation(raw, event, 2144 if i == 2 else 2112)
                self.assertEqual(observed.ranges_m, (0., .2, 1.234567, 2., 2.001))
                self.assertEqual(observed.ground_confirmed, i != 2)



if __name__ == '__main__':
    unittest.main()
