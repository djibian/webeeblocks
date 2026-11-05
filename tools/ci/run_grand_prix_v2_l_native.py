#!/usr/bin/env python3
"""Reproducible native L-corner rays in the complete inert CoursePlan scene.

Manual R2025a runner for #825. It attests the full L/open-H/closed-H
collider inventory, but only *measures L rays*. H ray behavior, contact,
mission admission, autonomous flight and pupil GUI need separate evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.course_static_world_v2 import static_course_world

DEFAULT_INDICES = (0, 5, 6, 11)  # GG/GD/DG/DD; short, mixed and 3 m legs.
OUT = ROOT / 'ci-artifacts/grand-prix-v2-l-native'


def probe_scene(index):
    course = reference_course(index)
    # Consume the *same full scene* as the H probe and future evaluator.
    # Do not construct a second L-only world or omit hidden H collisions.
    source = static_course_world(course)
    old = 'controller "<none>"'
    if (source.count(old) != 1 or source.count('window "<none>"') != 1 or
            source.count('DEF GP_V2_L_') != 4 or
            source.count('DEF GP_V2_H_') != 3 * course.count or
            source.count('DEF GP_V2_FINAL_') != 4 or
            source.count('boundingObject Box { size ') != 8 + 3 * course.count or
            'GP_ROUTE_EVALUATOR' in source or 'controllerArgs' in source or
            'controller "grand_prix_u_flight"' in source or
            'controller "grand_prix_route_flight"' in source):
        raise RuntimeError('full static course contract changed; refusing native L probe')
    source = source.replace(old, 'controller "grand_prix_v2_l_probe"', 1)
    return source


def check_native(result, course):
    if (type(result) is not dict or
            result.get('claim') != 'L-only-native-teleport-perception-not-flight' or
            result.get('configuration') != course.identifier or
            result.get('webots') != 'R2025a' or
            result.get('timestep_ms') != 8):
        raise RuntimeError('missing/wrong native L proof identity')
    samples = result.get('samples')
    if type(samples) is not list or len(samples) != 4:
        raise RuntimeError('incomplete L sensor evidence')
    if [x.get('box') for x in samples] != [
            f'GP_V2_L_{i}_{part}' for i in range(2) for part in range(2)]:
        raise RuntimeError('wrong L collider witness sequence')
    for sample in samples:
        for distance in ('near', 'far'):
            readings = sample.get(distance)
            if (type(readings) is not dict or
                    set(readings) != {'front', 'back', 'left', 'right'} or
                    any(type(value) not in (int, float) or
                        not 0 <= value <= 2.001 for value in readings.values())):
                raise RuntimeError('missing horizontal native measurements')
        if (not .07 < sample['near']['front'] < .50 or
                not sample['far']['front'] > sample['near']['front'] + .20 or
                not sample['far']['front'] < 1.30):
            raise RuntimeError('native L near/far discrimination failed')


def native_run(home, indexes):
    # Each invocation owns its output directory; never read, modify or delete
    # another invocation's proof or legacy top-level summary.
    OUT.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix='invocation-', dir=OUT)).resolve()
    summary_file = run_dir / 'summary.json'
    print('GP_V2_L_NATIVE_RUN_DIR ' + str(run_dir), flush=True)
    version_file = home / 'resources/version.txt'
    if not version_file.is_file() or version_file.read_text().strip() != 'R2025a':
        raise RuntimeError('Webots R2025a required; no fallback')
    executable = home / 'webots'
    if not executable.is_file():
        raise RuntimeError('Webots native executable missing')
    outcomes = []
    for position, index in enumerate(indexes):
        course = reference_course(index)
        case_dir = run_dir / f'{position:02d}-{course.identifier}'
        case_dir.mkdir()
        source = probe_scene(index)
        digest = hashlib.sha256(source.encode()).hexdigest()
        # World must sit directly under the project's worlds/ directory so
        # Webots resolves the existing controllers/ and PROTO resources.
        with tempfile.NamedTemporaryFile(
                mode='w', prefix='ci_gp_v2_l_', suffix='.wbt',
                dir=ROOT / 'worlds', encoding='utf-8', delete=False) as target:
            target.write(source)
            world = Path(target.name)
        native_file = case_dir / 'native.json'
        log_file = case_dir / 'native.log'
        env = os.environ.copy()
        env.update(WEBOTS_HOME=str(home), GP_V2_L_NATIVE_INDEX=str(index),
                   GP_V2_L_NATIVE_OUT=str(native_file),
                   LIBGL_ALWAYS_SOFTWARE='true',
                   WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
        proc = None
        try:
            with log_file.open('w') as log:
                proc = subprocess.Popen(
                    [str(executable), '--stdout', '--stderr', '--batch',
                     '--mode=fast', '--minimize', str(world)],
                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                status = proc.wait(timeout=120)
            content = log_file.read_text(errors='replace')
            if status != 0 or 'Traceback (most recent call last)' in content or any(
                    line.startswith('ERROR:') for line in content.splitlines()):
                raise RuntimeError('native Webots failure: ' + str(log_file))
            if not native_file.is_file():
                raise RuntimeError('no native output for ' + course.identifier)
            result = json.loads(native_file.read_text())
            check_native(result, course)
            witness = ['GP_V2_L_NATIVE ' + json.dumps(result, sort_keys=True)]
            # Require the native log and durable JSON to describe one and the
            # same sensor readings, not separate synthetic/static witnesses.
            if not any(line in content.splitlines() for line in witness):
                raise RuntimeError('native log and evidence file disagree')
            outcomes.append(dict(configuration=course.identifier,
                                 generated_world_sha256=digest,
                                 evidence_file=str(native_file.relative_to(run_dir)),
                                 evidence_sha256=hashlib.sha256(
                                     native_file.read_bytes()).hexdigest()))
            print('PASS L-only native perception ' + course.identifier, flush=True)
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()
            world.unlink(missing_ok=True)
            world.with_suffix('.wbproj').unlink(missing_ok=True)
    summary = dict(claim='L-only-native-teleport-perception-not-flight',
                   invocation=run_dir.name, webots_version='R2025a', results=outcomes)
    # Publish a complete validated matrix atomically, never a partial success.
    with tempfile.NamedTemporaryFile(
            mode='w', prefix='.summary-', suffix='.tmp', dir=run_dir,
            encoding='utf-8', delete=False) as target:
        pending = Path(target.name)
        target.write(json.dumps(summary, indent=2) + '\n')
    try:
        os.replace(pending, summary_file)
    finally:
        pending.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', action='store_true',
                        help='run actual R2025a sensors; no synthetic pass')
    parser.add_argument('--index', action='append', type=int, default=[],
                        help='reference_course index 0..11; may repeat')
    parser.add_argument('--all-12', action='store_true')
    args = parser.parse_args(argv)
    if not args.native:
        parser.error('native measurement is mandatory; no host-only PASS')
    if args.all_12 and args.index:
        parser.error('--all-12 and --index are mutually exclusive')
    indexes = tuple(range(12)) if args.all_12 else (
        tuple(args.index) if args.index else DEFAULT_INDICES)
    for index in indexes:
        reference_course(index)  # fail closed before spawning any process
    home = os.environ.get('WEBOTS_HOME')
    if not home:
        parser.error('WEBOTS_HOME must point to Webots R2025a')
    native_run(Path(home), indexes)


if __name__ == '__main__':
    main()
