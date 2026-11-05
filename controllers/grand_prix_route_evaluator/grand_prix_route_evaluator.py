"""R2025a Grand Prix route scene preflight; no READY/ALIVE/mission oracle.

Webots calls this controller for GP_ROUTE_EVALUATOR. Until native in-attempt
sensor/contact/RESET/mission evidence is qualified, admission is forbidden.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from controller import Supervisor
from tools.grand_prix.evaluator_preflight_v2 import serve_fail_closed


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise RuntimeError('evaluator requires one canonical host course identifier')
    serve_fail_closed(Supervisor(), args[0])


if __name__ == '__main__':
    main()
