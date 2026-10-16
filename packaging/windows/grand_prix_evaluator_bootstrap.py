"""Entry point for the isolated, packaged Windows Grand Prix evaluator.

CPython's embedded ._pth deliberately ignores the user's Python installation,
PYTHONPATH and site-packages. Admit only our project and Webots' own C API.
The observable-world evaluator and its oracles are copied without modification.
"""
import json
import os
from pathlib import Path
import runpy
import sys


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[1]
    webots = Path(os.environ['WEBOTS_HOME']).resolve(strict=True)
    api = webots / 'lib/controller/python'
    if not (api / 'controller/__init__.py').is_file():
        raise RuntimeError('Webots R2025a Python controller API missing')
    sys.path[:0] = [str(root), str(api)]
    # Resolve the complete closure before creating any Supervisor/connection.
    from controller import Supervisor
    from tools.grand_prix.layout_u import generate
    from tools.grand_prix.oracle_u import Attempt, ORACLE
    from tools.grand_prix.simulation_time import milliseconds
    if sys.argv[1:] == ['--verify-imports']:
        import tools.grand_prix.layout_u as layout
        import tools.grand_prix.oracle_u as oracle
        import controller
        print(json.dumps({
            'python': sys.version.split()[0], 'executable': sys.executable,
            'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
            'layout': layout.__file__, 'oracle_module': oracle.__file__,
            'controller': controller.__file__, 'oracle': ORACLE,
            'gates': len(generate(4).gates), 'milliseconds': milliseconds(210.0),
        }), flush=True)
        return
    runpy.run_path(str(directory / 'evaluator_impl.py'), run_name='__main__')


if __name__ == '__main__':
    main()
