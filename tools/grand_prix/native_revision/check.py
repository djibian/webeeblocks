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
    Path(os.environ['WEEBEE_FRAME_RESULT']).write_text(json.dumps({
        'time_ms': frame.time_ms, 'original_collider_x': original[0], 'moved_collider_x': shifted[0],
        'captured_revision': captured.revision, 'moved_revision': moved.revision,
        'restored_revision': restored.revision, 'applied_revision': applied.revision,
        'reset_revision': reset.revision, 'added_revision': added.revision, 'removed_revision': removed.revision,
        'before_and_after_child_count': count, 'stale_effect_refused': True, 'fresh_effect_applied_once': True,
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
