"""Fail-closed composition of native route observations on one Webots 8-ms tick.

This is read-only evidence for the future variable Grand Prix evaluator, not
READY, ALIVE, RESET, collision clearance, mission admission or flight authority.
A publisher must still independently attest fresh RESET, scene invariants,
route-oracle progress and the irreversible 210000-ms LAND boundary.
"""
from dataclasses import dataclass

from tools.grand_prix.evaluator_live_data_v2 import (
    NativeRouteData, NativeRouteDataReader,
)
from tools.grand_prix.evaluator_native_contacts_v2 import NativeContactObservation
from tools.grand_prix.evaluator_native_kinematics_v2 import (
    NativeKinematics, NativeKinematicsSampler,
)
from tools.grand_prix.evaluator_scene_identity_v2 import check_native_evaluator_scene
from tools.grand_prix.route_flight_observation_v2 import FlightObservation


@dataclass(frozen=True)
class NativeRouteObservation:
    time_ms: int
    kinematics: NativeKinematics
    flight: FlightObservation
    contacts: NativeContactObservation


class NativeRouteObservationSampler:
    """Observe one checked scene, native pose and flight-owned ranges/contacts.

    The caller steps Webots before snapshot(). The 8-ms pose/contact timestamps
    must match, while the native flight-owned range message may be up to 32 ms
    old (sensor acquisition can be another 32 ms older). A failed read poisons
    the instance: it cannot silently resume with an older or mixed observation.
    No field is written and no authority is inferred from an empty contact list.
    """

    def __init__(self, supervisor, identifier):
        # Verify the actual collider inventory before trusting any data source.
        # This is a necessary precondition, NEVER a READY authorization.
        check_native_evaluator_scene(supervisor, identifier)
        self._kinematics = NativeKinematicsSampler(supervisor, identifier)
        self._data = NativeRouteDataReader(supervisor, identifier)
        self._last_ms = None
        self._poisoned = False

    def snapshot(self):
        if self._poisoned:
            raise RuntimeError("native route observation poisoned; fresh preflight required")
        try:
            kinematics = self._kinematics.snapshot()
            data = self._data.snapshot()
            if (type(kinematics) is not NativeKinematics or
                    type(data) is not NativeRouteData or
                    type(data.flight) is not FlightObservation or
                    type(data.contacts) is not NativeContactObservation or
                    type(kinematics.time_ms) is not int or
                    type(data.time_ms) is not int or
                    type(data.contacts.time_ms) is not int or
                    data.time_ms != kinematics.time_ms or
                    data.contacts.time_ms != data.time_ms or
                    (self._last_ms is not None and
                     data.time_ms <= self._last_ms)):
                raise RuntimeError("native route pose/ranges/contacts tick mismatch")
            self._last_ms = data.time_ms
            return NativeRouteObservation(
                data.time_ms, kinematics, data.flight, data.contacts)
        except Exception:
            # Recover only by constructing a new sampler after independent
            # scene verification; never reuse possibly mixed native evidence.
            self._poisoned = True
            raise
