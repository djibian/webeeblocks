import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from run import transform,join_native,ROOT,HERE

class PhysicsTests(unittest.TestCase):
    def test_no_extra_runtime_queries_or_physics_mutations(self):
        source=(ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c').read_text()
        changed=transform(source)
        for token in ('wb_motor_set_velocity(', 'wb_supervisor_node_reset_physics(',
                      'wb_supervisor_field_set_sf_vec3f(', 'wb_supervisor_field_set_sf_rotation(',
                      '#define RESET_WINDOW 0.25', '#define RESET_TIMEOUT 5.0'):
            self.assertEqual(changed.count(token),source.count(token))
        h=(HERE/'buffered.h').read_text()
        self.assertNotIn('wb_supervisor_node_get_',h)
        p=(ROOT/'plugins/physics/reset637_native/reset637_native.c').read_text()
        for bad in ('dBodySet','dBodyAdd','dJointCreate','dJointAttach','dWebotsSend'):
            self.assertNotIn(bad,p)
        self.assertEqual(p.count('return 0;'),3)

    def test_join_refuses_missing_duplicate_and_truncated_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);n={'time':.032,'candidate_overflow':0}
            def files(native):
                (d/'physics-state.jsonl').write_text('{}\n'+'\n'.join(json.dumps(x) for x in native)+'\n')
                (d/'consumed-state.jsonl').write_text('{}\n'+json.dumps({'time':.032,'custom_data':'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 7'})+'\n')
            files([n]);join_native(d)
            self.assertEqual(json.loads((d/'native-reset-state.jsonl').read_text().splitlines()[1])['custom_data'],'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 7')
            for data in ([],[n,n],[{**n,'time':0}],[{**n,'candidate_overflow':1}]):
                files(data)
                with self.assertRaises(ValueError):join_native(d)

    def test_plugin_c_records_ode_values_and_keeps_collision_default(self):
        header=r'''
typedef double dReal;
typedef void *dBodyID;typedef void *dGeomID;typedef void *dJointID;
typedef struct {double pos[4],normal[4],depth;} dContactGeom;
enum {dJointTypeContact=1};
static double t;
static double p[]={1,2,3},r[]={1,0,0,0,0,1,0,0,0,0,1,0},v[]={4,5,6},w[]={7,8,9};
static dBodyID dWebotsGetBodyFromDEF(const char *s){return (void*)1;}
static int dGeomIsSpace(dGeomID g){return 0;}
static dBodyID dGeomGetBody(dGeomID g){return (void*)1;}
static int dCollide(dGeomID a,dGeomID b,int n,dContactGeom *o,int stride){o[0]=(dContactGeom){{.1,.2,.3,0},{0,0,1,0},.01};return 1;}
static const dReal *dBodyGetPosition(dBodyID b){return p;}
static const dReal *dBodyGetRotation(dBodyID b){return r;}
static const dReal *dBodyGetLinearVel(dBodyID b){return v;}
static const dReal *dBodyGetAngularVel(dBodyID b){return w;}
static int dBodyGetNumJoints(dBodyID b){return 1;}
static dJointID dBodyGetJoint(dBodyID b,int i){return (void*)1;}
static int dJointGetType(dJointID j){return dJointTypeContact;}
static double dWebotsGetTime(void){return t;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'plugins').mkdir();(d/'plugins/physics.h').write_text(header)
            source=(ROOT/'plugins/physics/reset637_native/reset637_native.c').read_text()
            (d/'test.c').write_text(source+'\nint main(void){webots_physics_init();webots_physics_step();if(webots_physics_collide((void*)2,(void*)3)!=0)return 1;webots_physics_step_end();t=32;webots_physics_step();webots_physics_step_end();webots_physics_cleanup();return 0;}\n')
            subprocess.run(['gcc','-std=c11','-I',tmp,str(d/'test.c'),'-lm','-o',str(d/'test')],check=True,capture_output=True)
            subprocess.run([str(d/'test')],env={**os.environ,'WEBEEBLOCKS_CI_ARTIFACT_DIR':tmp},check=True)
            rows=[json.loads(x) for x in (d/'physics-state.jsonl').read_text().splitlines()]
            self.assertEqual([x['time'] for x in rows[1:]],[.032,.064])
            self.assertEqual(rows[1]['velocity'],[4,5,6,7,8,9])
            self.assertEqual(rows[1]['orientation'],[1,0,0,0,1,0,0,0,1])
            self.assertEqual(rows[1]['contacts'][0]['point'],[.1,.2,.3])
            self.assertIsNone(rows[1]['contacts'][0]['node_id'])

if __name__=='__main__':unittest.main()
