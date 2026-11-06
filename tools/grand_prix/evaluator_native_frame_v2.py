"""One time-locked native pose/range/contact frame, without mission authority.

The caller must already attest the full R2025a scene and fresh RESET. This
read-only composition neither establishes either precondition nor grants a
READY/ALIVE, collision-clear, result or flight permission. Device periods are
not individual acquisition timestamps: report only a conservative age bound.
"""
from dataclasses import dataclass

from tools.grand_prix.evaluator_live_data_v2 import NativeRouteDataReader
from tools.grand_prix.evaluator_native_kinematics_v2 import NativeKinematicsSampler


@dataclass(frozen=True)
class NativeRouteFrame:
    time_ms: int
    kinematics: object
    data: object
    range_age_upper_ms: int


class NativeRouteFrameReader:
    """Join the two independently sourced snapshots at exactly one 8-ms tick.

    If either read fails or a native step occurs between reads, never return a
    partially valid frame. The underlying samplers reject replay, source drift,
    stale range packets and malformed contact points independently.
    """

    def __init__(self, supervisor, course_identifier):
        self._kinematics = NativeKinematicsSampler(supervisor, course_identifier)
        self._data = NativeRouteDataReader(supervisor, course_identifier)

    def snapshot(self):
        kinematics = self._kinematics.snapshot()
        data = self._data.snapshot()
        if (kinematics.time_ms != data.time_ms or
                data.contacts.time_ms != data.time_ms):
            raise RuntimeError("native route pose and devices are not from the same tick")
        age = data.time_ms - data.flight.time_ms
        period = data.flight.sensor_period_ms
        if (type(age) is not int or type(period) is not int or
                not 0 <= age <= 32 or period != 32):
            raise RuntimeError("invalid native range acquisition bound")
        # Last publication may itself follow acquisition by one device period.
        # Never claim the sample was acquired at its publication timestamp.
        return NativeRouteFrame(data.time_ms, kinematics, data, age + period)
