/* SPDX-License-Identifier: GPL-3.0-only */
#include "world_z.h"
#include <math.h>
#include <string.h>

static bool finite_state(const WorldZ *s) {
  for (int i=0; i<3; ++i) {
    if (!isfinite(s->x[i]) || s->p[i][i]<0) return false;
    for (int j=0; j<3; ++j) if (!isfinite(s->p[i][j])) return false;
  }
  return true;
}
bool world_z_init(WorldZ *s, float z, float v, float bias,
                  float sz, float sv, float sb, float qa, float qb) {
  if (!s) return false;
  memset(s, 0, sizeof(*s));
  s->x[0]=z; s->x[1]=v; s->x[2]=bias;
  s->p[0][0]=sz*sz; s->p[1][1]=sv*sv; s->p[2][2]=sb*sb;
  s->qa=qa; s->qb=qb;
  s->healthy=finite_state(s) && isfinite(sz) && isfinite(sv) && isfinite(sb)
     && isfinite(qa) && isfinite(qb) && sz>=0 && sv>=0 && sb>=0 && qa>=0 && qb>=0;
  return s->healthy;
}
bool world_z_predict(WorldZ *s, float a, float t) {
  if (!s || !s->healthy) return false;
  if (!isfinite(a) || !isfinite(t) || t<=0 || t>0.1f) {
    s->healthy=false; return false;
  }
  float t2=t*t, t3=t2*t, t4=t3*t, t5=t4*t;
  const float f[3][3]={{1,t,-t2/2},{0,1,-t},{0,0,1}};
  float fp[3][3]={{0}}, p[3][3]={{0}};
  const float qa[3][3]={{t3/3,t2/2,0},{t2/2,t,0},{0,0,0}};
  const float qb[3][3]={{t5/20,t4/8,-t3/6},{t4/8,t3/3,-t2/2},{-t3/6,-t2/2,t}};
  for(int i=0;i<3;++i) for(int j=0;j<3;++j)
    for(int k=0;k<3;++k) fp[i][j]+=f[i][k]*s->p[k][j];
  for(int i=0;i<3;++i) for(int j=0;j<3;++j) {
    for(int k=0;k<3;++k) p[i][j]+=fp[i][k]*f[j][k];
    p[i][j]+=s->qa*qa[i][j]+s->qb*qb[i][j];
  }
  s->x[0]+=s->x[1]*t+(a-s->x[2])*t2/2;
  s->x[1]+=(a-s->x[2])*t;
  memcpy(s->p,p,sizeof(p));
  s->healthy=finite_state(s);
  return s->healthy;
}
static bool correct_gain(WorldZ *s, float y, float r, const float k[3]) {
  if (!s || !s->healthy) return false;
  if (!isfinite(y) || !isfinite(r) || r<=0) {s->healthy=false; return false;}
  const float innovation=y-s->x[0];
  float a[3][3]={{1,0,0},{0,1,0},{0,0,1}}, ap[3][3]={{0}}, p[3][3]={{0}};
  for(int i=0;i<3;++i) a[i][0]-=k[i];
  /* Joseph update: preserve positive semidefiniteness under finite precision. */
  for(int i=0;i<3;++i) for(int j=0;j<3;++j)
    for(int l=0;l<3;++l) ap[i][j]+=a[i][l]*s->p[l][j];
  for(int i=0;i<3;++i) for(int j=0;j<3;++j) {
    for(int l=0;l<3;++l) p[i][j]+=ap[i][l]*a[j][l];
    p[i][j]+=k[i]*r*k[j];
  }
  for(int i=0;i<3;++i) s->x[i]+=k[i]*innovation;
  memcpy(s->p,p,sizeof(p)); s->healthy=finite_state(s);
  return s->healthy;
}
bool world_z_baro(WorldZ *s, float y, float r) {
  if (!s || !s->healthy) return false;
  if (!isfinite(r) || r<=0) {s->healthy=false; return false;}
  float k[3];
  for(int i=0;i<3;++i) k[i]=s->p[i][0]/(s->p[0][0]+r);
  return correct_gain(s,y,r,k);
}
bool world_z_slow_baro(WorldZ *s, float y, float r, float dt, float omega) {
  if(!s || !s->healthy) return false;
  if(!isfinite(dt) || dt<=0 || dt>0.1f || !isfinite(omega) || omega<=0
     || omega*dt>=0.1f) {s->healthy=false; return false;}
  const float k[3]={2*omega*dt,omega*omega*dt,0};
  return correct_gain(s,y,r,k);
}
bool world_z_project(const float q[4], const float a[3], float *out) {
  if (!q || !a || !out) return false;
  float norm=0;
  for(int i=0;i<4;++i) {if(!isfinite(q[i])) return false; norm+=q[i]*q[i];}
  for(int i=0;i<3;++i) if(!isfinite(a[i])) return false;
  if(fabsf(norm-1)>0.02f) return false;
  /* Normalize to avoid turning quaternion norm error into vertical acceleration. */
  const float gx=2*(q[1]*q[3]-q[0]*q[2])/norm;
  const float gy=2*(q[0]*q[1]+q[2]*q[3])/norm;
  const float gz=(q[0]*q[0]-q[1]*q[1]-q[2]*q[2]+q[3]*q[3])/norm;
  *out=9.81f*(gx*a[0]+gy*a[1]+gz*a[2]-1);
  return isfinite(*out);
}
bool local_flow_velocity(float dx, float dy, float dt,
                         const float w[3], const float l[3], float r,
                         float age, float max_age, float r22, bool plane,
                         float out[2]) {
  if(!w || !l || !out || !plane || !isfinite(dx) || !isfinite(dy)
     || !isfinite(dt) || dt<=0 || dt>0.1f || !isfinite(r) || r<0.1f || r>=5
     || !isfinite(age) || !isfinite(max_age) || age<0 || max_age<0 || age>max_age
     || !isfinite(r22) || r22<0.5f || r22>1.001f) return false;
  for(int i=0;i<3;++i) if(!isfinite(w[i]) || !isfinite(l[i])) return false;
  const float scale=0.71674f/35.0f;
  out[0]=r*(dx*0.1f*scale/dt+w[1])-(w[1]*l[2]-w[2]*l[1]);
  out[1]=r*(dy*0.1f*scale/dt-w[0])-(w[2]*l[0]-w[0]*l[2]);
  return isfinite(out[0]) && isfinite(out[1]);
}
