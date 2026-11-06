"""Read actual cross-Robot range transport and contact points at one Webots tick.

Data-only integration boundary for #824/#825. This module neither writes the
flight/evaluator channels nor establishes RESET, collision clearance, mission
success or READY/ALIVE. The caller must first verify the entire native scene
and treat any failed read as a terminal rejection; fresh sensor packets alone
cannot authorize takeoff.
"""
from dataclasses import dataclass

from tools.grand_prix.evaluator_native_contacts_v2 import NativeContactSampler
from tools.grand_prix.route_courses_v2 import course_from_identifier
from tools.grand_prix.route_evaluator_wire_v2 import parse_flight_channel
from tools.grand_prix.route_flight_observation_v2 import parse_flight_observation


@dataclass(frozen=True)
class NativeRouteData:
    time_ms: int
    flight: object
    contacts: object


class NativeRouteDataReader:
    """Read only the real evaluator Robot's fields and real vehicle contacts.

    The two timestamps refer to the same native 8-ms step. The observation
    timestamp may be up to 32 ms old, since actual device sampling is 32 ms.
    This is *not* a RESET proof or an admission validator.
    """

    def __init__(self, supervisor, identifier):
        if (type(identifier) is not str or
                course_from_identifier(identifier).identifier != identifier or
                supervisor.getBasicTimeStep() != 8):
            raise RuntimeError("noncanonical native data reader course or timestep")
        self._supervisor = supervisor
        self._identifier = identifier
        self._evaluator_id = self._evaluator().getId()
        self._contacts = NativeContactSampler(supervisor, identifier)

    def _evaluator(self):
        own = self._supervisor.getSelf()
        expected = self._supervisor.getFromDef("GP_ROUTE_EVALUATOR")
        if (own is None or expected is None or
                own.getId() != expected.getId() or
                own.getDef() != "GP_ROUTE_EVALUATOR" or
                own.getTypeName() != "Robot" or
                own.getBaseTypeName() != "Robot" or
                own.isProto()):
            raise RuntimeError("native evaluator identity unavailable")
        controller = own.getField("controller")
        supervisor = own.getField("supervisor")
        args = own.getField("controllerArgs")
        if (controller is None or controller.getSFString() != "grand_prix_route_evaluator" or
                supervisor is None or supervisor.getSFBool() is not True or
                args is None or args.getCount() != 1 or
                args.getMFString(0) != self._identifier):
            raise RuntimeError("native evaluator controller/course changed")
        for key in ("model", "customData", "description"):
            if own.getField(key) is None:
                raise RuntimeError("missing native evaluator field " + key)
        return own

    def snapshot(self):
        if self._supervisor.getBasicTimeStep() != 8:
            raise RuntimeError("native data timestep changed")
        own = self._evaluator()
        if (own.getId() != self._evaluator_id or
                self._supervisor.getFromId(self._evaluator_id) is None or
                self._supervisor.getFromId(self._evaluator_id).getId() != self._evaluator_id):
            raise RuntimeError("native evaluator source changed")
        # Contact sampler independently revalidates the live flight Robot's
        # provenance, and refuses replay, forged data and missing observations.
        contacts = self._contacts.snapshot()
        event = parse_flight_channel(own.getField("customData").getSFString(),
                                     self._identifier)
        flight = parse_flight_observation(own.getField("model").getSFString(),
                                          event, contacts.time_ms)
        current = self._supervisor.getTime()
        if (type(current) not in (int, float) or
                round(current * 1000) != contacts.time_ms or
                abs(current * 1000 - contacts.time_ms) > 1e-4):
            raise RuntimeError("native observation tick changed during read")
        return NativeRouteData(contacts.time_ms, flight, contacts)
