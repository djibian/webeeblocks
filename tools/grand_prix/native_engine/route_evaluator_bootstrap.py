"""Run the unchanged route evaluator using only the packaged interpreter."""
import os
from pathlib import Path
import runpy
import sys

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[1]
if Path(sys.executable).resolve() != (ROOT / 'runtime/python/webeeblocks-gp-python.exe').resolve():
    raise RuntimeError('Unexpected route evaluator interpreter')
home = Path(os.environ['WEBOTS_HOME']).resolve(strict=True)
sys.path[:0] = [str(ROOT), str(home / 'lib/controller/python')]
with os.add_dll_directory(str(home / 'msys64/mingw64/bin')):
    if sys.argv[1:] == ['--verify-imports']:
        runpy.run_path(str(DIRECTORY / 'evaluator_impl.py'))
        print('PASS embedded Python, Webots C API and route evaluator imports', flush=True)
    else:
        runpy.run_path(str(DIRECTORY / 'evaluator_impl.py'), run_name='__main__')
