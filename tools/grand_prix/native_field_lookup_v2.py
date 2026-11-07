"""Resolve scene fields and subscribe to the R2025a Supervisor step stream.

R2025a supervisor.c caches successful get_field calls, but a missing field
flushes the controller connection on EVERY call. Traversing visual Box/Shape/
Pose nodes by probing all possible graph edges makes each 8-ms check perform
hundreds of such round trips. Enumerate the immutable built-in declarations
once per built-in type instead. Track the observed SF values and world poses
at 8 ms, so Webots sends them together in the next step response. Getters
still run on every check. The native API requests missing current samples
synchronously. MFNode/MFString entries always use the normal live getters.

PROTO interfaces/internal fields are deliberately not inferred from a base
type. Unsupported test APIs use the original lookup; no check is exempted.
"""


class NativeFieldLookup:
    """Reuse only immutable built-in declarations across scene checks."""

    def __init__(self, *, prepare_tracking=False):
        self._schemas = {}
        self._subscriptions = [] if prepare_tracking else None
        self._tracking = False

    def start_tracking(self):
        """Subscribe once, after a successful full check of the loaded scene."""
        for subscribe in self._subscriptions:
            subscribe(8)
        self._subscriptions = None
        self._tracking = True

    def position(self, node):
        subscribe = getattr(node, 'enablePoseTracking', None)
        if self._subscriptions is not None and callable(subscribe):
            self._subscriptions.append(subscribe)
        if self._tracking and callable(subscribe):
            pose = node.getPose()
            return pose[3], pose[7], pose[11]
        return node.getPosition()

    def _watch(self, field):
        if self._subscriptions is not None and field is not None:
            subscribe = getattr(field, 'enableSFTracking', None)
            if callable(subscribe) and 0 < field.getType() <= field.SF_NODE:
                self._subscriptions.append(subscribe)
        return field

    def get(self, node, name):
        if node.isProto() or not all(callable(getattr(node, key, None)) for key in
                ('getNumberOfFields', 'getFieldByIndex')):
            return self._watch(node.getField(name))
        # A non-PROTO Webots built-in has one fixed declaration for its type.
        # Every actual handle and mutable value still comes from Webots.
        kind = node.getTypeName()
        if type(kind) is not str or not kind:
            raise RuntimeError('unavailable native built-in field schema')
        if kind not in self._schemas:
            count = node.getNumberOfFields()
            if type(count) is not int or not 0 <= count <= 4096:
                raise RuntimeError('invalid native built-in field count')
            names = set()
            for index in range(count):
                field = node.getFieldByIndex(index)
                key = field.getName() if field is not None else None
                if type(key) is not str or not key or key in names:
                    raise RuntimeError('invalid native built-in field declaration')
                names.add(key)
            self._schemas[kind] = frozenset(names)
        if name not in self._schemas[kind]:
            return None
        return self._watch(node.getField(name))
