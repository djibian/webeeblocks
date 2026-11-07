"""Avoid synchronous lookups of nonexistent built-in Webots fields.

R2025a supervisor.c caches successful get_field calls, but a missing field
flushes the controller connection on EVERY call. Traversing visual Box/Shape/
Pose nodes by probing all possible graph edges makes each 8-ms check perform
hundreds of such round trips. Enumerate the immutable built-in declarations
once per type and per check instead. Never cache a field VALUE or a node edge.

PROTO interfaces/internal fields are deliberately not inferred from a base
type. Unsupported test APIs use the original lookup; no check is exempted.
"""


class NativeFieldLookup:
    """Short-lived, read-only schema lookup, discarded after one scene check."""

    def __init__(self):
        self._schemas = {}

    def get(self, node, name):
        if node.isProto() or not all(callable(getattr(node, key, None)) for key in
                ('getNumberOfFields', 'getFieldByIndex')):
            return node.getField(name)
        # A non-PROTO Webots built-in has one fixed declaration for its type.
        # The caller creates a fresh lookup for every check; no scene identity,
        # previous topology, mutable value or authority survives here.
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
        return node.getField(name)  # Actual handle; all reads remain live.
