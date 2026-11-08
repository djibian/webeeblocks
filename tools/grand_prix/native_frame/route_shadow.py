"""Check the route-5 flight/RESET witness with the experimental frame in shadow."""
import argparse
from contextlib import ExitStack
import ctypes
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def observe():
    from controller import Node, Supervisor
    from probe import Frame, bind_frame_api, compact_observation, official_observation, require

    # The existing witness checks controller provenance. This isolated TCP
    # fixture aliases only the two deliberately externalized controller fields.
    get_field = Node.getField

    def fixture_field(node, name):
        field = get_field(node, name)
        if name == 'controller' and field is not None:
            expected = None
            if node.getTypeName() == 'Crazyflie' and get_field(node, 'name').getSFString() == 'Crazyflie WebeeBlocks':
                expected = 'grand_prix_route_flight'
            elif node.getDef() == 'GP_ROUTE_EVALUATOR':
                expected = 'grand_prix_route_evaluator'
            if expected and field.getSFString() == '<extern>':
                field.getSFString = lambda: expected
        return field

    Node.getField = fixture_field
    comparisons = 0
    mismatches = []
    invalidated = []
    lane = os.environ['WEEBEE_ROUTE_FRAME']
    if lane != 'baseline':
        request, read = bind_frame_api()
        frame = Frame()
        current_revision = None
        if lane == 'revision-shadow':
            from controller.wb import wb
            from tools.grand_prix.native_revision.check import Token

            captured = Token()
            live = Token()
            read_with_revision = wb.wb_supervisor_physics_frame_read_with_revision
            read_with_revision.argtypes = [ctypes.POINTER(Frame), ctypes.POINTER(Token)]
            read_with_revision.restype = ctypes.c_bool
            current_revision = wb.wb_supervisor_get_scene_revision
            current_revision.argtypes = [ctypes.POINTER(Token)]
            current_revision.restype = ctypes.c_bool
        target = None
        supervisor_id = None
        original_step = Supervisor.step

        def shadow_step(robot, duration):
            nonlocal target, supervisor_id, comparisons
            if target is None:
                children = robot.getRoot().getField('children')
                roots = [children.getMFNode(i) for i in range(children.getCount())]
                target, = [node for node in roots if node and node.getTypeName() == 'Crazyflie']
                supervisor_id = robot.getSelf().getId()
            require(duration == 8 and request(target.getId()), 'could not queue route frame')
            status = original_step(robot, duration)
            if status != -1:
                if current_revision:
                    require(read_with_revision(ctypes.byref(frame), ctypes.byref(captured)),
                            'missing route frame and captured revision')
                else:
                    require(read(ctypes.byref(frame)), 'missing route frame')
                actual = compact_observation(frame, robot, target.getId(), supervisor_id)
                official = official_observation(target)
                if current_revision:
                    require(current_revision(ctypes.byref(live)), 'missing live revision after legacy reads')
                    same_world = bytes(captured.incarnation) == bytes(live.incarnation)
                    if not same_world or captured.revision != live.revision:
                        invalidated.append({
                            'time_ms': round(robot.getTime() * 1000),
                            'captured_revision': captured.revision, 'live_revision': live.revision,
                            'same_world': same_world, 'observations_differ': actual != official,
                        })
                        return status
                comparisons += 1
                if actual != official:
                    names = ('position', 'orientation', 'velocity', 'contacts')
                    mismatches.append({
                        'time_ms': round(robot.getTime() * 1000),
                        **{key: [left, right] for key, left, right in zip(names, actual, official) if left != right},
                    })
            return status

        Supervisor.step = shadow_step
    try:
        runpy.run_path(str(ROOT / 'tools/ci/fixtures/gp_route_evaluator_probe.py'), run_name='__main__')
    finally:
        path = Path(os.environ['GP_ROUTE_EVALUATOR_OUT']).with_name('frame-parity.json')
        path.write_text(json.dumps({'comparisons': comparisons, 'mismatches': mismatches,
                                    'invalidated': invalidated}, indent=2) + '\n',
                        encoding='utf-8')


def start(stack, name, command, directory, env):
    log = stack.enter_context((directory / (name + '.log')).open('wb'))
    process = subprocess.Popen(command, env=env, cwd=directory, stdout=log, stderr=log)

    def stop():
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    stack.callback(stop)
    return process


def run(home, output, port, lane, timeout):
    from bench import fingerprint
    from tools.ci.run_grand_prix_route_evaluator_native import check_native
    from tools.grand_prix.course_active_world_v2 import active_course_world
    from tools.grand_prix.launch_linux import ensure_webots_assets
    from tools.grand_prix.route_courses_v2 import reference_course

    identity = fingerprint(home)
    ensure_webots_assets(home)
    course = reference_course(5)
    world = active_course_world(course).replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://')
    for name in ('grand_prix_route_flight', 'grand_prix_route_evaluator'):
        marker = f'controller "{name}"'
        if world.count(marker) != 1:
            raise ValueError(f'wrong fixture controller {name}')
        world = world.replace(marker, 'controller "<extern>"')
    (output / 'worlds').mkdir(parents=True)
    (output / 'plugins').mkdir()
    (output / 'plugins/robot_windows').symlink_to(ROOT / 'plugins/robot_windows', target_is_directory=True)
    scene = output / 'worlds/route.wbt'
    scene.write_text(world, encoding='utf-8')
    witness = output / 'native.json'
    pilot = ROOT / 'controllers/grand_prix_route_publisher_probe/grand_prix_route_publisher_probe'
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in {'http_proxy', 'https_proxy', 'all_proxy', 'webots_controller_url'}}
    env.update(
        WEBOTS_HOME=str(home), WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
        GP_ROUTE_EVALUATOR_SOURCE=str(ROOT), GP_ROUTE_EVALUATOR_OUT=str(witness),
        GP_ROUTE_EVALUATOR_MODE='flight-reset', GP_ROUTE_PILOT_COURSE_ID=course.identifier,
        GP_ROUTE_PILOT_ACK_OUT=str(output / 'pilot-acks.json'),
        GP_ROUTE_PILOT_NATIVE_READY_OUT=str(output / 'pilot-native-ready.txt'),
        WEEBEE_ROUTE_FRAME=lane,
    )
    controller = [str(home / 'webots-controller'), '--protocol=tcp', '--ip-address=127.0.0.1', f'--port={port}']
    with ExitStack() as stack:
        engine = start(stack, 'webots', [str(home / 'webots'), '--batch', '--stdout', '--stderr',
                       '--mode=fast', '--no-rendering', '--extern-urls', f'--port={port}', str(scene)], output, env)
        deadline = time.monotonic() + timeout
        log = output / 'webots.log'
        while log.read_text(encoding='utf-8', errors='replace').count('Waiting for local or remote connection') < 2:
            if engine.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError(f'route engine startup failed: {log}')
            time.sleep(.05)
        pilot_process = start(stack, 'pilot', [
            *controller, '--robot-name=Crazyflie WebeeBlocks', str(pilot), course.identifier], output, env)
        evaluator = start(stack, 'evaluator', [
            *controller, '--robot-name=Évaluateur Grand Prix variable', str(HERE / 'route_shadow.py')], output,
            dict(env, WEEBEE_ROUTE_OBSERVER='1'))
        while engine.poll() is None:
            if time.monotonic() >= deadline or any(p.poll() not in (None, 0) for p in (pilot_process, evaluator)):
                raise RuntimeError(f'route witness failed: {output}')
            time.sleep(.05)
        if engine.returncode != 0 or evaluator.wait(timeout=5) != 0:
            raise RuntimeError(f'route process failure: {output}')
    result = json.loads(witness.read_text(encoding='utf-8'))
    check_native(result)
    parity = json.loads((output / 'frame-parity.json').read_text(encoding='utf-8'))
    return {'engine': identity, 'witness': result, 'parity': parity}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official', type=Path, required=True)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=1330)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--with-revision', action='store_true',
                        help='classify frames invalidated by native revisions without transferring authority')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False, parents=True)
    stock = run(args.official.resolve(), output / 'stock', args.port, 'baseline', args.timeout)
    lane = 'revision-shadow' if args.with_revision else 'shadow'
    shadow = run(args.patched.resolve(), output / 'shadow', args.port + 1, lane, args.timeout)
    summary = {'stock': stock, 'shadow': shadow}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    if stock['witness']['acks'] != shadow['witness']['acks'] or not shadow['parity']['comparisons']:
        raise SystemExit(f'Incomplete or divergent native route witness: {output}')
    if shadow['parity']['mismatches']:
        raise SystemExit(f'Route parity refuted: {output / "summary.json"}')


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    if os.environ.get('WEEBEE_ROUTE_OBSERVER') == '1':
        observe()
    else:
        main()
