"""R2025a native route evaluator; Linux delivery/flight qualification separate."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from controller import Supervisor
from tools.grand_prix.evaluator_publisher_v2 import serve_native


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise RuntimeError('evaluator requires one canonical host course identifier')
    serve_native(Supervisor(), args[0])


if __name__ == '__main__':
    main()
