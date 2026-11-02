"""CI-only Supervisor: retirement authority is held by the verifying native host.

This controller is appended only to temporary progression worlds, never the
student world or the product controller. It never infers success from WWI.
"""
import os
from pathlib import Path
import re
from controller import Supervisor

root = Path(os.environ['WEBEEBLOCKS_CI_ARTIFACT_DIR'])
supervisor = Supervisor()
step = int(supervisor.getBasicTimeStep())
while supervisor.step(step) != -1:
    path = root / 'normal-quit.request'
    if not path.is_file():
        continue
    request = path.read_text(encoding='ascii')
    if not re.fullmatch(r'(memory|autonomous) [0-9a-f]{32}\n', request):
        raise RuntimeError('invalid CI normal-quit request identity')
    (root / 'normal-quit.ack').write_text(request, encoding='ascii')
    print('PROGRESSION_NORMAL_QUIT accepted=' + request.split()[0], flush=True)
    supervisor.simulationQuit(0)
    break
