"""Generate byte-identical real route C/broker for the quarantined WWI probe."""
from pathlib import Path
from shutil import copyfile
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.prepare_u_runtime import prepare
# The route-only generated C includes ../gp_route_takeoff_profile.h.
# Copy the original product header byte-for-byte beside this test controller.
copyfile(ROOT / 'controllers/grand_prix_route_flight/gp_route_takeoff_profile.h',
         ROOT / 'controllers/grand_prix_route_publisher_probe/gp_route_takeoff_profile.h')
prepare(ROOT / 'controllers/grand_prix_route_publisher_probe/build',
        legacy_worlds=False, route_observations=True)
