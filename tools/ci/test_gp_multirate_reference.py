"""Compile the actual composed analytic reference and G2 cache, not a flight."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tools.grand_prix.prepare_u_runtime import prepare
from tools.grand_prix.route_multirate_reference import REFERENCE


class ReferenceTests(unittest.TestCase):
    def test_32ms_knots_with_8ms_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root, legacy_worlds=False, route_observations=True)
            source = (root / 'runtime_u.c').read_text()
            begin = source.index('static double gp_move_ramp_position(')
            end = source.index('static double wrap_angle(', begin)
            profile = source[begin:end]
            self.assertIn(REFERENCE, profile)
            self.assertEqual(source.count('gp_reference_cached(&gp_ref,'), 2)
            self.assertIn('memset(&gp_ref, 0, sizeof(gp_ref));', source)
            constants = '\n'.join(re.findall(
                r'^#define (?:POSITION_KP|YAW_RATE_MAX) [^\n]+$', source, re.M))
            self.assertEqual(len(constants.splitlines()), 2)
            harness = '#include <math.h>\n#include <assert.h>\n#include <stdio.h>\n#include <string.h>\n' + constants + '\n' + profile + r'''
static double max_pos, max_speed;
static unsigned long long count, calls, knots;
static void run(double d,double v) {
  gp_reference_cache_t c={0}; double last=0., duration=0.;
  for (int tick=0; ;++tick) {
    double t=tick*.008, f,s,T, F,S,D;
    gp_motion_reference(d,v,t,&F,&S,&D);
    gp_reference_cached(&c,2,7,100.,100.+t,d,v,&f,&s,&T);
    assert(T==D && isfinite(f) && isfinite(s));
    assert(f>=0 && f<=1 && s>=0 && s<=v && f>=last-1e-12);
    assert(fabs(f-F)*d<.001 && fabs(s-S)<.001);
    max_pos=fmax(max_pos,fabs(f-F)*d); max_speed=fmax(max_speed,fabs(s-S));
    last=f; ++count; duration=T;
    if(t>=D+.008){assert(f==1. && s==0.);break;}
  }
  assert(c.knots < c.calls/2); calls+=c.calls; knots+=c.knots;
  double f,s,T; gp_reference_cached(&c,3,7,200.,200.,d,v,&f,&s,&T);
  assert(f==0 && s==0 && T==duration);
  gp_reference_cached(&c,3,8,201.,201.008,d,v,&f,&s,&T);
  assert(f>=0 && f<.001 && s>=0);
  memset(&c,0,sizeof(c)); gp_reference_cached(&c,3,8,202.,202.,d,v,&f,&s,&T);
  assert(f==0 && s==0 && c.knots==2 && c.calls==1);
}
int main(void) {
  for(int i=1;i<=200;i++)for(int j=10;j<=35;j++)run(i*.01,j*.01);
  printf("MOVE count=%llu knots=%llu calls=%llu pos_error=%.12g speed_error=%.12g\n",count,knots,calls,max_pos,max_speed);
  count=calls=knots=0;max_pos=max_speed=0;
  for(int i=1;i<=179;i++)run(i*3.141592653589793/180.,YAW_RATE_MAX);
  printf("TURN count=%llu knots=%llu calls=%llu angle_error=%.12g rate_error=%.12g\n",count,knots,calls,max_pos,max_speed);
}
'''
            (root / 'test.c').write_text(harness)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            str(root / 'test.c'), '-lm', '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True)


if __name__ == '__main__':
    unittest.main()
