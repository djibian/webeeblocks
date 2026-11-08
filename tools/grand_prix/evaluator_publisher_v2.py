"""Native variable-course evaluator, never a pupil-program implementation.

All authority originates in this Supervisor's verified live scene and coherent
native observations. No caller supplies observations or a validation boolean.
The Linux launcher remains gated on the separate native/GUI qualifications.
"""
import logging
import math

from tools.grand_prix.evaluator_observation_v2 import NativeCourseObservation
from tools.grand_prix.evaluator_scene_identity_v2 import read_native_evaluator_scene
from tools.grand_prix.evaluator_native_contacts_v2 import read_contacts
from tools.grand_prix.evaluator_native_kinematics_v2 import _now_ms, read_kinematics
from tools.grand_prix.native_field_lookup_v2 import NativeFieldLookup
from tools.grand_prix.native_scene_snapshot_v2 import NativeSceneSnapshot
from tools.grand_prix.oracle_attempt_v2 import (
    start_pure_attempt, observe_pure_attempt, fail_pure_attempt,
)
from tools.grand_prix.oracle_u import DEADLINE_MS
from tools.grand_prix.route_courses_v2 import course_from_identifier
from tools.grand_prix.route_evaluator_wire_v2 import Challenge, EvaluatorHandshake, parse_flight_channel
from tools.grand_prix.route_flight_observation_v2 import parse_flight_observation

ORACLE = 'grand-prix-route-v2'
LOGGER = logging.getLogger(__name__)


class NativeRouteEvaluator:
    """One native process; failure is irreversible until a newer RESET attempt.

    READY requires 500 continuous ms of independently observed canonical ground
    pose, motion, contacts and the flight controller's own stable-ground bit.
    A lost tick or invalid read revokes this attempt, rather than repairing the
    observation in place. A later attempt must establish fresh ground evidence.
    """

    def __init__(self, robot, identifier):
        self._robot = robot
        self.course = course_from_identifier(identifier)
        own = robot.getSelf()
        self._reply = own.getField('description') if own is not None else None
        if self._reply is None:
            raise RuntimeError('native evaluator description absent')
        self._reply.setSFString('')
        self._scene_fields = NativeFieldLookup()
        self._scene_snapshot = NativeSceneSnapshot(self.course)
        self._vehicle = read_native_evaluator_scene(
            robot, self.course, self._scene_fields, self._scene_snapshot)
        self._self_id = own.getId()
        self._vehicle_id = self._vehicle.getId()
        if type(self._vehicle_id) is not int or self._vehicle_id <= 0:
            raise RuntimeError('invalid native vehicle ID')
        self._channel = self._vehicle.getField('customData')
        self._request = own.getField('customData')
        self._model = own.getField('model')
        if any(field is None for field in (self._channel, self._request, self._model)):
            raise RuntimeError('native evaluator channel absent')
        # Ground coordinates must not be recalibrated from a restarted
        # evaluator's possibly airborne/terminal pose. The verified floor is
        # the z=0 Plane and the pinned robot's centered Cylinder is 30 mm high.
        # Read its actual base fields (read-only), as in the native contact
        # witness, and refuse a changed model instead of moving the oracle.
        bounds_field = self._vehicle.getBaseNodeField('boundingObject')
        physics_field = self._vehicle.getBaseNodeField('physics')
        bounds = bounds_field.getSFNode() if bounds_field is not None else None
        physics = physics_field.getSFNode() if physics_field is not None else None
        if (bounds is None or bounds.getTypeName() != 'Cylinder' or
                physics is None or physics.getTypeName() != 'Physics'):
            raise RuntimeError('native pinned vehicle physics unavailable')
        for key, expected in (('height', .03), ('radius', .05)):
            field = bounds.getField(key)
            value = field.getSFFloat() if field is not None else None
            if type(value) not in (int, float) or not math.isfinite(value) or abs(value - expected) > 1e-9:
                raise RuntimeError('native pinned vehicle bounds changed')
        self._origin_z = bounds.getField('height').getSFFloat() / 2
        self._last_ms = None
        self._clock_failed = False
        self._closed_attempt = 0
        self._context = None
        self._wire = EvaluatorHandshake(identifier)
        self._ground_since = None
        self._challenge_since = None
        self._ready = False
        self._active = None
        self._start_ms = None
        self._positive_written = False
        self.observation = None
        self.phase = 'waiting'
        self.last_error = None

    def _close(self, now, reason, *, error=None):
        self._reply.setSFString('')  # revoke before any outcome or diagnostic
        if self._context is not None:
            if self._context.attempt <= self._closed_attempt:
                return
            self._closed_attempt = self._context.attempt
        self.last_error = reason if error is None else type(error).__name__ + ': ' + str(error)
        self.phase = 'authority-revoked' if self._positive_written else 'failed'
        self._ready = False
        self._ground_since = None
        if self._active is not None and not self._positive_written:
            self._active = fail_pure_attempt(self._active,
                max(now, self._active.last_ms), reason)
            attempt = self._context.attempt
            # The broker may have acknowledged RESET before the next
            # challenge is visible. Never replace its newer attempt marker
            # with a failure from this evaluator's previous attempt.
            if self._active.attempt == attempt and self._channel.getSFString() in (
                    f'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 {attempt}',
                    f'WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt={attempt} oracle={ORACLE}',
                    f'WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1 attempt={attempt} oracle={ORACLE}',
                    self._outcome('achieved')):
                self._channel.setSFString(self._outcome('not-achieved'))
        if self._context is not None:
            LOGGER.warning('GP_ROUTE_EVALUATOR_CLOSED attempt=%d time_ms=%d reason=%s detail=%r',
                           self._context.attempt, now, reason, self.last_error)
        # A positive result is written only once. After publication, invalid
        # observations still revoke ALIVE, but may not overwrite a success that
        # the pilot already latched. The pilot independently fails if it had
        # not consumed valid success+landed before loss of ALIVE/the deadline.

    def _outcome(self, status):
        return (f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt={self._context.attempt} '
                f'oracle={ORACLE} status={status}')

    def _ground(self, observation):
        p = observation.kinematics.position
        v = observation.kinematics.velocity
        m = observation.kinematics.orientation
        roll = math.atan2(m[7], m[8])
        pitch = math.asin(max(-1., min(1., -m[6])))
        yaw = math.atan2(m[3], m[0])
        return (observation.flight.ground_confirmed and
            math.dist(p[:2], self.course.route.legs[0].start) < .03 and
            0 <= p[2] and abs(p[2] - self._origin_z) < .05 and
            math.hypot(*v[:2]) < .12 and abs(v[2]) < .15 and
            max(abs(w) for w in v[3:]) < .10 and
            max(abs(roll), abs(pitch), abs(yaw)) < math.radians(2) and
            all(point.point[2] <= .012 for point in observation.contacts.points))

    def _landed(self, observation):
        p, v = observation.kinematics.position, observation.kinematics.velocity
        m = observation.kinematics.orientation
        target = self.course.route.landing_target(self.course.count)
        return (observation.flight.ground_confirmed and
            abs(p[0] - target[0]) <= .14 and abs(p[1] - target[1]) <= .14 and
            self._origin_z - .02 <= p[2] <= self._origin_z + .07 and
            math.hypot(*v[:2]) <= .12 and abs(v[2]) <= .12 and
            max(abs(w) for w in v[3:]) < .10 and
            abs(math.atan2(m[7], m[8])) < math.radians(2) and
            abs(math.asin(max(-1., min(1., -m[6])))) < math.radians(2) and
            all(point.point[2] <= .012 for point in observation.contacts.points))

    def tick(self):
        """Observe only live native APIs, after one real 8-ms Supervisor step."""
        if self._clock_failed:
            self._reply.setSFString('')
            raise RuntimeError('terminal native clock failure')
        # Retain the last still-fresh response while reading this tick. Clearing
        # and then replacing it on every healthy tick would expose a transient
        # empty field to the concurrently stepping pilot. Failures revoke
        # immediately in _close; valid ticks publish exactly one final value.
        try:
            now = _now_ms(self._robot.getTime())
        except Exception:
            self._clock_failed = True
            self._close(self._last_ms or 0, 'invalid-native-clock')
            raise
        if self._last_ms is not None and now <= self._last_ms:
            self._clock_failed = True
            self._close(self._last_ms, 'regressed-native-clock')
            raise RuntimeError('terminal native clock failure')
        if self._last_ms is not None and now - self._last_ms != 8:
            self._close(now, 'native-observation-gap')
            self._last_ms = now
            return
        self._last_ms = now
        try:
            source = self._robot.getFromId(self._vehicle_id)
            if (self._robot.getSelf().getId() != self._self_id or
                    source is None or source.getId() != self._vehicle_id):
                raise RuntimeError('native source replaced')
            raw = self._request.getSFString()
            event = parse_flight_channel(raw, self.course.identifier)
            if event is None:
                if self._context is not None:
                    self._close(now, 'native-context-revoked')
                else:
                    self._reply.setSFString('')
                return
            context = event if type(event) is Challenge else event.challenge
            if context.attempt <= self._closed_attempt:
                self._reply.setSFString('')
                return
            if context != self._context:
                if type(event) is not Challenge:
                    self._context = context
                    self._close(now, 'start-without-fresh-reset')
                    return
                if self._context is not None and context.attempt <= self._context.attempt:
                    # During startup the pilot can lose raw idle/ground before
                    # its stable-ground bit exists, and issue a new nonce for
                    # the same still-unused attempt. No response was issued:
                    # discard that partial window and attest the new epoch.
                    # A Ready, admitted or refuted attempt cannot use this path.
                    unused_bootstrap = (context.attempt == self._context.attempt and
                        self.phase == 'observing-reset' and not self._ready and
                        self._active is None)
                    if not unused_bootstrap:
                        self._close(now, 'changed-native-epoch-without-reset')
                        return
                self._context = context
                self._reply.setSFString('')
                self._active = None
                self._start_ms = None
                self._positive_written = False
                self.observation = None
                self._ground_since = None
                self._challenge_since = now
                self._ready = False
                self._wire = EvaluatorHandshake(self.course.identifier)
                self.phase = 'observing-reset'
            # The pilot publishes its first challenge AFTER that tick's sample
            # hook. An initial empty model may therefore last one pilot period;
            # this bootstrap wait never grants READY. Once data have been
            # observed, absence is terminal.
            model = self._model.getSFString()
            if (self.observation is None and type(event) is Challenge and
                    model == '' and now - self._challenge_since <= 32):
                return
            vehicle = read_native_evaluator_scene(
                self._robot, self.course, self._scene_fields, self._scene_snapshot)
            if vehicle.getId() != self._vehicle_id:
                raise RuntimeError('native observation vehicle replaced')
            observation = NativeCourseObservation(
                now, read_kinematics(vehicle, now),
                parse_flight_observation(model, event, now), read_contacts(vehicle, now))
            if observation.flight.challenge != context or _now_ms(self._robot.getTime()) != now:
                raise RuntimeError('native context/tick changed during observation')
            previous = self.observation
            self.observation = observation
            if (self._active is not None and previous is not None and
                    math.dist(previous.kinematics.position, observation.kinematics.position) > .06):
                raise RuntimeError('discontinuous native pose')
            data = self._channel.getSFString()
            if type(event) is Challenge:
                if self._active is not None or data != f'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 {context.attempt}':
                    raise RuntimeError('native reset marker mismatch')
                if self._ground(observation):
                    if self._ground_since is None:
                        self._ground_since = now
                else:
                    if self._ready:
                        self._close(now, 'native-reset-evidence-lost')
                        return
                    self._ground_since = None
                    self._ready = False
                    self._reply.setSFString('')
                if self._ground_since is not None and now - self._ground_since >= 500:
                    reply = self._wire.observe(raw, now, native_validated=True)
                    if not reply:
                        raise RuntimeError('native readiness wire refused')
                    self._reply.setSFString(reply)
                    self._ready = True
                    self.phase = 'ready'
                return
            if event.state != 'admitted':
                self._close(now, 'time-limit' if event.state == 'deadline' else 'runtime-failure')
                return
            if self._active is None:
                if not self._ready or event.start_ms > now or now - event.start_ms > 32:
                    raise RuntimeError('native start without fresh admission')
                self._active = start_pure_attempt(self.course, context.attempt,
                                                  self._origin_z, event.start_ms)
                self._start_ms = event.start_ms
            elif event.start_ms != self._start_ms:
                raise RuntimeError('native start timestamp changed')
            if now - self._start_ms >= DEADLINE_MS:
                self._close(now, 'time-limit')
                return
            if now == self._start_ms:
                self._reply.setSFString('')
                return  # ALIVE must be strictly after admission, as in the C++ guard.
            if data == self._outcome('not-achieved') or data == (
                    f'WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1 attempt={context.attempt} oracle={ORACLE}'):
                self._close(now, 'runtime-failure')
                return
            completed = data == (f'WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt={context.attempt} oracle={ORACLE}')
            if data == self._outcome('achieved') and not self._positive_written:
                raise RuntimeError('unissued native positive outcome')
            if data not in (f'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 {context.attempt}',
                            self._outcome('achieved')) and not completed:
                raise RuntimeError('native outcome/attempt marker mismatch')
            reply = self._wire.observe(raw, now, native_validated=True)
            if not reply:
                raise RuntimeError('native liveness wire refused')
            if not self._positive_written:
                self._active = observe_pure_attempt(self._active, context.attempt, now,
                    observation.kinematics.position, observation.kinematics.velocity[:3],
                    contacts=[point.point for point in observation.contacts.points], completed=completed)
                result = self._active.result
                if result is not None:
                    if result.status != 'achieved':
                        self._close(now, result.reason)
                        return
                    if not self._landed(observation):
                        self._close(now, 'unconfirmed-native-landing')
                        return
                    self._channel.setSFString(self._outcome('achieved'))
                    self._positive_written = True
            elif not self._landed(observation):
                self._close(now, 'native-landing-evidence-lost')
                return
            self._reply.setSFString(reply)  # keep ALIVE after a positive publication
            self.phase = 'result-published' if self._positive_written else 'active'
        except Exception as error:
            self._close(now, 'invalid-native-observation', error=error)


def serve_native(robot, identifier):
    evaluator = NativeRouteEvaluator(robot, identifier)
    while robot.step(8) != -1:
        evaluator.tick()

