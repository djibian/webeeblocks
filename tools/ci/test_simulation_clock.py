#!/usr/bin/env python3
"""Compile and falsify the actual clock used by the native Webots controller."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as directory:
    source=Path(directory)/'probe.c';binary=Path(directory)/'probe'
    source.write_text(r'''
#include "simulation_clock.h"
#include <assert.h>
int main(void) {
  simulation_clock_t c={0,0,0}; double value=-1;
  assert(!simulation_clock_read(&c,1,&value));
  simulation_clock_begin(&c,40);
  assert(simulation_clock_read(&c,40,&value) && value==0);
  assert(simulation_clock_read(&c,160,&value) && value==120);
  assert(simulation_clock_read(&c,160.125,&value) && value==120.125);
  assert(!simulation_clock_read(&c,160,&value));
  assert(!simulation_clock_read(&c,170,&value));
  simulation_clock_begin(&c,300);
  assert(simulation_clock_read(&c,300.25,&value) && value==.25);
  simulation_clock_revoke(&c);
  assert(!simulation_clock_read(&c,301,&value));
  simulation_clock_begin(&c,NAN);assert(!simulation_clock_read(&c,1,&value));
  simulation_clock_begin(&c,-1);assert(!simulation_clock_read(&c,1,&value));
  simulation_clock_begin(&c,0);assert(!simulation_clock_read(&c,INFINITY,&value));
  return 0;
}
''')
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'controllers/crazyflie_runtime_v2'),str(source),'-lm','-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
print('PASS native simulation clock: admission, exact 120s, fractions, restart, terminal revocation, nonfinite and backward time')
