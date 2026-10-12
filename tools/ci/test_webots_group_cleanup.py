#!/usr/bin/env python3
"""Real process/socket counterexample: wrapper exit does not close its child."""
from pathlib import Path
import os
import shlex
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as directory:
    temp=Path(directory)
    (temp/'listener.py').write_text('''import json,os,signal,socket,sys,time
if sys.argv[2]=='ignore':signal.signal(signal.SIGTERM,signal.SIG_IGN)
s=socket.socket();s.bind(('127.0.0.1',0));s.listen()
open(sys.argv[1],'w').write(json.dumps({'port':s.getsockname()[1],'group':os.getpgrp()}))
while True:time.sleep(.02)
''')
    (temp/'wrapper.py').write_text('''import subprocess,sys
subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2],sys.argv[3]]).wait()
''')
    (temp/'check.py').write_text('''import json,socket,sys,time
port=json.load(open(sys.argv[1]))['port'];expected=sys.argv[2]=='alive'
for _ in range(100):
 s=socket.socket();s.settimeout(.05)
 alive=s.connect_ex(('127.0.0.1',port))==0;s.close()
 if alive==expected:break
 time.sleep(.02)
else:raise AssertionError((port,expected,alive))
''')
    script=f'''
set -euo pipefail
source {shlex.quote(str(ROOT/'tools/ci/stop_webots_group.sh'))}
cd {shlex.quote(str(temp))}
start_group() {{
 rm -f ready.json
 setsid {shlex.quote(sys.executable)} wrapper.py listener.py ready.json "$1" &
 group_pid=$!
 for i in $(seq 1 100); do test ! -s ready.json || break; sleep .02; done
 test -s ready.json
}}
trap 'test -z "${{group_pid:-}}" || stop_webots_group "$group_pid"' EXIT
start_group normal
kill -TERM "$group_pid"
wait "$group_pid" 2>/dev/null || true
{shlex.quote(sys.executable)} check.py ready.json alive
stop_webots_group "$group_pid"
{shlex.quote(sys.executable)} check.py ready.json dead
start_group normal
if stop_webots_group 0 || stop_webots_group invalid; then exit 1; fi
{shlex.quote(sys.executable)} check.py ready.json alive
stop_webots_group "$group_pid"
{shlex.quote(sys.executable)} check.py ready.json dead
start_group ignore
stop_webots_group "$group_pid"
{shlex.quote(sys.executable)} check.py ready.json dead
'''
    subprocess.run(['bash','-c',script],check=True,timeout=15)
print('PASS owned Webots group cleanup: wrapper-only survivor reproduced; session group retired, TERM-resistant child removed, invalid identifiers refuse')
