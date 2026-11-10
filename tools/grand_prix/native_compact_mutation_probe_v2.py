"""Bounded real-Webots negative probes for private compact collider v2.

ONLY enabled in isolated CI diagnostics. No pupil program, admission, flight
or oracle uses this code. Each mutation is reversed before history runs.
"""
import ctypes

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


def run(supervisor, native, expected, rectangles):
    """Read, mutate, read/refuse, restore, read, RESET physics, with true RPCs.

    The saved stale revision is tested at the native guarded velocity setter.
    We do not validate real-flight action, Webots GUI edits or a full world
    reload. A try/finally restores each field before the official checker.
    """
    read = native.wb_supervisor_collider_batch_read
    clock = round(supervisor.getTime() * 1000)
    ident = supervisor.getSelf().getId()

    def frame():
        buffer = ctypes.create_string_buffer(MAX_BYTES)
        size = ctypes.c_int32(0)
        if not read(buffer, MAX_BYTES, ctypes.byref(size)):
            raise RuntimeError('native compact read unavailable during mutation test')
        return parse_native_inventory(buffer.raw[:size.value],
                                      time_ms=clock, supervisor_id=ident)

    def matched():
        value = frame()
        compare_native_canons(value, expected, route_rectangles=rectangles)
        return value

    before = matched()
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
        field.setSFVec3f([previous[0] + 0.02, previous[1], previous[2]])
        moved = frame()
        if moved['revision'] <= before['revision'] or moved['incarnation'] != before['incarnation']:
            raise RuntimeError('canonical translation did not advance native scene revision')
        _refused(lambda: compare_native_canons(moved, expected, route_rectangles=rectangles),
                 'moved canonical Solid')
    finally:
        field.setSFVec3f(list(previous))
    restored = matched()
    if restored['revision'] <= moved['revision'] or restored['incarnation'] != before['incarnation']:
        raise RuntimeError('canonical restore did not advance native revision')
    result['checks'].append('canonical_move_restore_same_step_revision')

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
        plane_field.setSFVec2f([max(.1, old_size[0] / 8), max(.1, old_size[1] / 8)])
        floor_changed = frame()
        if floor_changed['revision'] <= restored['revision']:
            raise RuntimeError('Floor PROTO change did not advance native revision')
        _refused(lambda: compare_native_canons(floor_changed, expected, route_rectangles=rectangles),
                 'Floor Plane shrink')
    finally:
        plane_field.setSFVec2f(list(old_size))
    floor_restored = matched()
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
        root_children.importMFNodeFromString(-1, foreign)
        inserted = root_children.getCount() == before_count + 1
        if not inserted:
            raise RuntimeError('native physical foreign Solid insertion failed')
        native_foreign = frame()
        if native_foreign['revision'] <= floor_restored['revision']:
            raise RuntimeError('foreign body insertion failed to advance scene revision')
        _refused(lambda: compare_native_canons(native_foreign, expected, route_rectangles=rectangles),
                 'foreign Cylinder Solid')
    finally:
        if inserted:
            root_children.removeMF(before_count)
    clean = matched()
    if root_children.getCount() != before_count or clean['revision'] <= native_foreign['revision']:
        raise RuntimeError('foreign body removal did not restore native scene/revision')
    result['checks'].append('foreign_non_box_insert_remove_refused')

    before_reset = clean
    supervisor.simulationResetPhysics()
    after_reset = matched()
    if after_reset['revision'] <= before_reset['revision']:
        raise RuntimeError('native simulationResetPhysics failed to invalidate scene revision')
    result['checks'].append('native_physics_reset_revision_invalidation')
    result['final_revision'] = after_reset['revision']
    result['status'] = 'PASS'
    return result
