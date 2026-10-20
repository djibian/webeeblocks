import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from run import transform,combine,ROOT,HERE

class BufferedTests(unittest.TestCase):
    def test_transform_keeps_mutations_predicates_and_no_per_step_output(self):
        source=(ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c').read_text()
        changed=transform(source)
        for token in ('wb_motor_set_velocity(', 'wb_supervisor_node_reset_physics(',
                      'wb_supervisor_field_set_sf_vec3f(', 'wb_supervisor_field_set_sf_rotation(',
                      '#define RESET_WINDOW 0.25', '#define RESET_TIMEOUT 5.0'):
            self.assertEqual(changed.count(token),source.count(token))
        predicates=source[source.index('      const int pose_ready'):source.index('      if (!pose_ready)')]
        self.assertIn(predicates,changed)
        self.assertEqual(changed.count('diag_dump();'),2)
        self.assertNotIn('fprintf(stderr, PREFIX " RESET_PHASE_',changed)
        with self.assertRaises(ValueError):transform('invalid')

    def test_response_join_requires_exact_actual_response(self):
        p='WEBEEBLOCKS_RUNTIME_V2 RESET_PHASE_BEGIN id=4 time=0\nSAMPLE\n'
        actual='WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 OK\n'
        self.assertTrue(combine(p,actual).endswith(actual))
        for bad in ('','WEBEEBLOCKS_RUNTIME_V2 RESPONSE 5 OK\n',actual+actual):
            with self.assertRaises(ValueError):combine(p,bad)

    def test_native_buffer_has_no_file_before_decision_and_preserves_two_dumps(self):
        stub=r'''
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <math.h>
#include <stdbool.h>
typedef int WbNodeRef;
typedef int WbDeviceTag;
typedef struct {double point[3]; int node_id;} WbContactPoint;
static const double pos[]={1.,2.,3.},ori[]={1,0,0,0,1,0,0,0,1},vel[]={4,5,6,7,8,9};
static WbContactPoint cp[]={{{.1,.2,.3},42}};
static const char *wb_robot_get_custom_data(void){return "attempt \"7\"\\test";}
static const double *wb_supervisor_node_get_position(int n){return pos;}
static const double *wb_supervisor_node_get_orientation(int n){return ori;}
static const double *wb_supervisor_node_get_velocity(int n){return vel;}
static WbContactPoint *wb_supervisor_node_get_contact_points(int n,bool b,int *c){*c=1;return cp;}
static double wb_motor_get_velocity(int n){return n;}
'''
        suffix=r'''
int main(void){
 diag_open();diag_sample(1,1,pos,pos,pos,1,2,3,4);
 char path[2048];snprintf(path,sizeof(path),"%s/native-reset-state.jsonl",getenv("WEBEEBLOCKS_CI_ARTIFACT_DIR"));
 FILE *f=fopen(path,"r");if(f)return 2;
 fprintf(diag_phase,"first\n");diag_dump();
 diag_sample(1,2,pos,pos,pos,5,6,7,8);fprintf(diag_phase,"second\n");diag_dump();return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);c=p/'test.c';exe=p/'test'
            c.write_text(stub+'\n'+(HERE/'buffered.h').read_text()+'\n'+suffix)
            subprocess.run(['gcc','-std=c11','-Wall',str(c),'-lm','-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],env={**os.environ,'WEBEEBLOCKS_CI_ARTIFACT_DIR':tmp},check=True)
            rows=[json.loads(x) for x in (p/'native-reset-state.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),3)
            self.assertEqual([r['time'] for r in rows[1:]],[1,2])
            self.assertEqual(rows[1]['contacts'],[{'point':[.1,.2,.3],'node_id':42}])
            self.assertEqual(rows[1]['custom_data'],'attempt "7"\\test')
            self.assertEqual(rows[2]['motor_targets'],[5,6,7,8])
            self.assertEqual((p/'buffered-phase.log').read_text(),'first\nsecond\n')

if __name__=='__main__':unittest.main()
