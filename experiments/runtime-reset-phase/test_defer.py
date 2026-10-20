import subprocess,tempfile,unittest
from pathlib import Path
from defer import receiver,defer
from campaign import validate_delay
ROOT=Path(__file__).resolve().parents[2]
class DelayTests(unittest.TestCase):
 def test_native_receiver_holds_only_seventh_and_delivers_exactly_once(self):
  prefix=r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PREFIX "WEBEEBLOCKS_RUNTIME_V2"
static double fake_time;
static int index_;
static const char *queue[]={"hello","WEBEEBLOCKS_RUNTIME_V2 REQUEST 0 RESET",
"WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 RESET","WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 RESET",
"WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 RESET","WEBEEBLOCKS_RUNTIME_V2 REQUEST 4 RESET",
"WEBEEBLOCKS_RUNTIME_V2 REQUEST 5 RESET","WEBEEBLOCKS_RUNTIME_V2 REQUEST 6 RESET",
"WEBEEBLOCKS_RUNTIME_V2 REQUEST 99 RANGE front","WEBEEBLOCKS_RUNTIME_V2 REQUEST 7 RESET",
"WEBEEBLOCKS_RUNTIME_V2 REQUEST 8 RESET",NULL};
static double wb_robot_get_time(void){return fake_time;}
static double wb_robot_get_basic_time_step(void){return 32.;}
static const char *wb_robot_wwi_receive_text(void){return queue[index_++];}
'''
  suffix=r'''int main(void){
 for(int i=0;i<9;i++) assert(strcmp(reset_phase_receive(),queue[i])==0);
 assert(reset_phase_receive()==NULL); assert(index_==10);
 for(int n=0;n<STEPS;n++){fake_time=n*.032;assert(reset_phase_receive()==NULL);assert(index_==10);}
 fake_time=STEPS*.032;
 assert(strcmp(reset_phase_receive(),queue[9])==0);assert(index_==10);
 assert(strcmp(reset_phase_receive(),queue[10])==0);assert(index_==11);
 assert(reset_phase_receive()==NULL);return 0;}
'''
  for steps in (1,8,16):
   with self.subTest(steps=steps),tempfile.TemporaryDirectory() as tmp:
    c=Path(tmp)/'test.c';exe=Path(tmp)/'test';c.write_text(prefix+receiver(steps)+suffix.replace('STEPS',str(steps)))
    subprocess.run(['cc','-std=c11','-Wall','-Werror',str(c),'-o',str(exe)],check=True,capture_output=True)
    subprocess.run([str(exe)],check=True,capture_output=True)
 def test_unrecognized_source_and_wrong_timing_fail_closed(self):
  source=(ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c').read_text()
  for n in (0,2,32):
   with self.assertRaises(ValueError):defer(source,n)
  with self.assertRaises(ValueError):defer('',1)
  text='\n'.join([f' RESET_PHASE_BEGIN id={i} time=0' for i in range(1,7)])+'\n RESET_DEFER_BEGIN id=7 time=1.000000000 steps=8\n RESET_DEFER_RELEASE id=7 time=1.256000000\n RESET_PHASE_BEGIN id=7 time=1.256000000\n'
  self.assertEqual(validate_delay(text,8)['steps'],8)
  for changed in (text.replace('time=1.256','time=1.255'),text.replace('RELEASE id=7','RELEASE id=8'),text+text,text.replace('RESET_PHASE_BEGIN id=7','RESET_PHASE_BEGIN id=8')):
   with self.assertRaises(ValueError):validate_delay(changed,8)
if __name__=='__main__':unittest.main()
