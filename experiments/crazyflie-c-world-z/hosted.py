#!/usr/bin/env python3
"""Build host-only C observer + pinned Bitcraze attitude/measurement routines.

No radio libraries, hardware APIs or binary intended for flashing.
"""
from __future__ import annotations
import ctypes as ct
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'upstream.json').read_text())

class WorldZ(ct.Structure):
    _fields_ = [('x', ct.c_float * 3), ('p', (ct.c_float * 3) * 3),
                ('qa', ct.c_float), ('qb', ct.c_float), ('healthy', ct.c_bool)]

STUB = r'''
#ifndef LAB_STUB_H
#define LAB_STUB_H
#include <math.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#define M_PI_F 3.14159265358979323846f
#define DEG_TO_RAD (M_PI_F/180.0f)
#define FLOWDECK_POS_X 0.0f
#define FLOWDECK_POS_Y 0.0f
#define FLOWDECK_POS_Z 0.0f
#define LOG_GROUP_START(...)
#define LOG_GROUP_STOP(...)
#define LOG_ADD(...)
#define LOG_ADD_CORE(...)
#define PARAM_GROUP_START(...)
#define PARAM_GROUP_STOP(...)
#define PARAM_ADD(...)
#define PARAM_ADD_CORE(...)
typedef union {struct {float x,y,z;}; float axis[3];} Axis3f;
typedef struct {uint16_t numRows,numCols; float *pData;} arm_matrix_instance_f32;
enum {KC_STATE_X,KC_STATE_Y,KC_STATE_Z,KC_STATE_PX,KC_STATE_PY,KC_STATE_PZ,
      KC_STATE_D0,KC_STATE_D1,KC_STATE_D2,KC_STATE_DIM};
/* Shim layout, not an ABI definition for the firmware. */
typedef struct {float S[9]; float R[3][3]; float P[9][9];} kalmanCoreData_t;
typedef struct {float dt,dpixelx,dpixely,stdDevX,stdDevY;} flowMeasurement_t;
typedef struct {float distance,stdDev;} tofMeasurement_t;
void kalmanCoreScalarUpdate(kalmanCoreData_t*,arm_matrix_instance_f32*,float,float);
void kalmanCoreUpdateWithFlow(kalmanCoreData_t*,const flowMeasurement_t*,const Axis3f*);
void kalmanCoreUpdateWithTof(kalmanCoreData_t*,tofMeasurement_t*);
#endif
'''
SCALAR = r'''
#include "shim.h"
/* Standard scalar KF/Joseph algebra. No firmware propagation, clamping,
 * supervisor, scheduling or attitude error finalization is emulated here. */
void kalmanCoreScalarUpdate(kalmanCoreData_t *s, arm_matrix_instance_f32 *h,
                           float residual, float std) {
  float k[9]={0}, variance=std*std, a[9][9]={{0}}, ap[9][9]={{0}}, p[9][9]={{0}};
  for(int i=0;i<9;i++) {for(int j=0;j<9;j++) k[i]+=s->P[i][j]*h->pData[j];
    variance+=h->pData[i]*k[i];}
  for(int i=0;i<9;i++) {k[i]/=variance; s->S[i]+=k[i]*residual;
    for(int j=0;j<9;j++) a[i][j]=(i==j)-k[i]*h->pData[j];}
  for(int i=0;i<9;i++) for(int j=0;j<9;j++)
    for(int l=0;l<9;l++) ap[i][j]+=a[i][l]*s->P[l][j];
  for(int i=0;i<9;i++) for(int j=0;j<9;j++) {
    for(int l=0;l<9;l++) p[i][j]+=ap[i][l]*a[j][l];
    p[i][j]+=k[i]*std*std*k[j];}
  memcpy(s->P,p,sizeof(p));
}
float lab_stock_tof(float z, float range) {
  kalmanCoreData_t s={0}; s.S[KC_STATE_Z]=z; s.R[2][2]=1; s.P[2][2]=0.04f;
  tofMeasurement_t t={range,0.0025f}; kalmanCoreUpdateWithTof(&s,&t);
  return s.S[KC_STATE_Z];
}
float lab_stock_flow_z(float z, float vx, float local_depth, float cross) {
  kalmanCoreData_t s={0}; s.S[2]=z; s.S[3]=vx; s.R[2][2]=1;
  s.P[2][2]=s.P[3][3]=s.P[4][4]=0.04f; s.P[2][3]=s.P[3][2]=cross;
  flowMeasurement_t f={0.01f,0.01f*35/0.71674f*vx/local_depth/0.1f,0,2,2};
  Axis3f g={0}; kalmanCoreUpdateWithFlow(&s,&f,&g); return s.S[2];
}
float lab_zero_hz_coupling(void) {
  kalmanCoreData_t s={0}; s.P[2][2]=s.P[3][3]=0.04f;
  s.P[2][3]=s.P[3][2]=0.015f;
  float h[9]={0}; h[3]=1; arm_matrix_instance_f32 H={1,9,h};
  kalmanCoreScalarUpdate(&s,&H,0.2f,0.1f); return s.S[2];
}
'''
RESET = r'''
/* Host-only repeatability reset; not a firmware/public parameter operation. */
void lab_attitude_reset(void) {
 qw=1; qx=qy=qz=0; gravX=gravY=0; gravZ=1; baseZacc=1;
 isInit=false; isCalibrated=false;
 integralFBx=integralFBy=integralFBz=0; twoKp=TWO_KP_DEF; twoKi=TWO_KI_DEF;
 sensfusion6Init();
}
/* Host experiment only: hold gravity correction off for a bounded interval.
 * Uses the official quaternion gyro propagation without a ToF/Flow correction. */
void lab_attitude_gyro_only(void) {
 twoKp=twoKi=0; integralFBx=integralFBy=integralFBz=0;
}
'''

def validate_upstream(root: Path) -> None:
    sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != LOCK['commit']:
        raise ValueError(f'exact upstream required: {LOCK["commit"]}, got {sha}')
    for path, digest in LOCK['sha256'].items():
        if hashlib.sha256((root/path).read_bytes()).hexdigest() != digest:
            raise ValueError(f'changed/missing upstream bytes: {path}')

def build(directory: Path, firmware: Path) -> ct.CDLL:
    validate_upstream(firmware)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'shim.h').write_text(STUB)
    for name in ['mm_flow.h', 'mm_tof.h', 'log.h', 'param.h', 'platform_defaults.h',
                 'physicalConstants.h', 'autoconf.h']:
        (directory/name).write_text('#include "shim.h"\n')
    (directory/'sensfusion6.h').write_bytes((firmware/'src/modules/interface/sensfusion6.h').read_bytes())
    for name in ['mm_flow.c', 'mm_tof.c']:
        (directory/name).write_bytes((firmware/'src/modules/src/kalman_core'/name).read_bytes())
    source = (firmware/'src/modules/src/sensfusion6.c').read_text()
    # The official bit trick assumes 32-bit long and violates host alias rules.
    # Preserve its exact binary32 operation; do not replace by a different sqrt.
    replacements = {
        'long i = *(long*)&y;': 'uint32_t i; memcpy(&i, &y, sizeof(i));',
        'y = *(float*)&i;': 'memcpy(&y, &i, sizeof(y));',
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise ValueError('unexpected upstream inverse-square-root implementation')
        source = source.replace(old, new)
    (directory/'attitude.c').write_text(source+RESET)
    (directory/'scalar.c').write_text(SCALAR)
    libpath = directory/'libworldz.so'
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIC',
                    '-shared', '-I'+str(directory), str(HERE/'world_z.c'),
                    str(directory/'attitude.c'), str(directory/'mm_flow.c'),
                    str(directory/'mm_tof.c'), str(directory/'scalar.c'),
                    '-lm', '-o', str(libpath)], check=True)
    lib = ct.CDLL(str(libpath))
    f = ct.c_float
    p = ct.POINTER(f)
    lib.world_z_init.argtypes = [ct.POINTER(WorldZ)] + [f]*8
    lib.world_z_init.restype = ct.c_bool
    lib.world_z_predict.argtypes = [ct.POINTER(WorldZ), f, f]
    lib.world_z_predict.restype = ct.c_bool
    lib.world_z_baro.argtypes = [ct.POINTER(WorldZ), f, f]
    lib.world_z_baro.restype = ct.c_bool
    lib.world_z_slow_baro.argtypes = [ct.POINTER(WorldZ)]+[f]*4
    lib.world_z_slow_baro.restype = ct.c_bool
    lib.world_z_project.argtypes = [p, p, p]
    lib.world_z_project.restype = ct.c_bool
    lib.local_flow_velocity.argtypes = [f, f, f, p, p, f, f, f, f, ct.c_bool, p]
    lib.local_flow_velocity.restype = ct.c_bool
    lib.sensfusion6UpdateQ.argtypes = [f]*7
    lib.sensfusion6GetQuaternion.argtypes = [p]*4
    for name, count in [('lab_stock_tof', 2), ('lab_stock_flow_z', 4), ('lab_zero_hz_coupling', 0)]:
        getattr(lib, name).argtypes = [f]*count
        getattr(lib, name).restype = f
    return lib

def init(lib, *, z=0.0, v=0.0, bias=0.0, sz=0.005, sv=0.02,
         sb=0.00981, qa=0.0009, qb=0.000001) -> WorldZ:
    state = WorldZ()
    if not lib.world_z_init(ct.byref(state), z, v, bias, sz, sv, sb, qa, qb):
        raise ValueError('invalid observer initialization')
    return state

def project(lib, q, acc):
    result = ct.c_float()
    if not lib.world_z_project((ct.c_float*4)(*q), (ct.c_float*3)(*acc), ct.byref(result)):
        raise ValueError('invalid independent attitude/acceleration')
    return result.value

def attitude(lib, acc, gyro, dt):
    lib.sensfusion6UpdateQ(*gyro, *acc, dt)
    x, y, z, w = [ct.c_float() for _ in range(4)]
    lib.sensfusion6GetQuaternion(*[ct.byref(v) for v in (x,y,z,w)])
    return [w.value,x.value,y.value,z.value]

def flow(lib, dx, dy, dt, r, *, age=0, plane=True, r22=1, omega=(0,0,0), lever=(0,0,0)):
    result = (ct.c_float*2)()
    ok = lib.local_flow_velocity(dx,dy,dt,(ct.c_float*3)(*omega),
          (ct.c_float*3)(*lever),r,age,0.03,r22,plane,result)
    return list(result) if ok else None
