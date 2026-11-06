"""Read one coherent native pose/range/contact tick; no mission authority.

A route evaluator can only consume these observations after a real scene check.
This data boundary publishes no READY/ALIVE, RESET verdict, safe-to-fly flag,
collision clearance, score or mission result. The native sensor/physics
qualifications remain separate; host test doubles never prove R2025a behavior.
"""
from dataclasses import dataclass

from tools.grand_prix.evaluator_scene_identity_v2 import check_native_evaluator_scene
from tools.grand_prix.evaluator_native_kinematics_v2 import NativeKinematicsSampler
from tools.grand_prix.evaluator_live_data_v2 import NativeRouteDataReader


@dataclass(frozen=True)
class NativeCourseObservation:
    time_ms: int
    kinematics: object
    flight: object
    contacts: object


class NativeCourseObservationSampler:
    """Compose read-only streams at the identical 8-ms Webots tick.

    The full scene/collider check precedes data-reader construction, but its
    success does not establish subsequent RESET freshness or READY/ALIVE.
    Any failed or inconsistent snapshot is terminal for the caller, not a
    request to reuse the preceding observation.
    """

    def __init__(self, supervisor, identifier):
        check_native_evaluator_scene(supervisor, identifier)
        self._kinematics = NativeKinematicsSampler(supervisor, identifier)
        self._data = NativeRouteDataReader(supervisor, identifier)

    def snapshot(self):
        pose = self._kinematics.snapshot()
        data = self._data.snapshot()
        if pose.time_ms != data.time_ms or data.contacts.time_ms != data.time_ms:
            raise RuntimeError("native pose/range/contact tick mismatch")
        return NativeCourseObservation(data.time_ms, pose, data.flight, data.contacts)
