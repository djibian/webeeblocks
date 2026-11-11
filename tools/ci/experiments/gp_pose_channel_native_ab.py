"""Native R2025a nonblocking pose IPC stress, diagnostic-only.

Same native pilot, evaluator, safety witness and unrendered Webots for 12
trials: baseline, publication with no reader, fast reader, reader sleeping
100 ms then stopped. All Controller and oracle code is unchanged. The
diagnostic controller FILE is substituted in the temporary test project only.
No additional Webots controller, network listener, authority or renderer.
"""
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from unittest.mock import patch

from tools.ci import run_grand_prix_route_evaluator_native as native
from tools.ci.experiments.pose_mailbox_v1 import SIZE, read_once

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'ci-artifacts/grand-prix-pose-native-ab'
ORDER = (('baseline', 1), ('publish_only', 1), ('consumer_fast', 1),
         ('consumer_stall', 1), ('consumer_stall', 2), ('consumer_fast', 2),
         ('publish_only', 2), ('baseline', 2), ('publish_only', 3),
         ('baseline', 3), ('consumer_stall', 3), ('consumer_fast', 3))
PHASES = {'first_flight': (4008, 7000), 'second_flight': (14008, 17000)}


def quantile(data, p):
    data = sorted(data)
    return data[min(len(data)-1, math.ceil(len(data)*p)-1)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_trial(home, env, kind, repetition):
    directory = OUT / f'{repetition}-{kind}'
    if directory.exists():
        raise RuntimeError('refuse overwrite of native evidence')
    directory.mkdir(parents=True)
    native.OUT = directory
    original_fixture = ROOT / 'tools/ci/fixtures/gp_route_evaluator_probe.py'
    wrapper = ROOT / 'tools/ci/experiments/gp_pose_probe_controller.py'
    copyfile_orig = native.shutil.copyfile
    popen_orig = subprocess.Popen
    channel = directory / 'latest-pose.bin'
    fd = os.open(channel, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    os.ftruncate(fd, SIZE)
    os.close(fd)
    report = {'kind': kind, 'repetition': repetition, 'status': 'UNPROVEN'}
    env = dict(env, GP_POSE_PROBE_OUT=str((directory / 'pose-observations.json').resolve()))
    if kind != 'baseline':
        env['GP_POSE_MAILBOX_PATH'] = str(channel.resolve())
    else:
        env.pop('GP_POSE_MAILBOX_PATH', None)

    def controlled_copyfile(src, dst, *args, **kwargs):
        # Substitute ONLY the temporary CI evaluator fixture. The production
        # evaluator, pilot and all other project files are left unmodified.
        if (Path(src) == original_fixture and
                Path(dst).name == 'grand_prix_route_evaluator.py'):
            return copyfile_orig(wrapper, dst, *args, **kwargs)
        return copyfile_orig(src, dst, *args, **kwargs)

    def controlled_popen(command, *args, **kwargs):
        if (not isinstance(command, list) or
                Path(command[0]) != home / 'webots' or
                '--mode=fast' not in command or
                not command[-1].endswith('.wbt')):
            raise RuntimeError('unexpected native process or physical mode')
        command = command[:-1] + ['--no-rendering', command[-1]]
        return popen_orig(command, *args, **kwargs)

    consumer = None
    consumer_log = None
    try:
        if kind in ('consumer_fast', 'consumer_stall'):
            consumer_log = (directory / 'consumer.stdout.log').open('w')
            consumer = popen_orig([sys.executable, '-u', '-m',
                    'tools.ci.experiments.gp_pose_consumer', str(channel.resolve()),
                    str((directory / 'consumer.samples.jsonl').resolve()),
                    '--mode', 'fast' if kind == 'consumer_fast' else 'stall'],
                    cwd=ROOT, env=env, stdout=consumer_log,
                    stderr=subprocess.STDOUT)
        with patch.object(native.shutil, 'copyfile', side_effect=controlled_copyfile), \
             patch.object(native.subprocess, 'Popen', side_effect=controlled_popen):
            native.run_case(home, env, 'flight-reset')
        cases = list(directory.glob('flight-reset-invocation-*'))
        if len(cases) != 1:
            raise RuntimeError('expected exactly one native witness')
        case = cases[0]
        witness = json.loads((case / 'native.json').read_text())
        native.check_native(witness)
        rows = [json.loads(line) for line in (case / 'native.trace').read_text().splitlines()]
        observed = json.loads((directory / 'pose-observations.json').read_text())
        if not rows or len(observed['samples']) < 1600:
            raise RuntimeError('native pose diagnostics incomplete')
        with channel.open('rb') as f:
            with mmap.mmap(f.fileno(), SIZE, access=mmap.ACCESS_READ) as mapped:
                latest = read_once(mapped)
        stats = observed['publisher']
        if kind == 'baseline':
            if stats is not None or latest is not None:
                raise RuntimeError('unmodified baseline inadvertently published')
        elif (not stats or stats['publications'] < 1600 or
              stats['epoch_changes'] < 2 or not latest or not latest['valid']):
            raise RuntimeError('publisher or post-RESET incarnation unavailable')
        report.update(status='NATIVE_WITNESS_PASS', world_sha256=digest(case / 'world.wbt'),
                      source_witness=witness, trace_sha256=digest(case / 'native.trace'),
                      observation_sha256=digest(directory / 'pose-observations.json'),
                      native_steps=len(rows), publisher=stats, latest=latest, sections={})
        for label, (begin, end) in PHASES.items():
            selected = [r for r in rows if begin <= r['time_ms'] <= end]
            if (len(selected) != (end - begin) // 8 + 1 or
                    any(r['phase'] != 'active' for r in selected)):
                raise RuntimeError('missing common active native flight ' + label)
            steps = [r['step_wall_s']*1000 for r in selected]
            ticks = [r['tick_wall_s']*1000 for r in selected]
            elapsed = (selected[-1]['wall_elapsed_s'] - selected[0]['wall_elapsed_s'] +
                       selected[0]['step_wall_s'] + selected[0]['tick_wall_s'])
            report['sections'][label] = dict(
                count=len(selected), speed_x=round(len(selected)*.008/elapsed, 6),
                avg_cycle_ms=round(1000*elapsed/len(selected), 6),
                step_mean_ms=round(statistics.mean(steps), 6),
                tick_mean_ms=round(statistics.mean(ticks), 6),
                cycle_p99_ms=round(quantile([s+t for s,t in zip(steps,ticks)], .99), 6),
                tick_cpu_mean_ms=round(statistics.mean(
                    [r['tick_cpu_s']*1000 for r in selected]), 6))
        return report, observed['samples']
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        # Never wait for a consumer until AFTER the entire Webots trial exits.
        if consumer and consumer.poll() is None:
            consumer.terminate()
            try:
                consumer.wait(timeout=4)
            except subprocess.TimeoutExpired:
                consumer.kill()
                consumer.wait(timeout=5)
        if consumer_log:
            consumer_log.close()
        (directory / 'trial.json').write_text(
            json.dumps(report, indent=2, sort_keys=True) + '\n')


def compare(reports, samples):
    if len({r['world_sha256'] for r in reports}) != 1:
        raise RuntimeError('different native world between IPC arms')
    comparisons = {}
    for phase, (begin, end) in PHASES.items():
        baseline = next((ss for rr, ss in zip(reports, samples)
                         if rr['kind'] == 'baseline' and rr['repetition'] == 1), None)
        if baseline is None:
            raise RuntimeError('native baseline unavailable')
        anchor = {r['time_ms']: r for r in baseline if begin <= r['time_ms'] <= end}
        if len(anchor) != (end - begin)//8 + 1:
            raise RuntimeError('native reference phase incomplete')
        discrepancy = []
        max_delta = 0.
        for trial, series in zip(reports, samples):
            selected = {r['time_ms']: r for r in series if begin <= r['time_ms'] <= end}
            if selected.keys() != anchor.keys():
                raise RuntimeError('dropped native observations in ' + phase)
            for tick, original in anchor.items():
                record = selected[tick]
                for key in ('attempt', 'phase', 'error', 'contact_count'):
                    if record[key] != original[key]:
                        discrepancy.append((trial['kind'],trial['repetition'],tick,key))
                for key in ('position','orientation','velocity','ranges_m'):
                    a,b = record[key],original[key]
                    if a is None or b is None or len(a) != len(b):
                        raise RuntimeError('missing native field ' + key)
                    max_delta = max(max_delta, max(abs(x-y) for x,y in zip(a,b)))
        comparisons[phase] = dict(checked_steps=len(anchor),
            max_numeric_delta=max_delta, identity_discrepancies=discrepancy[:10],
            equivalent=(not discrepancy and max_delta <= 1e-6))
    medians = {}
    for kind in ('baseline','publish_only','consumer_fast','consumer_stall'):
        rows=[r for r in reports if r['kind'] == kind]
        medians[kind] = {phase:dict(
            speed_x_median=statistics.median(r['sections'][phase]['speed_x'] for r in rows),
            cycle_ms_median=statistics.median(r['sections'][phase]['avg_cycle_ms'] for r in rows))
            for phase in PHASES}
    return dict(phase_comparisons=comparisons, summary=medians,
                equivalent=all(x['equivalent'] for x in comparisons.values()))


def main():
    home = Path(os.environ['WEBOTS_HOME']).resolve()
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('exact Webots R2025a required')
    if not os.environ.get('DISPLAY'):
        raise RuntimeError('Xvfb display required')
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true',
        LP_NUM_THREADS='2', WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    for cmd in (
        [sys.executable,'-m','tools.grand_prix.prepare_route_runtime'],
        ['make','-C',str(ROOT/'controllers/grand_prix_route_flight'),'release'],
        ['make','-C',str(ROOT/'controllers/grand_prix_route_publisher_probe'),'release']):
        subprocess.run(cmd, cwd=ROOT, env=env, check=True, timeout=180)
    reports,samples=[],[]
    for kind,repetition in ORDER:
        print('GP_POSE_IPC_START',repetition,kind,flush=True)
        report,observations=run_trial(home,env,kind,repetition)
        reports.append(report)
        samples.append(observations)
    result=compare(reports,samples)
    result.update(schema='gp-pose-ipc-native-diagnostic-v1',
        status='MEASURED_ONLY', trial_count=len(reports),
        world_sha256=reports[0]['world_sha256'],
        webots_sha256=digest(home / 'bin/webots-bin'),
        host=dict(os=platform.platform(),cpu=platform.processor()),
        trials=reports,
        provenance='native R2025a historical evaluator, temporary fixture only',
        limitation='No 3D display, Blockly browser or Windows; 3-second active phases; CPU contention possible')
    (OUT / 'summary.json').write_text(
        json.dumps(result,indent=2,sort_keys=True) + '\n')
    print('GP_POSE_IPC_RESULT',json.dumps(dict(status=result['status'],
          equivalent=result['equivalent'],summary=result['summary']),
          sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
