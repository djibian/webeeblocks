"""Draft-only native Webots + REAL passive WebGL A/B experiment.

Requires R2025a, Xvfb (or an actual desktop), Playwright and Chromium.
Reuses the existing historical evaluator/pilot and IPC run_trial unchanged.
Do not mistake WebGL draw submissions under Xvfb for presented monitor FPS.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import patch

from tools.ci.experiments import gp_pose_channel_native_ab as ipc
from tools.ci.experiments.gp_pose_wall_cycle_metrics import measure_wall_cycles

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'ci-artifacts/grand-prix-pose-3d-live-ab'
ARMS = ('publish_only', 'viewer_fast', 'viewer_slow', 'viewer_stopped')


def _cpu_total():
    """Include browser descendants, which are subprocesses of this probe."""
    try:
        import psutil
        p = psutil.Process()
        children = [p] + p.children(recursive=True)
        return sum(c.cpu_times().user + c.cpu_times().system for c in children if c.is_running())
    except Exception:
        # CPU telemetry is optional and must not break the native safety witness.
        return None


def _require_reader_proof(arm, closed, delayed_gets, stopped_at_ms=None):
    """A browser draw alone cannot prove slow/stopped-reader interference."""
    if arm == 'viewer_stopped':
        if not closed:
            raise RuntimeError('viewer_stopped did not actually close after an active native pose')
        # If it closes after the measured active intervals, unchanged traces
        # do not show that Webots progressed without the graphical consumer.
        if (type(stopped_at_ms) is not int or
                not 4008 <= stopped_at_ms <= 7000 or stopped_at_ms % 8):
            raise RuntimeError('viewer_stopped lacks a first-active-flight close timestamp')
    if arm == 'viewer_slow' and delayed_gets < 5:
        raise RuntimeError('viewer_slow did not exercise five delayed real pose GETs')


def _require_live_stop_pose(displayed, publisher):
    """Verify a *current* independent mailbox read before closing the reader.

    A renderer frozen on a 5000-ms pose may still draw when Webots has
    already completed both measurement windows. Its displayed timestamp
    cannot by itself establish when the reader was actually stopped.
    """
    if (type(displayed) is not dict or type(publisher) is not dict or
            displayed.get('poseValid') is not True or
            publisher.get('valid') is not True or
            type(displayed.get('poseSeq')) is not int or
            type(publisher.get('sequence')) is not int or
            publisher['sequence'] < displayed['poseSeq'] or
            type(displayed.get('poseTimeMs')) is not int or
            type(publisher.get('time_ms')) is not int or
            displayed.get('incarnation') != publisher.get('incarnation') or
            not 4008 <= displayed['poseTimeMs'] <= publisher['time_ms'] <= 6500 or
            publisher['time_ms'] % 8 or displayed['poseTimeMs'] % 8 or
            publisher['time_ms'] - displayed['poseTimeMs'] > 500):
        raise RuntimeError('stopped-reader closure is not within fresh first-flight native publisher data')
    return publisher['time_ms']


def _finish_browser_report(report, screenshot, close):
    """Only publish success after every browser evidence operation succeeds."""
    if screenshot is not None:
        screenshot()
    close()
    report['status'] = 'WEBGL_DRAW_MEASURED_ONLY'


def _require_browser_result(report):
    """Reject success labels contradicted by a late screenshot/close failure."""
    if (type(report) is not dict or
            report.get('status') != 'WEBGL_DRAW_MEASURED_ONLY' or
            report.get('error')):
        raise RuntimeError('browser did not produce valid real WebGL evidence')


def _browser_child(args):
    """Separate process avoids interfering with native.subprocess.Popen patch."""
    report = dict(kind=args.arm, status='UNPROVEN', samples=[])
    ready, stop, output = map(Path, (args.ready, args.stop, args.output))
    start = time.monotonic()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            launch = dict(headless=False, args=[
                '--use-gl=angle', '--use-angle=swiftshader',
                '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
            if os.environ.get('GP_VIEWER_CHROMIUM'):
                launch['executable_path'] = os.environ['GP_VIEWER_CHROMIUM']
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page(viewport=dict(width=960, height=620),
                                    device_scale_factor=1)
            delayed_gets = 0
            if args.arm == 'viewer_slow':
                # Delay the *real* localhost GET before forwarding, no fake poses.
                def slow_pose(route):
                    nonlocal delayed_gets
                    delayed_gets += 1
                    time.sleep(.750)
                    route.continue_()
                page.route('**/pose', slow_pose)
            page.goto(args.url, wait_until='domcontentloaded', timeout=15000)
            page.wait_for_function('window.viewerMetrics && '
                'viewerMetrics.webgl && viewerMetrics.staticBoxes > 0 && '
                'viewerMetrics.frames >= 3', timeout=15000)
            report['renderer'] = page.evaluate('''() => {
                const gl=document.getElementById('view').getContext('webgl');
                const ext=gl.getExtension('WEBGL_debug_renderer_info');
                return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) :
                    gl.getParameter(gl.RENDERER);
            }''')
            if not page.evaluate('window.viewerMetrics.staticBoxes === 21'):
                raise RuntimeError('not the expected native 21-Box witness')
            start_cpu = _cpu_total()
            first = time.monotonic()
            # Atomic marker: the parent must never read a partial JSON file.
            ready_tmp = ready.with_name(ready.name + '.tmp')
            ready_tmp.write_text(json.dumps(dict(status='REAL_WEBGL_READY',
                renderer=report['renderer'], box_count=21)) + '\n')
            os.replace(ready_tmp, ready)
            page_stopped = False
            stopped_at_ms = None
            while not stop.exists() and time.monotonic() - first < 120:
                elapsed = time.monotonic() - first
                if args.arm == 'viewer_stopped' and elapsed >= 5 and not page_stopped:
                    # The displayed pose can be stale after a blocked browser
                    # fetch. Cross-check the independent current mmap publisher
                    # via the read-only original /pose endpoint before closing.
                    displayed = page.evaluate("""() => ({
                        poseTimeMs: viewerMetrics.poseTimeMs,
                        poseSeq: viewerMetrics.poseSeq,
                        poseValid: viewerMetrics.poseValid,
                        incarnation: viewerMetrics.incarnation
                    })""")
                    if displayed['poseValid'] and displayed['poseTimeMs'] >= 4008:
                        import urllib.request
                        with urllib.request.urlopen(args.url.rstrip('/') + '/pose',
                                                    timeout=2) as response:
                            publisher = json.load(response)
                        stopped_at_ms = _require_live_stop_pose(displayed, publisher)
                        report['viewer_closed_display_pose_ms'] = displayed['poseTimeMs']
                        report['viewer_closed_native_pose_ms'] = stopped_at_ms
                        report['viewer_closed_native_sequence'] = publisher['sequence']
                        report['viewer_closed_wall_s'] = elapsed
                        page.close()
                        page_stopped = True
                if not page_stopped:
                    page.wait_for_timeout(250)
                    sample = page.evaluate('''() => {
                        const m=viewerMetrics;
                        const gl=document.getElementById('view').getContext('webgl');
                        return {frames:m.frames,received:m.received,dropped:m.dropped,
                            incarnations:m.incarnations,errors:m.errors,
                            resolution:m.resolution,poseSeq:m.poseSeq,
                            poseTimeMs:m.poseTimeMs,staticBoxes:m.staticBoxes,
                            gl_error:gl.getError()};
                    }''')
                    sample['wall_s'] = round(time.monotonic() - first, 3)
                    report['samples'].append(sample)
                else:
                    time.sleep(.250)
            report['duration_s'] = round(time.monotonic() - first, 3)
            report['delayed_gets'] = delayed_gets
            _require_reader_proof(args.arm, page_stopped, delayed_gets, stopped_at_ms)
            if not stop.exists():
                raise RuntimeError('viewer exceeded 120s before native witness ended')
            end_cpu = _cpu_total()
            report['browser_cpu_seconds'] = (round(end_cpu - start_cpu, 4)
                if end_cpu is not None and start_cpu is not None else None)
            if not report['samples']:
                raise RuntimeError('browser rendered no measurable frame samples')
            last = report['samples'][-1]
            if (any(sample['gl_error'] != 0 for sample in report['samples'])
                    or last['staticBoxes'] != 21 or last['errors']):
                raise RuntimeError('browser GL, geometry or HTTP failure: ' + str(last))
            if last['received'] < 2 or not last.get('poseSeq'):
                raise RuntimeError('WebGL renderer never consumed live native poses')
            if args.arm != 'viewer_stopped' and (last['incarnations'] < 1 or
                    last['poseTimeMs'] is None or last['poseTimeMs'] < 14008):
                raise RuntimeError('WebGL did not observe the post-RESET flight')
            if not (last['resolution'] == [960, 554]):
                raise RuntimeError('browser native framebuffer unexpected: ' + str(last['resolution']))
            if len(report['samples']) >= 2:
                a, b = report['samples'][0], report['samples'][-1]
                span = b['wall_s'] - a['wall_s']
                report['draw_submissions_per_s'] = ((b['frames']-a['frames'])/span
                    if span > 0 else None)
            _finish_browser_report(
                report,
                (lambda: page.screenshot(path=str(output.with_suffix('.png'))))
                if not page_stopped else None,
                browser.close)
    except Exception as exc:
        report['status'] = 'WEBGL_FAILURE'
        report['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        report['wall_total_s'] = round(time.monotonic() - start, 3)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    _require_browser_result(report)


def _wait_ready(child, marker, seconds=25):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if marker.is_file():
            proof = json.loads(marker.read_text())
            if (type(proof) is not dict or proof.get('status') != 'REAL_WEBGL_READY'
                    or proof.get('box_count') != 21
                    or not isinstance(proof.get('renderer'), str)
                    or not proof['renderer']):
                raise RuntimeError('invalid real WebGL readiness evidence')
            return proof
        if child.poll() is not None:
            raise RuntimeError('3D browser preflight exited before WebGL readiness')
        time.sleep(.1)
    raise RuntimeError('bounded 3D browser WebGL readiness timeout')


def _native_arm(home, env, arm):
    # Reuse exact native witness, source modifications limited to the temporary
    # evaluator fixture via ipc.run_trial; no product modification or new authority.
    ipc.OUT = OUT / arm
    trial = ipc.OUT / '1-publish_only'
    if trial.exists():
        raise RuntimeError('refuse overwriting prior evidence: ' + str(trial))
    orig_popen = subprocess.Popen
    server = viewer = None
    browser_ready = trial / 'browser-ready.json'
    browser_stop = trial / 'browser-stop'
    browser_result = trial / 'browser.json'
    webots_invocations = 0
    scene_hash = None
    logs = []

    def launch(command, *a, **kw):
        nonlocal server, viewer, webots_invocations, scene_hash
        if not isinstance(command, list) or Path(command[0]) != home / 'webots':
            raise RuntimeError('unexpected subprocess in native live A/B')
        if webots_invocations:
            raise RuntimeError('unexpected extra native Webots launch')
        webots_invocations += 1
        if '--no-rendering' not in command or '--mode=fast' not in command:
            raise RuntimeError('IPC source did not request original 8 ms / no-rendering run')
        command = ['--mode=realtime' if x == '--mode=fast' else x for x in command]
        world = Path(command[-1]); scene_hash = ipc.digest(world)
        if arm != 'publish_only':
            mailbox = trial / 'latest-pose.bin'
            server_log = (trial / 'server.stdout.log').open('w')
            logs.append(server_log)
            # No additional Webots/Supervisor process. Server is read-only.
            # Port is chosen by OS and printed by original adapter.
            server = orig_popen([sys.executable, '-u', '-m',
                'tools.ci.experiments.gp_pose_3d_server', '--world', str(world),
                '--mailbox', str(mailbox), '--port', '0'], cwd=ROOT,
                env=env, stdout=server_log, stderr=subprocess.STDOUT)
            import urllib.request
            until = time.monotonic() + 10
            server_info = None
            server_log_path = trial / 'server.stdout.log'
            while time.monotonic() < until:
                if server.poll() is not None:
                    raise RuntimeError('3D server crashed before readiness')
                try:
                    server_info = json.loads(server_log_path.read_text().splitlines()[0])
                    break
                except (OSError, ValueError, IndexError):
                    time.sleep(.1)
            if not server_info or server_info.get('mode') != 'native-mailbox':
                raise RuntimeError('bounded 3D server startup failed')
            address = server_info['url'].rstrip('/')
            if not address.startswith('http://127.0.0.1:'):
                raise RuntimeError('3D listener is not loopback')
            with urllib.request.urlopen(address + '/scene', timeout=3) as response:
                scene = json.load(response)
            if scene['world_sha256'] != scene_hash or len(scene['boxes']) != 21:
                raise RuntimeError('3D scene does not match exact native world')
            browser_log = (trial / 'browser.stdout.log').open('w')
            logs.append(browser_log)
            viewer = orig_popen([sys.executable, '-u', '-m',
                'tools.ci.experiments.gp_pose_3d_native_live_ab',
                '--child-viewer', '--arm', arm, '--url', address + '/',
                '--ready', str(browser_ready), '--stop', str(browser_stop),
                '--output', str(browser_result)], cwd=ROOT, env=env,
                stdout=browser_log, stderr=subprocess.STDOUT)
            _wait_ready(viewer, browser_ready)
        return orig_popen(command, *a, **kw)

    try:
        # run_trial itself patches the launch only for the canonical temporary
        # test fixture. Here we observe the already patched real Webots launch.
        with patch.object(subprocess, 'Popen', side_effect=launch):
            report, samples = ipc.run_trial(home, env, 'publish_only', 1)
        # Read the exact native trace AFTER Webots exits, while the browser may
        # still be alive. Preserve the historical step+tick metrics unchanged.
        evidence = ipc.OUT / '1-publish_only'
        cases = list(evidence.glob('flight-reset-invocation-*'))
        if len(cases) != 1:
            raise RuntimeError('cannot identify unique native trace for wall-cycle evidence')
        trace_path = cases[0] / 'native.trace'
        if ipc.digest(trace_path) != report['trace_sha256']:
            raise RuntimeError('native trace digest changed before wall-cycle analysis')
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
        full_wall = {}
        for phase, (begin, end) in ipc.PHASES.items():
            full_wall[phase] = measure_wall_cycles(trace, begin, end)
            report['sections'][phase]['full_wall_cycle'] = full_wall[phase]
        (evidence / 'wall-cycle-metrics.json').write_text(
            json.dumps(full_wall, indent=2, sort_keys=True) + '\n')
        if webots_invocations != 1:
            raise RuntimeError('native Webots launch missing')
        return report, samples, scene_hash
    finally:
        browser_stop.touch(exist_ok=True) if trial.exists() else None
        if viewer is not None:
            try:
                viewer.wait(timeout=6)
            except subprocess.TimeoutExpired:
                viewer.kill(); viewer.wait(timeout=3)
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=4)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait(timeout=3)
        for handle in logs:
            handle.close()


def _compare(trials):
    anchor = trials['publish_only'][1]
    results = {}
    for arm, (report, rows, world_sha) in trials.items():
        if world_sha != trials['publish_only'][2]:
            raise RuntimeError('native worlds differ across arms')
        mismatches = []
        for phase, (begin, end) in ipc.PHASES.items():
            reference_rows = [r for r in anchor if begin <= r['time_ms'] <= end]
            observed_rows = [r for r in rows if begin <= r['time_ms'] <= end]
            # A dict alone conceals repeated timestamps and can yield false
            # evidence equivalence when two sensor observations share a tick.
            if len(reference_rows) != 375 or len(observed_rows) != 375:
                raise RuntimeError('native phase windows not aligned (duplicate/missing tick)')
            reference = {r['time_ms']: r for r in reference_rows}
            observed = {r['time_ms']: r for r in observed_rows}
            if (len(reference) != 375 or len(observed) != 375 or
                    reference.keys() != observed.keys()):
                raise RuntimeError('native phase windows not aligned (duplicate/missing tick)')
            for ms, old in reference.items():
                new = observed[ms]
                for k in ('attempt', 'phase', 'error', 'contact_count',
                          'position', 'orientation', 'velocity', 'ranges_m'):
                    if new[k] != old[k]:
                        mismatches.append((phase, ms, k))
        if mismatches:
            raise RuntimeError('native dynamic trace refutation: ' + str(mismatches[:5]))
        results[arm] = dict(equivalent=True, first_flight=report['sections']['first_flight'],
                            second_flight=report['sections']['second_flight'])
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--arms', nargs='+', choices=ARMS,
                        default=['publish_only', 'viewer_fast'])
    parser.add_argument('--output-root', default='ci-artifacts/grand-prix-pose-3d-live-ab',
                        help='unique relative ci-artifacts subdirectory, no overwrite')
    parser.add_argument('--child-viewer', action='store_true')
    parser.add_argument('--arm', choices=ARMS)
    for key in ('url','ready','stop','output'):
        parser.add_argument('--' + key)
    args = parser.parse_args()
    if args.child_viewer:
        if not all(getattr(args, key) for key in ('arm','url','ready','stop','output')):
            parser.error('incomplete child viewer arguments')
        return _browser_child(args)
    if not args.arms or args.arms[0] != 'publish_only' or len(set(args.arms)) != len(args.arms):
        parser.error('require publish_only first and unique paired arms')
    global OUT
    output = Path(args.output_root)
    evidence_root = (ROOT / 'ci-artifacts').resolve()
    if (output.is_absolute() or '..' in output.parts or
            (ROOT / output).resolve() == evidence_root or
            not (ROOT / output).resolve().is_relative_to(evidence_root)):
        parser.error('output-root must be a unique subdirectory inside ci-artifacts')
    OUT = (ROOT / output).resolve()
    home = Path(os.environ['WEBOTS_HOME']).resolve()
    if (home/'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('exact native Webots R2025a required')
    if not os.environ.get('DISPLAY'):
        raise RuntimeError('real Xvfb/desktop display required')
    if OUT.exists():
        raise RuntimeError('refuse overwrite of native evidence directory: ' + str(OUT))
    OUT.mkdir(parents=True)
    env = dict(os.environ, WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true',
               LP_NUM_THREADS='2', WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    for cmd in ([sys.executable, '-m', 'tools.grand_prix.prepare_route_runtime'],
                ['make', '-C', str(ROOT/'controllers/grand_prix_route_flight'), 'release'],
                ['make', '-C', str(ROOT/'controllers/grand_prix_route_publisher_probe'), 'release']):
        subprocess.run(cmd, cwd=ROOT, env=env, check=True, timeout=180)
    results = {}
    for arm in args.arms:
        print('GP967_REAL_WEBGL_NATIVE_START', arm, flush=True)
        results[arm] = _native_arm(home, env, arm)
    comparison = _compare(results)
    browser = {}
    for arm in args.arms:
        if arm != 'publish_only':
            path = OUT / arm / '1-publish_only' / 'browser.json'
            if not path.is_file():
                raise RuntimeError('native viewer metrics missing: ' + str(path))
            browser[arm] = json.loads(path.read_text())
            _require_browser_result(browser[arm])
    summary = dict(schema='gp967-live-3d-native-ab-v1', status='MEASURED_ONLY',
        source='historical native R2025a flight-reset, passive WebGL presentation',
        webots_sha256=ipc.digest(home/'bin/webots-bin'),
        host=dict(platform=platform.platform(),cpu=platform.processor()),
        phase_comparison=comparison, browser=browser,
        limitations='Linux/Xvfb/SwiftShader draws are NOT monitor-presented FPS; '
                    'not Windows, not Blockly, 2 x 3s native active flight windows; '
                    'GPU load and STOP/210s cases unproven; no authority changes')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print('GP967_REAL_WEBGL_NATIVE_RESULT',json.dumps(summary,sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
