/* A5 V2 Draft-only R2025a test driver: REAL native attempt and outcome
 * protocol, but NO flight, Blockly, motor writes, physical authorization
 * or claimed pupil success. It must fail closed on missing evaluator output.
 * This controller writes *only* the preexisting test Crazyflie customData.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <stdio.h>
#include <string.h>

#define PROBE "WEBEEBLOCKS_A5_V2_ATTEMPT_PROBE"
#define ORACLE "progression-reactive-L-v2"
static int stop(const char *why) {
  fprintf(stderr,PROBE "_FATAL %s\n",why);
  fflush(stderr);
  wb_robot_cleanup();
  return 2;
}
static int step_n(int n,int ms) {
  for(int i=0;i<n;++i)
    if(wb_robot_step(ms)==-1)return 0;
  return 1;
}
static WbNodeRef find_unique_crazyflie(void) {
  WbNodeRef root=wb_supervisor_node_get_root();
  WbFieldRef children=root?wb_supervisor_node_get_field(root,"children"):NULL;
  if(!children)return NULL;
  WbNodeRef craft=NULL;
  for(int i=0;i<wb_supervisor_field_get_count(children);++i){
    WbNodeRef node=wb_supervisor_field_get_mf_node(children,i);
    WbFieldRef name=node?wb_supervisor_node_get_field(node,"name"):NULL;
    const char *value=name?wb_supervisor_field_get_sf_string(name):NULL;
    if(value&&strcmp(value,"Crazyflie WebeeBlocks")==0){
      if(craft)return NULL;
      craft=node;
    }
  }
  return craft;
}
static int native_outcome(WbFieldRef f,unsigned long long n,int ms){
  char target[160];
  snprintf(target,sizeof target,
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=not-achieved",
    n,ORACLE);
  for(int i=0;i<24;++i){
    if(!step_n(1,ms))return 0;
    const char *value=wb_supervisor_field_get_sf_string(f);
    if(value&&strcmp(value,target)==0)return 1;
    if(value&&strstr(value,"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1"))
      return 0; /* wrong attempt/oracle/status */
  }
  return 0;
}
static int write_and_verify(WbFieldRef f,const char *value,int ms){
  wb_supervisor_field_set_sf_string(f,value);
  if(!step_n(3,ms))return 0;
  const char *got=wb_supervisor_field_get_sf_string(f);
  return got && strcmp(got,value)==0;
}
int main(void){
  wb_robot_init();
  int step=(int)wb_robot_get_basic_time_step();
  if(step<8||step>64)return stop("invalid Webots step");
  char variant=0;
  for(char v='A';v<='C';++v){
    char name[90];
    snprintf(name,sizeof name,"WEBEEBLOCKS_REACTIVE_L_V2_%c_SCENE",v);
    if(wb_supervisor_node_get_from_def(name)){
      if(variant)return stop("multiple physical A5 worlds");
      variant=v;
    }
  }
  if(!variant)return stop("A5 V2 scene absent");
  WbNodeRef craft=find_unique_crazyflie();
  WbFieldRef channel=craft?wb_supervisor_node_get_field(craft,"customData"):NULL;
  if(!channel)return stop("missing unique native original Crazyflie channel");
  const char *initial=wb_supervisor_field_get_sf_string(channel);
  if(initial&&initial[0])return stop("startup customData already modified");
  if(!step_n(5,step))return stop("native evaluator startup never progressed");

  /* Premature COMPLETE must not be mistaken for achievement. */
  if(!write_and_verify(channel,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1",step))
    return stop("attempt 1 not preserved by native channel");
  if(!write_and_verify(channel,
      "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=1 oracle=" ORACLE,step))
    return stop("premature completion 1 not submitted");
  if(!native_outcome(channel,1,step))
    return stop("premature completion 1 not rejected by native evaluator");
  printf(PROBE "_RESULT variant=%c attempt=1 status=not-achieved cause=premature-complete\n",
         variant);
  fflush(stdout);

  /* A fresh increasing attempt must be usable, without a stale outcome. */
  if(!write_and_verify(channel,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2",step))
    return stop("RESET attempt 2 not preserved");
  if(!step_n(4,step))return stop("native reset wait failed");
  const char *state=wb_supervisor_field_get_sf_string(channel);
  if(!state||strcmp(state,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2")!=0)
    return stop("previous negative outcome leaked into next attempt");
  if(!write_and_verify(channel,
      "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=2 oracle=" ORACLE,step))
    return stop("premature completion 2 not submitted");
  if(!native_outcome(channel,2,step))
    return stop("fresh attempt 2 not rejected independently");
  printf(PROBE "_RESULT variant=%c attempt=2 status=not-achieved cause=premature-complete\n",
         variant);
  printf(PROBE "_DONE variant=%c two_real_native_attempts=true "
         "fresh_reset=true no_pupil_flight=true\n",variant);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}
