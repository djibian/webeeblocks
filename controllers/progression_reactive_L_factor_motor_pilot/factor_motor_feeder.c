/* Private CI-only WWI command feeder for A5 H-fixed / G-variable worlds.
 * When the opt-in environment flag is ABSENT, this wrapper is a transparent
 * relay to the genuine Webots WWI functions; the browser path is unchanged.
 * When enabled, the unmodified runtime/PID processes the exact native
 * REQUEST protocol. No student Blockly, Robot Window, physical radio or
 * external actuator permission is present in this experiment.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <math.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern const char *__real_wb_robot_wwi_receive_text(void);
#define PREFIX "WEBEEBLOCKS_RUNTIME_V2"
static const char NONCE[] =
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static int initialized=0,enabled=0,blind=0;
static int variant=0,stage=0,pending=0,finished=0,failed=0,go_left=-1;
static double measured=0;
static char request[256];
static void fail(const char *why) {
  if(!failed) {
    fprintf(stderr,"WEBEEBLOCKS_A5_FACTOR_FEEDER_FATAL %s stage=%d\n",why,stage);
    fflush(stderr);
  }
  failed=1;
}
static void initialize(void) {
  if(initialized)return;
  initialized=1;
  const char *flag=getenv("WEBEEBLOCKS_A5_FACTOR_NATIVE_FEEDER");
  if(!flag||!flag[0])return;
  if(strcmp(flag,"positive")&&strcmp(flag,"blind")){fail("unknown feeder mode");return;}
  enabled=1;blind=!strcmp(flag,"blind");
  const int L=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GL_SCENE")!=NULL;
  const int R=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GR_SCENE")!=NULL;
  if(L==R){fail("missing unique physical scene");return;}
  variant=L?'A':'B';
  if(blind&&variant!='B'){fail("blind must challenge G-right");return;}
  printf("WEBEEBLOCKS_A5_FACTOR_FEEDER_INIT variant=%c mode=%s "
         "browser_bypassed=true physical_pid_original=true\n",
         variant,blind?"blind":"positive");
  fflush(stdout);
}
static int build(int index,char *out,size_t n){
  int id=index+1;
  switch(index){
    case 0:
      return snprintf(out,n,PREFIX " REQUEST %d SCENE %s %s",id,
        variant=='A'?"a5-factor-g-left-proto":"a5-factor-g-right-proto",NONCE);
    case 1:return snprintf(out,n,PREFIX " REQUEST %d SPEED 0.16",id);
    case 2:return snprintf(out,n,PREFIX " REQUEST %d TAKEOFF 0.50",id);
    case 3:case 4:return snprintf(out,n,PREFIX " REQUEST %d MOVE forward 1.20",id);
    case 5:return snprintf(out,n,PREFIX " REQUEST %d MOVE forward 0.10",id);
    case 6:return snprintf(out,n,PREFIX " REQUEST %d RANGE left",id);
    case 7:return snprintf(out,n,PREFIX " REQUEST %d TURN %d",id,go_left?90:-90);
    case 8:return snprintf(out,n,PREFIX " REQUEST %d MOVE forward 0.60",id);
    case 9:return snprintf(out,n,PREFIX " REQUEST %d TURN %d",id,go_left?-90:90);
    case 10:return snprintf(out,n,PREFIX " REQUEST %d MOVE forward 0.85",id);
    case 11:return snprintf(out,n,PREFIX " REQUEST %d MOVE forward 0.80",id);
    case 12:
      if(go_left)return snprintf(out,n,PREFIX " REQUEST %d LAND",id);
      return snprintf(out,n,PREFIX " REQUEST %d TURN 90",id);
    case 13:
      if(!go_left)return snprintf(out,n,PREFIX " REQUEST %d MOVE forward 1.24",id);
      break;
    case 14:
      if(!go_left)return snprintf(out,n,PREFIX " REQUEST %d LAND",id);
      break;
  }
  return -1;
}
const char *__wrap_wb_robot_wwi_receive_text(void){
  initialize();
  if(!enabled)return __real_wb_robot_wwi_receive_text();
  if(failed||finished||pending)return NULL;
  if(wb_robot_get_time()<2.5)return NULL; /* physical pose settled */
  const int n=build(stage,request,sizeof request);
  if(n<=0||(size_t)n>=sizeof request){fail("invalid bounded test request");return NULL;}
  pending=1;
  printf("WEBEEBLOCKS_A5_FACTOR_FEEDER_COMMAND id=%d stage=%d\n",stage+1,stage);
  fflush(stdout);
  return request;
}
void __wrap_wb_robot_wwi_send_text(const char *message){
  initialize();
  if(!enabled){
    /* The Webots R2025a controller may expose its WWI send function via
     * its loaded shared library, not as a link-time __real_ symbol.
     * Preserve original browser transport ONLY if an actual dynamic
     * implementation is available; fail closed rather than fake delivery. */
    void (*relay)(const char *)=
      (void (*)(const char *))dlsym(RTLD_NEXT,"wb_robot_wwi_send_text");
    if(!relay){fail("real_wwi_send_passthrough_unavailable");return;}
    relay(message);
    return;
  }
  if(!message||strncmp(message,PREFIX " RESPONSE ",strlen(PREFIX " RESPONSE ")))return;
  int id=-1;
  char kind[24]={0};
  if(sscanf(message,PREFIX " RESPONSE %d %23s",&id,kind)!=2||
     id!=stage+1||!pending){fail("out-of-order or unpaired response");return;}
  if(!strcmp(kind,"ERR")){fail(message);return;}
  const int success=!strcmp(kind,"OK")||!strcmp(kind,"SCENE_OK")||!strcmp(kind,"VALUE");
  if(!success){fail("invalid native response type");return;}
  if(stage==0){
    char exact[192];
    snprintf(exact,sizeof exact,PREFIX " RESPONSE 1 SCENE_OK %s",NONCE);
    if(strcmp(message,exact)){fail("missing original scene nonce");return;}
  }else if(stage==6){
    double value=-1;
    if(sscanf(message,PREFIX " RESPONSE 7 VALUE %lf",&value)!=1||
       !isfinite(value)||value<0||value>2.001){
      fail("native G range absent");return;
    }
    measured=value;
    go_left=blind?1:(value>1.0);
    printf("WEBEEBLOCKS_A5_FACTOR_FEEDER_LATE_RANGE variant=%c "
           "left_m=%.9f route=%s mode=%s\n",
           variant,measured,go_left?"left":"right",blind?"blind":"positive");
    fflush(stdout);
  }else if(strcmp(kind,"OK")){fail("unexpected non-OK motion response");return;}
  printf("WEBEEBLOCKS_A5_FACTOR_FEEDER_ACK id=%d kind=%s\n",id,kind);
  fflush(stdout);
  pending=0;
  const int last=(go_left?12:14);
  if(stage==last){
    if(strcmp(kind,"OK")){fail("LAND not confirmed");return;}
    finished=1;
    printf("WEBEEBLOCKS_A5_FACTOR_FEEDER_DONE variant=%c route=%s "
           "last_id=%d late_left_m=%.9f original_pid=true\n",
           variant,go_left?"left":"right",id,measured);
    fflush(stdout);
    return;
  }
  stage++;
}
