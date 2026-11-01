#!/usr/bin/env python3
"""M1b: direct native webots-bin retirement for the two FAST progression oracles.

The browser authorizes consideration of retirement, not success. This CI-only
host owns the real Linux Webots GUI PID and reuses the #793 log/PGID mechanisms.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.ci.grand_prix_u_log_capture import NativeLogCapture, require_no_terminal_crash
from tools.ci.run_grand_prix_u_prototype import owned_process_group_state, stop_groups

COMPLETE = {
    'memory': 'MEMORY_OVERWRITE_TEST_COMPLETE',
    'autonomous': 'AUTONOMOUS_MISSION_TEST_COMPLETE',
}
SUMMARY = {
    'memory': {
        'overwritten_large': 'not-achieved', 'collision': 'not-achieved',
        'lateral_reread_small': 'not-achieved', 'wrong_final_bay': 'not-achieved',
    },
    'autonomous': {
        'integrated': ['achieved'] * 4, 'fixed_route': 'not-achieved',
        'no_memory': 'not-achieved', 'front_only': 'not-achieved',
        'incomplete': 'not-achieved',
        'downstream_inference': ['achieved', 'not-achieved'],
        'alternate': ['achieved'] * 4,
    },
}
SCRIPTS = {
    'memory': ROOT / 'tools/ci/run_progression_memory_overwrite.py',
    'autonomous': ROOT / 'tools/ci/run_progression_autonomous_mission.py',
}

def required_events(mode):
    """Use the same event inventory as the original final Python oracle."""
    tree = ast.parse(SCRIPTS[mode].read_text(encoding='utf-8'))
    matches = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and
                isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'required'):
            if not isinstance(node.value, (ast.Tuple, ast.List)):
                raise RuntimeError('unknown required-event inventory')
            matches.append([v.value for v in node.value.elts
                            if isinstance(v, ast.Constant) and isinstance(v.value, str)])
    if len(matches) != 1 or len(matches[0]) < 10 or COMPLETE[mode] not in matches[0]:
        raise RuntimeError('ambiguous required-event inventory')
    return matches[0]

def validate_browser_oracles(mode, by_name, required):
    """Pre-retirement subset of the existing final oracles; final oracle still runs."""
    if any(n.endswith('_FRESH') and by_name[n] != {'code': 'OUTCOME_UNAVAILABLE'}
           for n in required if n.endswith('_FRESH')):
        raise RuntimeError('an old outcome survived RESET before retirement')
    if mode == 'memory':
        for name in required:
            if name.endswith('_NOT_ACHIEVED'):
                allowed = ({'status': 'not-achieved'},) if name == 'MEMORY_FINAL_BAY_NOT_ACHIEVED' else (
                    {'status': 'not-achieved'},
                    {'status': 'not-achieved', 'runtime_code': 'UNSAFE_OR_TIMEOUT'})
                if by_name[name] not in allowed:
                    raise RuntimeError('memory negative oracle mismatch: ' + name)
    else:
        if by_name['AUTONOMOUS_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE'] != {
                'code': 'OUTCOME_UNAVAILABLE'}:
            raise RuntimeError('autonomous failure without evidence was accepted')
        for name in required:
            if name.endswith('_ACHIEVED') and not name.endswith('_NOT_ACHIEVED'):
                if by_name[name] != {'status': 'achieved'}:
                    raise RuntimeError('autonomous achieved oracle mismatch: ' + name)
            if name.endswith('_NOT_ACHIEVED'):
                allowed = ({'status': 'not-achieved'},
                           {'status': 'not-achieved', 'runtime_code': 'UNSAFE_OR_TIMEOUT'}) \
                    if name in ('AUTONOMOUS_FIXED_ROUTE_NOT_ACHIEVED',
                                'AUTONOMOUS_FRONT_ONLY_RIGHT_NOT_ACHIEVED') else (
                                    {'status': 'not-achieved'},)
                if by_name[name] not in allowed:
                    raise RuntimeError('autonomous negative oracle mismatch: ' + name)
        small = by_name['AUTONOMOUS_DEPARTURE_SMALL_RANGE']
        large = by_name['AUTONOMOUS_DEPARTURE_LARGE_RANGE']
        if not isinstance(small, dict) or not isinstance(large, dict):
            raise RuntimeError('missing autonomous departure observation')
        lo, hi = small.get('meters'), large.get('meters')
        if (type(lo) not in (int, float) or type(hi) not in (int, float)
                or not (lo > 1.0 and hi < 1.0 and lo > hi + 0.5)):
            raise RuntimeError('autonomous departure readings do not discriminate parcels')

def native_mission_markers(mode):
    """Extract existing native markers from the final host oracle, not a new list."""
    tree = ast.parse(SCRIPTS[mode].read_text(encoding='utf-8'))
    candidates = []
    for node in ast.walk(tree):
        values = None
        if (mode == 'memory' and isinstance(node, ast.For) and
                isinstance(node.target, ast.Name) and node.target.id == 'marker' and
                isinstance(node.iter, (ast.Tuple, ast.List))):
            values = node.iter.elts
        if (mode == 'autonomous' and isinstance(node, ast.Assign) and
                len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and
                node.targets[0].id == 'markers' and isinstance(node.value, (ast.Tuple, ast.List))):
            values = node.value.elts
        if values is not None and all(isinstance(v, ast.Constant) and isinstance(v.value, str)
                                      for v in values):
            native = [v.value for v in values]
            prefix = 'WEBEEBLOCKS_MEMORY_' if mode == 'memory' else 'WEBEEBLOCKS_AUTONOMOUS_'
            if len(native) >= 10 and all(v.startswith(prefix) for v in native):
                candidates.append(native)
    if len(candidates) != 1:
        raise RuntimeError('ambiguous native marker inventory')
    return candidates[0]

def require_native_mission_oracles(mode, path, native):
    if any(marker not in native for marker in native_mission_markers(mode)):
        raise RuntimeError('native mission result missing before retirement')
    if 'ERROR:' in native:
        raise RuntimeError('native Webots reported ERROR before retirement')
    if mode == 'memory':
        line = next((s for s in native.splitlines()
                     if 'WEBEEBLOCKS_MEMORY_TIMEOUT attempt=3' in s), '')
        if not line or any(token not in line
                           for token in ('collision=0', 'landed=1', 'stationary=1', 'arrival=0')):
            raise RuntimeError('wrong-final-bay native terminal oracle missing')

def complete_evidence(mode, path, required):
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if not raw.endswith(b'\n'):
        return None  # The event server may be in the middle of a write.
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in events):
        raise RuntimeError('malformed browser evidence')
    if any(row.get('event') in ('ERROR', 'WINDOW_ERROR', 'UNHANDLED_REJECTION')
           for row in events):
        raise RuntimeError('browser reported an error; refuse native retirement')
    by_name = {}
    for row in events:
        name = row.get('event')
        if name in required:
            if name in by_name:
                raise RuntimeError('duplicate required browser proof: ' + name)
            by_name[name] = row.get('detail')
    if COMPLETE[mode] not in by_name:
        return None
    if set(required) != set(by_name):
        raise RuntimeError('browser COMPLETE preceded required mission proofs')
    if by_name[COMPLETE[mode]] != SUMMARY[mode] or by_name.get(
            'MEMORY_OVERWRITE_PROBE_READY' if mode == 'memory' else 'AUTONOMOUS_PROBE_READY'
    ) != {'ready': True}:
        raise RuntimeError('browser final mission evidence wrong')
    validate_browser_oracles(mode, by_name, required)
    return hashlib.sha256(raw).hexdigest()

def native_main(args):
    directory = Path(args.artifacts)
    if not directory.is_dir() or not Path(args.world).is_file():
        raise RuntimeError('isolated native world/artifacts missing')
    home = Path(os.environ.get('WEBOTS_HOME', '/usr/local/webots'))
    native = home / 'bin/webots-bin'
    if not native.is_file() or (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('wrong native Webots executable identity')
    env = os.environ.copy()
    env['WEBOTS_HOME'] = str(home)
    # Preserve the R2025a Linux launcher temporary-directory contract:
    # WEBOTS_TMPDIR defaults to TMPDIR, otherwise /tmp; both are exported.
    original_tmp = env.get('WEBOTS_TMPDIR') or env.get('TMPDIR') or '/tmp'
    env['TMPDIR'] = original_tmp
    env['WEBOTS_TMPDIR'] = original_tmp
    env['WEBOTS_ORIGINAL_LD_LIBRARY_PATH'] = env.get('LD_LIBRARY_PATH', '')
    env['LD_LIBRARY_PATH'] = str(home / 'lib/webots') + os.pathsep + env['WEBOTS_ORIGINAL_LD_LIBRARY_PATH']
    env['QT_QPA_PLATFORM'] = 'xcb'
    env.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')
    required = required_events(args.kind)
    report = {'schema': 1, 'kind': args.kind, 'normal_success': False,
              'native_binary': str(native), 'browser_complete': False,
              'fallback_used': False}
    command = [str(native), '--stdout', '--stderr', '--batch', '--mode=fast',
               '--minimize', str(Path(args.world).resolve())]
    child = None
    log = None
    try:
        with tempfile.TemporaryDirectory(prefix='progression-qpa-') as qpa:
            os.chmod(qpa, 0o700)
            env['XDG_RUNTIME_DIR'] = qpa
            with NativeLogCapture(directory / 'webots.log') as log:
                child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                         cwd=ROOT, env=env, start_new_session=True)
                report['native_pid'] = child.pid
                deadline = time.monotonic() + 1500
                events = directory / 'browser-events.jsonl'
                while True:
                    if child.poll() is not None:
                        raise RuntimeError('webots-bin exited before administrative retirement')
                    if time.monotonic() >= deadline:
                        raise TimeoutError('native progression exceeded 1500s')
                    fingerprint = complete_evidence(args.kind, events, required)
                    if fingerprint:
                        require_no_terminal_crash(directory / 'webots.log')
                        require_native_mission_oracles(args.kind, directory / 'webots.log',
                                                       (directory / 'webots.log').read_text(errors='replace'))
                        report['browser_complete'] = True
                        report['frozen_events_sha256'] = fingerprint
                        request = args.kind + ' ' + uuid.uuid4().hex + '\n'
                        pending = directory / 'normal-quit.pending'
                        with pending.open('x', encoding='ascii') as stream:
                            stream.write(request)
                            stream.flush()
                            os.fsync(stream.fileno())
                        pending.replace(directory / 'normal-quit.request')
                        report['requested'] = True
                        child.wait(timeout=5)
                        report['native_exit_code'] = child.returncode
                        if child.returncode != 0:
                            raise RuntimeError('real webots-bin exited nonzero')
                        if (directory / 'normal-quit.ack').read_text(encoding='ascii') != request:
                            raise RuntimeError('Supervisor ACK missing or mismatched')
                        report['acknowledged'] = True
                        break
                    time.sleep(0.2)
            log.finish()
            report['stdout_eof'] = True
            require_no_terminal_crash(directory / 'webots.log')
            until = time.monotonic() + 2
            while True:
                state = owned_process_group_state(child.pid)
                report['owned_group_state'] = state
                if state['status'] == 'empty':
                    break
                if state['status'] == 'unknown' or time.monotonic() >= until:
                    raise RuntimeError('real Webots process group not proven absent')
                time.sleep(0.05)
            if hashlib.sha256((directory / 'browser-events.jsonl').read_bytes()).hexdigest() != report['frozen_events_sha256']:
                raise RuntimeError('browser proof mutated during native shutdown')
            report['proofs_unchanged'] = True
            report['normal_success'] = True
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        report['fallback_used'] = True
        if child is not None:
            try:
                stop_groups([child])  # #793: TERM then KILL, NEVER normal success.
            except Exception as cleanup_exc:
                report['cleanup_error'] = repr(cleanup_exc)
        raise
    finally:
        (directory / 'normal-quit.json').write_text(
            json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('PROGRESSION_NATIVE_NORMAL_EXIT ' + json.dumps(report, sort_keys=True), flush=True)

def verify_native_report(directory, kind):
    """Outer host rejects any synthetic Docker/wrapper success."""
    directory = Path(directory)
    report = json.loads((directory / 'normal-quit.json').read_text(encoding='utf-8'))
    if (report.get('schema') != 1 or report.get('kind') != kind or
            report.get('normal_success') is not True or
            report.get('browser_complete') is not True or
            report.get('requested') is not True or
            report.get('acknowledged') is not True or
            report.get('stdout_eof') is not True or
            report.get('native_exit_code') != 0 or
            report.get('proofs_unchanged') is not True or
            report.get('fallback_used') is not False or
            not isinstance(report.get('native_pid'), int) or
            report.get('native_pid') <= 1 or
            report.get('owned_group_state', {}).get('status') != 'empty' or
            report.get('owned_group_state', {}).get('evidence') != 'kernel-pgid-esrch' or
            not report.get('native_binary', '').endswith('/bin/webots-bin')):
        raise RuntimeError('real native Webots exit not proven')
    request = (directory / 'normal-quit.request').read_text(encoding='ascii')
    if not re.fullmatch(re.escape(kind) + r' [0-9a-f]{32}\n', request):
        raise RuntimeError('invalid native retirement request')
    if (directory / 'normal-quit.ack').read_text(encoding='ascii') != request:
        raise RuntimeError('native retirement ACK mismatch')
    if hashlib.sha256((directory / 'browser-events.jsonl').read_bytes()).hexdigest() != report.get('frozen_events_sha256'):
        raise RuntimeError('native retirement browser evidence mutated')
    require_no_terminal_crash(directory / 'webots.log')
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True, choices=tuple(COMPLETE))
    parser.add_argument('--world', required=True)
    parser.add_argument('--artifacts', required=True)
    native_main(parser.parse_args())

if __name__ == '__main__':
    main()
