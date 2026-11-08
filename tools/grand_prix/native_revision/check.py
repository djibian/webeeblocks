"""Falsify the source-built revision fence with native same-time scene writes."""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys


HERE = Path(__file__).resolve().parent
FRAME = HERE.parent / 'native_frame'
sys.path.insert(0, str(FRAME))


class Token(c.Structure):
    _fields_ = [('incarnation', c.c_ubyte * 16), ('revision', c.c_uint64)]


def observe():
    from controller import Supervisor
    from controller.wb import wb
    from probe import Frame, bind_frame_api, require

    robot = Supervisor()
    target = robot.getFromDef('TARGET')
    collider = robot.getFromDef('COLLIDER')
    require(target is not None and collider is not None, 'missing fixture nodes')
    target_id = target.getId()
    root_children = robot.getRoot().getField('children')
    request, _ = bind_frame_api()

    read = wb.wb_supervisor_physics_frame_read_with_revision
    read.argtypes = [c.POINTER(Frame), c.POINTER(Token)]
    read.restype = c.c_bool
    current = wb.wb_supervisor_get_scene_revision
    current.argtypes = [c.POINTER(Token)]
    current.restype = c.c_bool
    effect = wb.wb_supervisor_set_velocity_at_scene_revision
    effect.argtypes = [c.c_int32, c.POINTER(Token), c.POINTER(c.c_double)]
    effect.restype = c.c_bool

    def token_now():
        token = Token()
        require(current(c.byref(token)) and any(token.incarnation), 'no native scene revision')
        return token

    original = list(collider.getPosition())
    shifted = [original[0] + .1, *original[1:]]
    collider.saveState('canonical')
    collider.getField('translation').setSFVec3f(shifted)
    require(robot.step(8) != -1 and list(collider.getPosition()) == shifted, 'could not save moved collider')
    collider.saveState('shifted')
    collider.loadState('canonical')
    require(list(collider.getPosition()) == original, 'could not restore collider')

    before_step = token_now()
    captured = Token()
    frame = Frame()
    require(request(target_id) and robot.step(8) != -1 and read(c.byref(frame), c.byref(captured)),
            'missing compact frame plus revision')
    instant = robot.getTime()
    require(frame.time_ms == round(1000 * instant) and
            bytes(captured.incarnation) == bytes(before_step.incarnation) and
            captured.revision == before_step.revision, 'ordinary physics dirtied the experimental counter')

    collider.loadState('shifted')
    require(robot.getTime() == instant and list(collider.getPosition()) == shifted, 'missing native movement pulse')
    moved = token_now()
    collider.loadState('canonical')
    require(robot.getTime() == instant and list(collider.getPosition()) == original, 'missing native restoration')
    restored = token_now()
    require(captured.revision < moved.revision < restored.revision, 'the two writes must advance the native revision')
    require(bytes(captured.incarnation) == bytes(moved.incarnation) == bytes(restored.incarnation),
            'mutation masked by incarnation change')

    velocity = (c.c_double * 6)(.125, 0, 0, 0, 0, 0)
    before = list(target.getVelocity())
    require(not effect(target_id, c.byref(captured), velocity) and list(target.getVelocity()) == before,
            'stale frame token allowed the native velocity effect')

    # A current revision alone is insufficient: incarnation is part of the
    # exact token. Conversely, a correct incarnation cannot mint a future
    # revision. Both refusals must leave the physical effect unapplied.
    wrong_incarnation = Token()
    wrong_incarnation.incarnation[:] = restored.incarnation[:]
    wrong_incarnation.incarnation[0] ^= 1
    wrong_incarnation.revision = restored.revision
    future_revision = Token()
    future_revision.incarnation[:] = restored.incarnation[:]
    future_revision.revision = restored.revision + 1
    require(not effect(target_id, c.byref(wrong_incarnation), velocity) and
            list(target.getVelocity()) == before,
            'incorrect incarnation with current revision allowed the native effect')
    require(not effect(target_id, c.byref(future_revision), velocity) and
            list(target.getVelocity()) == before,
            'future revision with current incarnation allowed the native effect')
    require(token_now().revision == restored.revision,
            'rejected native effects changed the scene revision')

    require(effect(target_id, c.byref(restored), velocity) and list(target.getVelocity()) == list(velocity),
            'fresh token did not apply the native velocity effect')
    applied = token_now()
    require(restored.revision < applied.revision and not effect(target_id, c.byref(restored), velocity),
            'velocity effect could be replayed with a consumed revision')

    target.resetPhysics()
    reset = token_now()
    require(robot.getTime() == instant and applied.revision < reset.revision and
            list(target.getVelocity()) == [0.] * 6, 'same-time resetPhysics did not invalidate and zero velocity')

    count = root_children.getCount()
    root_children.importMFNodeFromString(-1, 'DEF REVISION_PROBE_NODE Solid { name "revision probe" }')
    added = token_now()
    node = robot.getFromDef('REVISION_PROBE_NODE')
    require(node is not None and root_children.getCount() == count + 1, 'fixture insert had no native effect')
    node.remove()
    removed = token_now()
    require(robot.getTime() == instant and root_children.getCount() == count and
            reset.revision < added.revision < removed.revision, 'transient topology did not invalidate')
    require(not effect(target_id, c.byref(captured), velocity), 'older frame token resurrected')
    require(added.revision == reset.revision + 1 and removed.revision == added.revision + 1,
            'node insertion or removal was counted twice')

    mesh = robot.getFromDef('MESH_COLLIDER').getField('boundingObject').getSFNode()
    points = mesh.getField('coord').getSFNode().getField('point')
    original_points = [list(points.getMFVec3f(i)) for i in range(points.getCount())]
    inserted_point = [1., 1., .5]
    mf_captured = Token()
    require(request(target_id) and robot.step(8) != -1 and read(c.byref(frame), c.byref(mf_captured)),
            'missing frame before native MF geometry mutation')
    mf_instant = robot.getTime()
    points.insertMFVec3f(1, inserted_point)
    require(robot.getTime() == mf_instant and points.getCount() == len(original_points) + 1 and
            list(points.getMFVec3f(1)) == inserted_point, 'MF insertion did not change the collision triangle')
    mf_inserted = token_now()
    points.removeMF(1)
    require(robot.getTime() == mf_instant and
            [list(points.getMFVec3f(i)) for i in range(points.getCount())] == original_points,
            'MF removal did not restore the collision triangle')
    mf_removed = token_now()
    before_mf_effect = list(target.getVelocity())
    require(not effect(target_id, c.byref(mf_captured), velocity) and
            list(target.getVelocity()) == before_mf_effect,
            'same-time primitive MF insertion/removal allowed a stale velocity effect')
    require(mf_inserted.revision == mf_captured.revision + 1 and mf_removed.revision == mf_inserted.revision + 1 and
            bytes(mf_captured.incarnation) == bytes(mf_inserted.incarnation) == bytes(mf_removed.incarnation),
            'native MF pulse did not produce two distinct revisions in the same world')
    # The global simulation reset is distinct from WbSolid::reset and the
    # per-node reset. Invalidate an already-live token before clearing ODE.
    global_prepare = token_now()
    require(effect(target_id, c.byref(global_prepare), velocity),
            'could not establish moving Solid before global physics reset')
    global_captured = token_now()
    require(abs(target.getVelocity()[0] - velocity[0]) < 1e-9,
            'global reset witness did not establish a nonzero velocity')
    reset_instant = robot.getTime()
    robot.simulationResetPhysics()
    global_after = token_now()
    require(robot.getTime() == reset_instant and
            global_after.revision == global_captured.revision + 1 and
            list(target.getVelocity()) == [0.] * 6,
            'global reset did not zero physics and advance the revision once')
    require(not effect(target_id, c.byref(global_captured), velocity) and
            list(target.getVelocity()) == [0.] * 6,
            'stale token survived global simulation resetPhysics')

    # A Robot controller restart must revoke the former session's effect token.
    restart_before = token_now()
    target.restartController()
    require(robot.step(8) != -1, 'could not complete native controller restart')
    restart_after = token_now()
    require(bytes(restart_before.incarnation) == bytes(restart_after.incarnation) and
            restart_after.revision == restart_before.revision + 1,
            'Robot controller restart did not advance native scene revision once')
    velocity_before_restart_refusal = list(target.getVelocity())
    require(not effect(target_id, c.byref(restart_before), velocity) and
            list(target.getVelocity()) == velocity_before_restart_refusal,
            'stale controller-session token applied native velocity')

    Path(os.environ['WEEBEE_FRAME_RESULT']).write_text(json.dumps({
        'time_ms': round(1000 * instant), 'original_collider_x': original[0], 'moved_collider_x': shifted[0],
        'captured_revision': captured.revision, 'moved_revision': moved.revision,
        'restored_revision': restored.revision, 'applied_revision': applied.revision,
        'reset_revision': reset.revision, 'added_revision': added.revision, 'removed_revision': removed.revision,
        'before_and_after_child_count': count, 'stale_effect_refused': True, 'fresh_effect_applied_once': True,
        'controller_restart': {'before_revision': restart_before.revision,
                               'after_revision': restart_after.revision, 'stale_effect_refused': True},
        'mf_collision_triangle': {
            'time_ms': frame.time_ms, 'revisions': [mf_captured.revision, mf_inserted.revision, mf_removed.revision],
            'restored_points': original_points, 'inserted_point': inserted_point, 'stale_effect_refused': True,
        },
        'global_physics_reset': {
            'captured_revision': global_captured.revision, 'reset_revision': global_after.revision,
            'same_simulated_instant': True, 'zero_velocity': True, 'stale_effect_refused': True,
        },
    }, indent=2) + '\n', encoding='utf-8')
    robot.simulationQuit(0)


def main():
    from bench import distribution, fingerprint, run_external

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tcp-port', type=int, default=1335)
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args()
    output, home = args.output.resolve(), args.patched.resolve()
    identity = fingerprint(home)
    worlds = output / 'worlds'
    output.mkdir(parents=True, exist_ok=False)
    worlds.mkdir()
    source = (FRAME / 'observation.wbt').read_text(encoding='utf-8')
    source = source.replace('\nSolid {', '\nDEF COLLIDER Solid {', 1).replace('controller "observe"', 'controller "<extern>"')
    source += '''
DEF MESH_COLLIDER Solid {
  translation 20 0 0
  boundingObject IndexedFaceSet {
    coord Coordinate {
      point [ 0 0 0, 1 0 0, 0 1 0 ]
    }
    coordIndex [ 0 1 2 -1 ]
  }
}
'''
    world = worlds / 'revision.wbt'
    world.write_text(source, encoding='utf-8')
    trace = output / 'revision.json'
    env = {k: v for k, v in os.environ.items() if k.lower() not in {'http_proxy', 'https_proxy', 'all_proxy'}}
    env.update(WEEBEE_REVISION_OBSERVE='1', WEEBEE_FRAME_RESULT=str(trace))
    executable, _, _ = distribution(home)
    command = [str(executable), '--batch', '--stdout', '--stderr', '--mode=fast', '--no-rendering',
               '--extern-urls', f'--port={args.tcp_port}', str(world)]
    with (output / 'webots.log').open('wb') as log:
        run_external(command, home, output, Path(__file__).resolve(), env,
                     SimpleNamespace(tcp_port=args.tcp_port, timeout=args.timeout), log)
    result = json.loads(trace.read_text(encoding='utf-8'))
    result['engine_fingerprints'] = identity
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    if os.environ.get('WEEBEE_REVISION_OBSERVE') == '1':
        observe()
    else:
        main()
