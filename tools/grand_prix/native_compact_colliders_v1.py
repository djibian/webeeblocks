"""Read-only R2025a native collider-inventory experiment.

Private matched engine + libController message 107. This never supplies an
evaluator verdict or a flight-authority token. Unsupported physical shapes,
PROTO internals, Floor and partial #923 revisions remain non-authoritative.
"""
import ctypes
import json
import math
import os
from pathlib import Path
import struct
import time

HEADER = struct.Struct('<iiiiidQ16sQ')
ENTRY = struct.Struct('<iiii48s13d')
TAIL = struct.Struct('<QQ')
MAX_RECORDS = 128
MAX_BYTES = 32768
PREFIX = 'GP_COMPACT_COLLIDER_V1 '
ROOT_PREFIX = ('GP_V2_L_', 'GP_V2_H_', 'GP_V2_FINAL_')


def parse_native_inventory(raw, *, time_ms, supervisor_id):
    """Decode precisely one terminal binary native answer; reject all tails."""
    if not isinstance(raw, bytes) or not HEADER.size + TAIL.size <= len(raw) <= MAX_BYTES:
        raise ValueError('compact native inventory length')
    version, count, root_count, proto_roots, source_id, clock, revision, incarnation, root_hash = HEADER.unpack_from(raw)
    if version != 2 or count < 0 or count > MAX_RECORDS or len(raw) != HEADER.size + count * ENTRY.size + TAIL.size:
        raise ValueError('invalid native batch version/count/tail')
    if (source_id != supervisor_id or not math.isfinite(clock) or
            abs(clock - time_ms) > 0.001 or int(round(clock)) % 8 or
            root_count < 2 or proto_roots < 0 or proto_roots > root_count or
            revision == 0 or incarnation == bytes(16) or root_hash == 0):
        raise ValueError('native batch provenance or 8-ms clock mismatch')
    solids = []
    ids = set()
    for index in range(count):
        id_, parent, bounding, flags, name, *values = ENTRY.unpack_from(raw, HEADER.size + index * ENTRY.size)
        if id_ <= 0 or id_ in ids or not 0 <= flags < 65536 or any(not math.isfinite(v) for v in values):
            raise ValueError('invalid native physical record')
        ids.add(id_)
        if name.split(bytes((0,)), 1)[0].find(bytes((0,))) >= 0:
            raise ValueError('invalid native fixed name')
        try:
            def_name = name.split(bytes((0,)), 1)[0].decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('nonascii collider DEF') from exc
        if bytes((0,)) in name and any(name[len(def_name) + 1:]):
            raise ValueError('nonzero native name padding')
        solids.append(dict(id=id_, parent=parent, bounding_type=bounding, flags=flags,
                           name=def_name, position=values[:3], physical=values[3:6],
                           visual=values[6:9], rotation=values[9:13]))
    producer_ns, serialization_ns = TAIL.unpack_from(raw, len(raw) - TAIL.size)
    if producer_ns <= 0 or serialization_ns <= 0 or producer_ns > 100_000_000_000 or serialization_ns > 100_000_000_000:
        raise ValueError('invalid native timing evidence')
    return dict(clock_ms=clock, count=count, root_count=root_count,
                proto_roots=proto_roots, supervisor_id=source_id, revision=revision,
                incarnation=incarnation.hex(), roots_hash=root_hash, solids=solids,
                payload_bytes=len(raw), native_producer_ns=producer_ns,
                native_serialization_ns=serialization_ns)


def _equal_triplet(actual, expected):
    # Match the *historical* 6-decimal Webots serialization and 1e-9 tolerance.
    return len(actual) == 3 and all(math.isclose(a, float(f'{e:.6f}'), rel_tol=0, abs_tol=1e-9)
                                    for a, e in zip(actual, expected))


def compare_native_canons(snapshot, expected, *, route_rectangles=()):
    """Strict Box and Floor comparison, not complete PROTO/scene attestation."""
    canonical = [s for s in snapshot['solids'] if s['name'].startswith(ROOT_PREFIX)]
    by_name = {s['name']: s for s in canonical}
    targets = {b.name: b for b in expected}
    if len(canonical) != len(targets) or len(by_name) != len(targets) or set(by_name) != set(targets):
        raise ValueError('missing/extra/duplicate native canonical DEF')
    for name, box in targets.items():
        s = by_name[name]
        required = 1 | 2 | 16 | 32 | 128 | 2048
        prohibited = 4 | 8 | 64 | 256 | 512 | 1024 | 8192 | 16384 | 32768
        if (s['flags'] & required) != required or (s['flags'] & prohibited):
            raise ValueError('noncanonical direct Box, visible Shape or root identity: ' + name)
        if (not _equal_triplet(s['position'], box.position) or
                not _equal_triplet(s['physical'], box.size) or
                not _equal_triplet(s['visual'], box.size) or
                abs(s['rotation'][3]) > 1e-6):
            raise ValueError('native canonical geometry mismatch: ' + name)
    # Physical Floor is a root PROTO Solid containing a direct Plane.
    floors = [body for body in snapshot['solids'] if body['flags'] & 512]
    if len(floors) != 1 or snapshot['proto_roots'] < 2:
        raise ValueError('missing/duplicate native Floor PROTO')
    floor = floors[0]
    floor_required = 1 | 8 | 16 | 256 | 512
    if ((floor['flags'] & floor_required) != floor_required or
            (floor['flags'] & (64 | 128 | 16384))):
        raise ValueError('Floor must be a locked root PROTO with direct Plane')
    if (abs(floor['position'][2]) > 1e-9 or abs(floor['rotation'][3]) > 1e-9 or
            min(floor['physical'][:2]) <= 0 or floor['physical'][2] != 0):
        raise ValueError('invalid physical Floor/Plane position, dimensions or rotation')
    if route_rectangles:
        x, y = floor['position'][:2]
        sx, sy = floor['physical'][:2]
        for xmin, ymin, xmax, ymax in route_rectangles:
            if not (x - sx / 2 <= xmin <= xmax <= x + sx / 2 and
                    y - sy / 2 <= ymin <= ymax <= y + sy / 2):
                raise ValueError('Floor Plane does not cover the route')
    vehicles = [body for body in snapshot['solids'] if body['flags'] & 1024]
    evaluators = [body for body in snapshot['solids'] if body['flags'] & 8192]
    if (len(vehicles) != 1 or len(evaluators) != 1 or
            evaluators[0]['name'] != 'GP_ROUTE_EVALUATOR'):
        raise ValueError('missing/duplicate native root pilot or evaluator')
    if ((vehicles[0]['flags'] & (8 | 16 | 1024)) != (8 | 16 | 1024) or
            (evaluators[0]['flags'] & (16 | 8192)) != (16 | 8192)):
        raise ValueError('invalid native root pilot/evaluator provenance')
    accounted = {body['id'] for body in
                 list(by_name.values()) + floors + vehicles + evaluators}
    for body in snapshot['solids']:
        if body['id'] in accounted:
            continue
        if (body['flags'] & 16) or not (body['flags'] & 32768):
            raise ValueError('foreign/unexplained native physical Solid: ' + str(body['id']))
    internal = [body for body in snapshot['solids'] if body['flags'] & 32768]
    return dict(canonical_count=len(targets), floor_verified=True,
                proto_internal_count=len(internal), unknown_count=len(internal),
                extra_root_count=0, proto_roots=snapshot['proto_roots'],
                full_coverage=False)



class NativeCompactColliderShadow:
    """One 107 RPC before the historical checker, and no authority changes."""

    def __init__(self, expected, probe, window=125, route=None):
        self.expected = expected
        self.probe = probe
        if route is None:
            self.route_rectangles = ()
        else:
            from tools.grand_prix.course_footprint_v2 import course_rectangles
            self.route_rectangles = tuple(course_rectangles(route))
        self.window = window
        self.samples = 0
        self.parity = self.shadow_accepted = self.historical_accepted = 0
        self.unknown = self.structure_changes = self.errors = 0
        self.floor_verified = self.proto_internal_total = self.refusals = 0
        self.incarnation_changes = self.revision_changes = 0
        self.bytes_total = self.producer_ns = self.serialization_ns = 0
        self.rpc_ns = self.consumer_ns = 0
        self.last = None
        self.last_root_hash = None
        self.last_token = None
        self.first_incarnation = None
        self.mutation_done = False
        home = Path(os.environ['WEBOTS_HOME'])
        dll = home / ('lib/controller/Controller.dll' if os.name == 'nt' else 'lib/controller/libController.so')
        self.native = ctypes.CDLL(str(dll))
        self.read = self.native.wb_supervisor_collider_batch_read
        self.read.argtypes = (ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int32))
        self.read.restype = ctypes.c_bool

    def observe(self, supervisor):
        begun = time.perf_counter_ns()
        frame = None
        try:
            buf = ctypes.create_string_buffer(MAX_BYTES)
            size = ctypes.c_int32(0)
            native_started = time.perf_counter_ns()
            ok = self.read(buf, MAX_BYTES, ctypes.byref(size))
            native_ns = time.perf_counter_ns() - native_started
            if not ok or not HEADER.size + TAIL.size <= size.value <= MAX_BYTES:
                raise RuntimeError('native compact RPC unavailable')
            decoded_started = time.perf_counter_ns()
            frame = parse_native_inventory(buf.raw[:size.value],
                                           time_ms=supervisor.getTime() * 1000,
                                           supervisor_id=supervisor.getSelf().getId())
            observation = compare_native_canons(frame, self.expected,
                                                route_rectangles=self.route_rectangles)
            decode_ns = time.perf_counter_ns() - decoded_started
            root_hash = frame['roots_hash']
            structure_changed = self.last_root_hash is not None and self.last_root_hash != root_hash
            token = (frame['incarnation'], frame['revision'])
            if self.first_incarnation is None:
                self.first_incarnation = token[0]
            if (not self.mutation_done and
                    os.environ.get('WEBEEBLOCKS_GP_COMPACT_MUTATION_PROBE') == '1' and
                    frame['clock_ms'] >= 400):
                self.mutation_done = True
                try:
                    from tools.grand_prix.native_compact_mutation_probe_v2 import run
                    result = run(supervisor, self.native, self.expected,
                                 self.route_rectangles)
                    self.probe.sink('GP_COMPACT_MUTATION_V2 ' +
                                    json.dumps(result, separators=(',', ':'), sort_keys=True))
                except Exception as mutation_error:
                    self.probe.sink('GP_COMPACT_MUTATION_V2 ' + json.dumps({
                        'schema': 2, 'status': 'UNPROVEN',
                        'reason': type(mutation_error).__name__ + ': ' + str(mutation_error),
                        'clock_ms': frame['clock_ms'],
                    }, separators=(',', ':'), sort_keys=True))
                    raise
            incarnation_changed = self.last_token is not None and token[0] != self.last_token[0]
            revision_changed = self.last_token is not None and token[1] != self.last_token[1]
            self.incarnation_changes += int(incarnation_changed)
            self.revision_changes += int(revision_changed)
            self.last_root_hash = root_hash
            self.last_token = token
            self.floor_verified += int(observation['floor_verified'])
            self.proto_internal_total += observation['proto_internal_count']
            self.bytes_total += frame['payload_bytes']
            self.producer_ns += frame['native_producer_ns']
            self.serialization_ns += frame['native_serialization_ns']
            self.rpc_ns += native_ns
            self.consumer_ns += decode_ns
            self.structure_changes += int(structure_changed)
            self.unknown += int(not observation['full_coverage'] or structure_changed)
            self.last = (not structure_changed and not incarnation_changed, None)
        except Exception as exc:
            self.errors += 1
            self.refusals += 1
            self.last = (False, str(type(exc).__name__) + ': ' + str(exc))
        finally:
            self.probe.record('compact_native_rpc_and_decode', time.perf_counter_ns() - begun)

    def historical(self, accepted, error=None):
        if self.last is None:
            return
        observed, reason = self.last
        self.last = None
        self.samples += 1
        self.parity += int(observed == accepted)
        self.shadow_accepted += int(observed)
        self.historical_accepted += int(accepted)
        if self.samples % self.window == 0:
            self.probe.sink(PREFIX + json.dumps({
                'schema': 1, 'window': self.samples // self.window - 1,
                'samples': self.window, 'canonical_parity': self.parity,
                'canonical_accepted': self.shadow_accepted,
                'historical_accepted': self.historical_accepted,
                'unknown_coverage_samples': self.unknown,
                'root_structure_changes': self.structure_changes,
                'decode_errors': self.errors,
                'native_refusals': self.refusals,
                'floor_verified_samples': self.floor_verified,
                'proto_internal_records': self.proto_internal_total,
                'incarnation_changes': self.incarnation_changes,
                'revision_changes': self.revision_changes,
                'first_incarnation': self.first_incarnation,
                'last_incarnation': self.last_token[0] if self.last_token else None,
                'last_revision': self.last_token[1] if self.last_token else None,
                'whole_scene_qualified': False,
                'payload_bytes': self.bytes_total,
                'native_production_ns': self.producer_ns,
                'native_serialization_ns': self.serialization_ns,
                'native_rpc_total_ns': self.rpc_ns,
                'python_consumption_ns': self.consumer_ns,
                'transfer_plus_controller_dispatch_ns': max(
                    0, self.rpc_ns - self.producer_ns - self.serialization_ns),
                'note': ('Residual is not pure transport: includes scheduling, '
                         'socket, Controller C decoding, request and Python FFI. '
                         'PROTO internals, non-Box and revision coverage require '
                         'the historical authority. Direct Floor Plane is checked.'),
            }, separators=(',', ':'), sort_keys=True))
            self.parity = self.shadow_accepted = self.historical_accepted = 0
            self.unknown = self.structure_changes = self.errors = 0
            self.floor_verified = self.proto_internal_total = self.refusals = 0
            self.incarnation_changes = self.revision_changes = 0
            self.bytes_total = self.producer_ns = self.serialization_ns = 0
            self.rpc_ns = self.consumer_ns = 0
