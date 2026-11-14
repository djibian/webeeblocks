"""Build the isolated route pilot from shared native Runtime; never launch it.

Windows must get its process-fresh epoch from CNG, not from a MinGW entropy
estimate. Other platforms keep their original controller source/entropy path.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.prepare_u_runtime import prepare
from tools.grand_prix.route_windows_epoch import write_windows_route_deadline


if __name__ == '__main__':
    destination = ROOT / 'controllers/grand_prix_route_flight/build'
    prepare(destination, legacy_worlds=False, route_observations=True)
    if os.name == 'nt':
        write_windows_route_deadline(destination / 'grand_prix_route_deadline.cpp')
