"""Extract the exact candidate handler; execute one controlled POSIX contrast."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--patched-main', type=Path,
                    default=HERE/'old-patched-main.cpp')
args = parser.parse_args()
source = args.patched_main.read_text()
assert hashlib.sha256(source.encode()).hexdigest() == '0581be5f8638371654e870b2c74885e3be11a147fe1fb9e8d6169a4d301104c7'
start = source.index('static volatile sig_atomic_t gQuitNotificationFd = -1;')
end = source.index('#else\n// Preserve the original Windows', start)
handler = source[start:end]
(HERE/'handler.inc').write_text(handler)
compile_result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra',
                '-O2', '-pthread', str(HERE/'fd_retirement.cpp'),
                '-o', str(HERE/'fd_retirement')], check=True, capture_output=True, text=True)
(HERE/'compiler.log').write_text(compile_result.stdout+compile_result.stderr)
version = subprocess.check_output(['g++', '--version'], text=True)
(HERE/'compiler-version.txt').write_text(version)
results = []
with tempfile.TemporaryDirectory() as directory:
    for mode in ('keep', 'full', 'retire'):
        run = subprocess.run([str(HERE/'fd_retirement'), mode, str(Path(directory)/mode)],
                             capture_output=True, text=True, check=True, timeout=5)
        results.append(json.loads(run.stdout))
result = {'candidate': 'b8116937179da1a840d8ece9ac15bd3f3323c4fa',
          'patched_main_sha256': hashlib.sha256(source.encode()).hexdigest(),
          'exact_extracted_handler_sha256': hashlib.sha256(handler.encode()).hexdigest(),
          'results': results,
          'scope': 'real POSIX kernel FD lifetime counterexample; Qt/Webots not executed',
          'intervention': 'write wrapper gates scheduling between sampled FD and kernel write'}
(HERE/'RESULT.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
