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
        self._failed = False

    def snapshot(self):
        # The published data boundary is fail-stop, not merely fail-closed on
        # one call. A later valid tick cannot erase a previous bad read or
        # mismatched native streams. A new sampler requires new validation;
        # it does NOT itself attest RESET or authorize READY.
        if self._failed:
            raise RuntimeError("native observation sampler terminal after failure")
        try:
            pose = self._kinematics.snapshot()
            data = self._data.snapshot()
            if pose.time_ms != data.time_ms or data.contacts.time_ms != data.time_ms:
                raise RuntimeError("native pose/range/contact tick mismatch")
            return NativeCourseObservation(data.time_ms, pose, data.flight, data.contacts)
        except Exception:
            self._failed = True
            raise
