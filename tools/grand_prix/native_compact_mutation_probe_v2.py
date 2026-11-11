"""Bounded real-Webots negative probes for private compact collider v2.

ONLY enabled in isolated CI diagnostics. No pupil program, admission, flight
or oracle uses this code. Each mutation is reversed before history runs.
"""
import ctypes
import json
import os

from tools.grand_prix.native_compact_colliders_v1 import (
    MAX_BYTES, parse_native_inventory, compare_native_canons,
)


class RevisionToken(ctypes.Structure):
    _fields_ = [('incarnation', ctypes.c_ubyte * 16),
                ('revision', ctypes.c_uint64)]


def _refused(fn, label):
    try:
        fn()
    except (ValueError, RuntimeError):
        return
    raise RuntimeError('native adversarial observation accepted ' + label)


def run(supervisor, native, expected, rectangles, course_identifier):
    """Read, mutate, read/refuse, restore, read, RESET physics, with true RPCs.

    The saved stale revision is tested at the native guarded velocity setter.
    We do not validate real-flight action, Webots GUI edits or a full world
    reload. A try/finally restores each field before the official checker.
    """
    if not isinstance(course_identifier, str) or not course_identifier:
        raise ValueError('canonical course identifier required for historical negatives')
    from tools.grand_prix.evaluator_scene_identity_v2 import check_native_evaluator_scene

    def historical():
        check_native_evaluator_scene(supervisor, course_identifier)

    read = native.wb_supervisor_collider_batch_read
    clock = round(supervisor.getTime() * 1000)
    ident = supervisor.getSelf().getId()
    trace_file = os.environ.get('WEBEEBLOCKS_GP_MUTATION_TRACE_FILE')
    stage = 'initial'

    def trace(event, **details):
        if not trace_file:
            return
        # Independent, bounded forensic record: survives a native engine
        # access violation that cuts Webots' forwarded controller stdout.
        datum = {'event': event, 'stage': stage, 'sim_ms': round(supervisor.getTime() * 1000)}
        datum.update(details)
        fd = os.open(trace_file, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, (json.dumps(datum, sort_keys=True) + '\n').encode('utf-8'))
            os.fsync(fd)
        finally:
            os.close(fd)

    def frame():
        trace('frame_begin')
        buffer = ctypes.create_string_buffer(MAX_BYTES)
        size = ctypes.c_int32(0)
        if not read(buffer, MAX_BYTES, ctypes.byref(size)):
            trace('frame_refused_by_controller', size=size.value)
            raise RuntimeError('native compact read unavailable during mutation test')
        trace('frame_wire_received', size=size.value)
        value = parse_native_inventory(buffer.raw[:size.value],
                                       time_ms=clock, supervisor_id=ident)
        trace('frame_parsed', revision=value['revision'], count=value['count'])
        return value

    def matched():
        value = frame()
        compare_native_canons(value, expected, route_rectangles=rectangles)
        return value

    trace('probe_begin')
    before = matched()
    trace('initial_matched', revision=before['revision'])
    historical()  # Initial same-step independent historical acceptance.
    trace('initial_historical_accepted')
    result = {'schema': 2, 'status': 'UNPROVEN', 'clock_ms': clock,
              'incarnation': before['incarnation'], 'checks': []}
    get_revision = native.wb_supervisor_get_scene_revision
    get_revision.argtypes = [ctypes.POINTER(RevisionToken)]
    get_revision.restype = ctypes.c_bool
    guard = native.wb_supervisor_set_velocity_at_scene_revision
    guard.argtypes = [ctypes.c_int32, ctypes.POINTER(RevisionToken),
                      ctypes.POINTER(ctypes.c_double)]
    guard.restype = ctypes.c_bool
    old_token = RevisionToken()
    if not get_revision(ctypes.byref(old_token)):
        raise RuntimeError('cannot read engine revision at native mutation start')
    if (bytes(old_token.incarnation).hex() != before['incarnation'] or
            old_token.revision != before['revision']):
        raise RuntimeError('native batch and engine revision query disagree')

    target = supervisor.getFromDef(expected[0].name)
    if target is None or target.getTypeName() != 'Solid':
        raise RuntimeError('canonical native target unavailable')
    field = target.getField('translation')
    previous = tuple(field.getSFVec3f())
    moved = None
    try:
        stage = 'move'
        trace('set_begin', node=expected[0].name, field='translation', original=previous)
        field.setSFVec3f([previous[0] + 0.02, previous[1], previous[2]])
        trace('set_return')
        moved = frame()
        trace('move_captured', revision=moved['revision'])
        old_geometry = next((s for s in before['solids'] if s['name'] == expected[0].name), None)
        new_geometry = next((s for s in moved['solids'] if s['name'] == expected[0].name), None)
        if old_geometry is None or new_geometry is None:
            raise RuntimeError('cannot witness canonical native position change')
        edge = {
            'schema': 2, 'phase': 'immediately_after_set_before_restore',
            'sim_ms_before': before['clock_ms'],
            'sim_ms_after': moved['clock_ms'],
            'revision_before': before['revision'],
            'revision_after': moved['revision'],
            'position_before': old_geometry['position'],
            'position_after': new_geometry['position'],
            'expected_position_after': [previous[0] + .02, previous[1], previous[2]],
            'same_incarnation': moved['incarnation'] == before['incarnation'],
        }
        print('GP_COMPACT_MUTATION_EDGE_V2 ' +
              json.dumps(edge, sort_keys=True, separators=(',', ':')), flush=True)
        if moved['incarnation'] != before['incarnation']:
            raise RuntimeError('native mutation crossed scene incarnation')
        if moved['clock_ms'] != before['clock_ms']:
            raise RuntimeError('native mutation did not remain at same simulation time')
        if moved['revision'] <= before['revision']:
            if new_geometry['position'] != old_geometry['position']:
                raise RuntimeError('COVERAGE_GAP: applied native translation without scene revision')
            raise RuntimeError('PENDING_NOT_COMMITTED: translation remains unapplied at native read')
        if (abs(new_geometry['position'][0] - (previous[0] + .02)) > 1e-9 or
                any(abs(new_geometry['position'][i] - previous[i]) > 1e-9 for i in (1, 2))):
            raise RuntimeError('native revision advanced but translation was not applied exactly')
        _refused(lambda: compare_native_canons(moved, expected, route_rectangles=rectangles),
                 'moved canonical Solid')
        _refused(historical, 'historical moved canonical Solid')
    finally:
        stage = 'restore'
        trace('set_begin', node=expected[0].name, field='translation', original=previous)
        field.setSFVec3f(list(previous))
        trace('set_return')
    restored = matched()
    trace('restored_matched', revision=restored['revision'])
    historical()  # Both readers accept the fully restored same-tick scene.
    if restored['revision'] <= moved['revision'] or restored['incarnation'] != before['incarnation']:
        raise RuntimeError('canonical restore did not advance native revision')
    result['checks'].append('canonical_move_restore_same_step_revision')
    result['native_move_revision_before'] = before['revision']
    result['native_move_revision_after'] = moved['revision']
    result['native_restore_revision'] = restored['revision']
    result['same_simulation_clock_move_restore'] = (
        before['clock_ms'] == moved['clock_ms'] == restored['clock_ms'])
    if not result['same_simulation_clock_move_restore']:
        raise RuntimeError('native move/restore test crossed a physics step')

    # Engine-side check and actual setter must be atomic. The stale token
    # must not change the drone velocity even if geometry has been restored.
    root_children = supervisor.getRoot().getField('children')
    pilot = [root_children.getMFNode(i) for i in range(root_children.getCount())
             if root_children.getMFNode(i).getTypeName() == 'Crazyflie']
    if len(pilot) != 1:
        raise RuntimeError('missing/duplicated native pilot')
    zero = (ctypes.c_double * 6)(0, 0, 0, 0, 0, 0)
    if guard(pilot[0].getId(), ctypes.byref(old_token), zero):
        raise RuntimeError('stale native guarded effect was applied')
    if frame()['revision'] != restored['revision']:
        raise RuntimeError('refused stale native effect mutated the scene revision')
    result['checks'].append('stale_native_effect_refused_after_restore')

    # Modify a real pinned Floor PROTO field and read the actual Plane in the
    # native inventory, not a fabricated copy of the VRML scene.
    floors = [root_children.getMFNode(i) for i in range(root_children.getCount())
              if root_children.getMFNode(i).getTypeName() == 'Floor']
    if len(floors) != 1:
        raise RuntimeError('missing/duplicated Floor PROTO')
    plane_field = floors[0].getField('size')
    old_size = tuple(plane_field.getSFVec2f())
    floor_changed = None
    try:
        stage = 'floor_mutation'
        trace('set_begin', node='Floor', field='size', original=old_size)
        plane_field.setSFVec2f([max(.1, old_size[0] / 8), max(.1, old_size[1] / 8)])
        trace('set_return')
        floor_changed = frame()
        trace('floor_captured', revision=floor_changed['revision'])
        if floor_changed['revision'] <= restored['revision']:
            raise RuntimeError('Floor PROTO change did not advance native revision')
        _refused(lambda: compare_native_canons(floor_changed, expected, route_rectangles=rectangles),
                 'Floor Plane shrink')
        _refused(historical, 'historical Floor Plane shrink')
    finally:
        stage = 'floor_restore'
        trace('set_begin', node='Floor', field='size', original=old_size)
        plane_field.setSFVec2f(list(old_size))
        trace('set_return')
    floor_restored = matched()
    trace('floor_restored', revision=floor_restored['revision'])
    historical()
    if floor_restored['revision'] <= floor_changed['revision']:
        raise RuntimeError('Floor restore did not advance native scene revision')
    result['checks'].append('floor_proto_plane_mutate_restore')

    # Add then remove a *foreign non-Box* physical body at identical simulation
    # time; the historical checker must not see a modified scene after cleanup.
    before_count = root_children.getCount()
    foreign = ('DEF WB_COMPACT_INTRUDER Solid { translation 5 5 0.5 '
               'locked TRUE boundingObject Cylinder { radius 0.1 height 0.2 } }')
    inserted = False
    native_foreign = None
    try:
        stage = 'foreign_insert'
        trace('import_begin')
        root_children.importMFNodeFromString(-1, foreign)
        trace('import_return')
        inserted = root_children.getCount() == before_count + 1
        if not inserted:
            raise RuntimeError('native physical foreign Solid insertion failed')
        native_foreign = frame()
        if native_foreign['revision'] <= floor_restored['revision']:
            raise RuntimeError('foreign body insertion failed to advance scene revision')
        _refused(lambda: compare_native_canons(native_foreign, expected, route_rectangles=rectangles),
                 'foreign Cylinder Solid')
        _refused(historical, 'historical foreign Cylinder Solid')
    finally:
        if inserted:
            stage = 'foreign_remove'
            trace('remove_begin')
            root_children.removeMF(before_count)
            trace('remove_return')
    clean = matched()
    historical()
    if root_children.getCount() != before_count or clean['revision'] <= native_foreign['revision']:
        raise RuntimeError('foreign body removal did not restore native scene/revision')
    result['checks'].append('foreign_non_box_insert_remove_refused')

    before_reset = clean
    stage = 'physics_reset'
    trace('reset_begin')
    supervisor.simulationResetPhysics()
    trace('reset_return')
    after_reset = matched()
    historical()
    if after_reset['revision'] <= before_reset['revision']:
        raise RuntimeError('native simulationResetPhysics failed to invalidate scene revision')
    result['checks'].append('native_physics_reset_revision_invalidation')
    result['final_revision'] = after_reset['revision']
    result['same_step_historical_negative_cases'] = 3
    result['same_step_historical_positive_restorations'] = 3
    result['status'] = 'PASS'
    return result
