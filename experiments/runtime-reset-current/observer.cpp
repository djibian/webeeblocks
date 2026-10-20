/* Diagnostic ODE reads only; collision return 0 preserves normal handling. */
#include <plugins/physics.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <stdint.h>
#include <inttypes.h>
#include "WbMotor.hpp"
#include "WbPropeller.hpp"
static WbMotor *motors[4];
static WbPropeller *propellers[4];
static dBodyID body;
static FILE *stream;
static int count,overflow;
typedef struct {dContactGeom contact; uintptr_t first,second;} observation;
static observation contacts[128];
static void number(double x) {
  if(isfinite(x))fprintf(stream,"%.17g",x);
  else fprintf(stream,"\"%s\"",isnan(x)?"nan":x>0?"inf":"-inf");
}
static void array(const dReal *a,int n) {
  fputc('[',stream);for(int i=0;i<n;i++){if(i)fputc(',',stream);number(a[i]);}fputc(']',stream);
}
void webots_physics_init(void) {
  body=dWebotsGetBodyFromDEF("CI_AUTONOMOUS_CRAZYFLIE");
  const char *dir=getenv("WEBEEBLOCKS_CI_ARTIFACT_DIR");char path[2048];
  if(!body||!dir){fprintf(stderr,"ERROR: PHYSICS_OBSERVER_PREPARATION\n");return;}
  snprintf(path,sizeof(path),"%s/physics-state.jsonl",dir);stream=fopen(path,"w");
  if(!stream){fprintf(stderr,"ERROR: PHYSICS_OBSERVER_FILE\n");return;}
  for(int id=0;id<10000;++id) {
    WbMotor *motor=dynamic_cast<WbMotor *>(WbNode::findNode(id));
    if(!motor)continue;
    for(int i=0;i<4;++i) {
      const QString wanted=QString("m%1_motor").arg(i+1);
      if(motor->deviceName()!=wanted)continue;
      if(motors[i]){fprintf(stderr,"ERROR: DUPLICATE_NATIVE_MOTOR\n");exit(81);}
      motors[i]=motor;propellers[i]=motor->propeller();
    }
  }
  for(int i=0;i<4;++i)if(!motors[i]||!propellers[i]){fprintf(stderr,"ERROR: NATIVE_MOTOR_MISSING\n");exit(82);}
  fprintf(stream,"{\"type\":\"motor_identity\",\"source\":\"direct R2025a native getters\",\"node_ids\":[%d,%d,%d,%d]}\n",
    motors[0]->uniqueId(),motors[1]->uniqueId(),motors[2]->uniqueId(),motors[3]->uniqueId());
  fputs("{\"type\":\"header\",\"scope\":\"ODE-step-end-read-only; contact candidates are not force measurements\",\"state_time_offset_seconds\":0.032}\n",stream);fflush(stream);
}
void webots_physics_step(void) {count=0;overflow=0;}
int webots_physics_collide(dGeomID a,dGeomID b) {
  if(!body||dGeomIsSpace(a)||dGeomIsSpace(b))return 0;
  if(dGeomGetBody(a)!=body&&dGeomGetBody(b)!=body)return 0;
  dContactGeom points[32];int n=dCollide(a,b,32,points,sizeof(dContactGeom));
  for(int i=0;i<n;i++) {
    if(count==128){overflow=1;break;}
    contacts[count].contact=points[i];contacts[count].first=(uintptr_t)a;contacts[count].second=(uintptr_t)b;count++;
  }
  return 0;
}
void webots_physics_step_end(void) {
  if(!stream||!body)return;
  double engine_ms=dWebotsGetTime();
  fprintf(stream,"{\"type\":\"sample\",\"engine_time_ms\":%.9f,\"time\":%.9f,\"position\":",engine_ms,engine_ms/1000.+.032);
  array(dBodyGetPosition(body),3);
  const dReal *m=dBodyGetRotation(body);
  double rotation[9]={m[0],m[1],m[2],m[4],m[5],m[6],m[8],m[9],m[10]};
  fputs(",\"orientation\":",stream);array(rotation,9);
  const dReal *v=dBodyGetLinearVel(body),*w=dBodyGetAngularVel(body);
  double six[6]={v[0],v[1],v[2],w[0],w[1],w[2]};
  fputs(",\"velocity\":",stream);array(six,6);
  double current[4],thrust[4],torque[4];
  for(int i=0;i<4;++i){current[i]=motors[i]->currentVelocity();thrust[i]=propellers[i]->currentThrust();torque[i]=propellers[i]->currentTorque();}
  fputs(",\"motor_current\":",stream);array(current,4);
  fputs(",\"propeller_thrust\":",stream);array(thrust,4);
  fputs(",\"propeller_torque\":",stream);array(torque,4);
  int joints=0;for(int i=0;i<dBodyGetNumJoints(body);i++)if(dJointGetType(dBodyGetJoint(body,i))==dJointTypeContact)joints++;
  fprintf(stream,",\"contact_joint_count\":%d,\"candidate_overflow\":%d,\"contacts\":[",joints,overflow);
  for(int i=0;i<count;i++) {
    if(i)fputc(',',stream);
    fputs("{\"point\":",stream);array(contacts[i].contact.pos,3);
    fputs(",\"normal\":",stream);array(contacts[i].contact.normal,3);
    fprintf(stream,",\"depth\":%.17g,\"node_id\":null,\"geometry_pair\":[\"%" PRIxPTR "\",\"%" PRIxPTR "\"]}",
      contacts[i].contact.depth,contacts[i].first,contacts[i].second);
  }
  fputs("]}\n",stream);if(fflush(stream))fprintf(stderr,"ERROR: PHYSICS_OBSERVER_WRITE\n");
}
void webots_physics_cleanup(void) {if(stream)fclose(stream);stream=NULL;}
