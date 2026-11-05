"""Build the shared native Runtime for the variable route, never launch it."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.prepare_u_runtime import prepare


if __name__ == '__main__':
    prepare(ROOT / 'controllers/grand_prix_route_flight/build',
            legacy_worlds=False, route_observations=True)
