"""First native variable Grand Prix evaluator process: preflight, not admission.

The R2025a Supervisor validates the current physical scene and host identity,
then deliberately publishes no READY, ALIVE, RESULT or flight permission. This
is a quarantined, fail-closed bootstrap pending qualified real device, contact,
RESET and route-oracle evidence. Never mistake the process's liveness for
evaluator authorization or a usable pupil Linux simulation.
"""
from tools.grand_prix.evaluator_scene_identity_v2 import check_native_evaluator_scene


def serve_fail_closed(robot, identifier):
    """Attest only startup scene identity; keep the authority field empty.

    Return only after the native simulation stops. A rejected/missing scene
    never gains readiness, even if the field retained a stale earlier value.
    """
    node = robot.getSelf()
    field = node.getField('description') if node is not None else None
    if field is None:
        raise RuntimeError('native route evaluator description field absent')
    field.setSFString('')  # revoke stale evidence *before* all checks
    check_native_evaluator_scene(robot, identifier)  # may raise; remains empty
    # This is not a publisher: writing only empty strings cannot grant READY.
    # Revalidation and evidence-driven publication belong to a later stage.
    while robot.step(8) != -1:
        field.setSFString('')
