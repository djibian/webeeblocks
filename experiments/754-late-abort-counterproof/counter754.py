"""Consumer-level late-abort contrast; no Webots or hardware qualification."""
import json
import os
from pathlib import Path
import resource
import select
import signal
import subprocess
import sys
import tempfile
from unittest.mock import Mock

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from tools.ci.run_grand_prix_u_prototype import retire_trial
from tools.ci.grand_prix_u_log_capture import NativeLogCapture

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
for mode in ('clean', 'abort'):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        out = root/'capture'
        out.mkdir()
        target = root/'trial.wbt'
        target.write_text('bounded synthetic trial')
        read_fd, write_fd = os.pipe()
        code = '''import os,signal,sys
def stop(signum, frame):
    if sys.argv[2] == 'abort':
        print('malloc(): corrupted top size', flush=True)
        os.abort()
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
print('GP_U_RESULT valid-negative', flush=True)
os.write(int(sys.argv[1]), b'R')
while True: signal.pause()
'''
        child = None
        try:
            with NativeLogCapture(out/'webots.log') as capture:
                child = subprocess.Popen([sys.executable, '-c', code, str(write_fd), mode],
                    stdout=capture, stderr=subprocess.STDOUT, pass_fds=(write_fd,),
                    start_new_session=True)
                os.close(write_fd)
                write_fd = None
                assert select.select([read_fd], [], [], 3)[0], 'handler readiness missing'
                assert os.read(read_fd, 1) == b'R'
            runtime = Mock()
            startup = Mock()
            error = None
            try:
                retire_trial([child], capture, startup, [], runtime, out, target)
            except RuntimeError as exc:
                error = str(exc)
            record = {'mode': mode, 'returncode': child.returncode,
                'sealed': (out/'sha256.json').exists(), 'error': error,
                'world_removed': not target.exists(),
                'runtime_cleanup': runtime.cleanup.call_count,
                'startup_cleanup': startup.after_cleanup.call_count,
                'log': (out/'webots.log').read_text()}
            if (out/'teardown-failures.json').exists():
                record['stages'] = [f['stage'] for f in json.loads(
                    (out/'teardown-failures.json').read_text())]
            print(json.dumps(record, sort_keys=True), flush=True)
            assert child.returncode == (0 if mode == 'clean' else -signal.SIGABRT)
            assert record['runtime_cleanup'] == record['startup_cleanup'] == 1
            assert record['world_removed']
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
            if child is not None and child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=3)
