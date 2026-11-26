"""Compile the real route-composed C transitions with bounded injected inputs.

No ODE, PID or native WWI proof is claimed here. The contact predicate and
flight branches are extracted from the exact generated route source; only
Webots contact samples, command delivery and forced-transfer inputs are stubs.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.grand_prix.prepare_u_runtime import prepare


def between(text, start, end):
    if text.count(start) != 1:
        raise AssertionError('missing/ambiguous generated C anchor: ' + start)
    tail = text.split(start, 1)[1]
    if end not in tail:
        raise AssertionError('missing generated C end: ' + end)
    return start + tail.split(end, 1)[0]


def harness(text):
    early = between(text, '    const int gp_land_contact_sampled =',
                    '    /* After genuine touchdown')
    transfer = between(text, '      land_start_z = z; /* Immediate LAND reference',
                       '      printf("GP_U_DEADLINE')
    stop = between(text, '      if (request.kind == REQUEST_STOP) {',
                   '      if (command != CMD_IDLE) {')
    contact = between(text, '      const int gp_contact_now =',
                      '      // Preserve the requested landing point')
    motor = between(text, '    if (land_touchdown) {\n      // Latch through loss of contact',
                    '      gp_multirate_pid(')
    predicate = between(text, 'static int land_has_ground_contact(', 'static void send_text(')
    return r'''#include <assert.h>
#include <stdio.h>
#include <math.h>
#include <stdbool.h>
#define ALT_TOL .05
#define PREFIX "WBB"
enum { CMD_IDLE, CMD_LAND, CMD_RESET };
enum { REQUEST_STOP };
typedef struct { double point[3]; } WbContactPoint;
static int floor_contact, motors, pending, expired;
static int forced_ack_errors, stop_refusals;
static WbContactPoint cp={{0,0,0}};
static void *wb_supervisor_node_get_self(void){return &cp;}
static const WbContactPoint *wb_supervisor_node_get_contact_points(void *node,bool include,int *count){
  (void)node;(void)include;*count=floor_contact;return floor_contact?&cp:NULL;
}
static void stop_motors(int m1,int m2,int m3,int m4){(void)m1;(void)m2;(void)m3;(void)m4;motors=0;}
static void simulation_clock_revoke(int *p){*p=0;}
static void response_error(int id,const char *s){
  (void)s;
  if(id==2147483646)++forced_ack_errors;
  if(id==18)++stop_refusals;
}
static void response_ok(int id){(void)id;}
static void gp_route_stop_land(void){pending=1;}
static int command,active_id,land_touchdown,airborne,failsafe_latched,program_clock;
static double land_start_z,stable_since,action_start,gp_land_contact_since,active_value,target_x,target_y,target_z,target_yaw;
static char active_direction[32];
''' + predicate + r'''
static void tick(int ms,int contact,int stop,int force){
  floor_contact=contact;
  double now=ms/1000.0,origin_z=.015,z=contact?.014978450958911526:.016260955052825998;
  double x=0,y=0,yaw=0;
  int m1=1,m2=2,m3=3,m4=4;
  struct {int kind,id;} request={REQUEST_STOP,18};
''' + early + r'''
  if(force || pending){
    expired=1;pending=0;
''' + transfer + r'''
  }
  /* Test parser delivery even if the external filter would normally reject
     an expired STOP (e.g. delayed/deferred STOP). */
  if(stop){do {
''' + stop + r'''
  }while(0);}
  if(command==CMD_LAND){
''' + contact + r'''
  }
''' + motor + r'''
    motors=1;
  }else{stop_motors(m1,m2,m3,m4);}
}
int main(void){
  for(int kind=0;kind<2;kind++)for(int phase=-8;phase<=8;phase+=8){
    pending=expired=land_touchdown=failsafe_latched=0;
    airborne=1;command=CMD_LAND;active_id=17;motors=1;
    gp_land_contact_since=-1;stable_since=-1;
    forced_ack_errors=stop_refusals=0;
    for(int ms=80;ms<=144;ms+=8){
      int contact=ms==96 || ms>=120;
      tick(ms,contact,kind==0&&ms==96+phase,kind==1&&ms==96+phase);
      if(ms>=96){assert(land_touchdown);assert(motors==0);}
      if(ms==104)assert(gp_land_contact_since<0);
    }
    assert(active_id==2147483646 && command==CMD_LAND);
    assert(gp_land_contact_since>=.12);
    /* A delayed STOP must not cancel the independent LAND or its latch. */
    tick(152,1,1,0);
    assert(active_id==2147483646 && command==CMD_LAND && land_touchdown && motors==0);
    assert(forced_ack_errors==0 && stop_refusals==1);
    printf("PHASE_PASS kind=%d phase=%d\n",kind,phase);
  }
  return 0;
}
'''


class LandLatchTests(unittest.TestCase):
    def test_generated_contact_stop_and_transfer_interleavings(self):
        cc = shutil.which('cc')
        self.assertIsNotNone(cc, 'C compiler required')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root / 'route', legacy_worlds=False, route_observations=True)
            source = (root / 'route/runtime_u.c').read_text()
            probe = root / 'phase.c'
            probe.write_text(harness(source))
            executable = root / 'phase'
            subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra',
                            str(probe), '-lm', '-o', str(executable)],
                           check=True, timeout=30)
            result = subprocess.run([str(executable)], check=True, capture_output=True,
                                    text=True, timeout=10)
            self.assertEqual(result.stdout.count('PHASE_PASS'), 6)
