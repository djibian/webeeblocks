"""Generate byte-identical real route C/broker for the quarantined WWI probe."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.prepare_u_runtime import prepare
prepare(ROOT / 'controllers/grand_prix_route_publisher_probe/build',
        legacy_worlds=False, route_observations=True)
