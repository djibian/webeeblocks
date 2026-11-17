#!/usr/bin/env python3
"""Falsify high-takeoff and no-ascent shortcuts in actual Webots R2025a.

No mocked flight, no simulator bypass, no AST inspection. Outputs are evidence,
not an owner pedagogical PASS; the first low-flight trajectory is experimental.
"""
from __future__ import annotations
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import prepare_classroom_altitude_canopy as world
import run_classroom_altitude_scene_ack as ack

ARTIFACT = world.ROOT / 'ci-artifacts' / Path(
    os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR',
                   '/workspace/ci-artifacts/progression-neutral-start')
).name / 'altitude-canopy-flight'
def high_fail_safe_event_order(contact, fatal, error_response, first_reset, low_success):
    """Both unsafe native signals must follow physical contact and precede RESET.

    The Qt/WWI response and native FATAL have no guaranteed relative log order:
    either can be flushed first. Both are required, never just one.
    """
    stamps = (contact, fatal, error_response, first_reset, low_success)
    return (all(value >= 0 for value in stamps) and
            contact < fatal < first_reset < low_success and
            contact < error_response < first_reset)


REQUIRED = (
    'CANOPY_HTML_LOADED','CANOPY_JS_STARTED','CANOPY_RUNTIME_READY',
    'CANOPY_SCENE_ACK','CANOPY_HIGH_REJECTED','CANOPY_RESET_FRESH',
    'CANOPY_SCENE_REATTACHED','CANOPY_CLEARED_LOW',
    'CANOPY_ASCENDED_AFTER_CLEARANCE','CANOPY_LOW_CLIMB_ACHIEVED',
    'CANOPY_BLIND_RESET_FRESH','CANOPY_BLIND_SCENE_REATTACHED',
    'CANOPY_BLIND_NO_ASCENT_REJECTED','CANOPY_TEST_COMPLETE',
)


def run() -> int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    log_path = ARTIFACT / 'webots.log'
    events_path = ARTIFACT / 'events.json'
    ack.EVENTS.clear()
    server = None
    process = None
    output = None
    try:
        world.prepare()
        server = ack.http.server.ThreadingHTTPServer(('127.0.0.1',8765),ack.Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        env = dict(os.environ)
        env['WEBOTS_WEB_BROWSER'] = '/workspace/tools/ci/webots_runtime_v2_browser.sh'
        output = log_path.open('w',encoding='utf-8')
        process = subprocess.Popen(
            ['timeout','-k','5s','295s','xvfb-run','-a','webots',
             '--stdout','--stderr','--batch','--mode=realtime',str(world.WORLD)],
            cwd=str(world.ROOT),stdout=output,stderr=subprocess.STDOUT,
            env=env,start_new_session=True
        )
        deadline = time.monotonic()+285
        while time.monotonic()<deadline:
            observed = [e.get('event') for e in ack.EVENTS]
            if 'CANOPY_TEST_COMPLETE' in observed or 'CANOPY_ERROR' in observed:
                break
            if process.poll() is not None:
                break
            time.sleep(0.25)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=8)
        if output is not None: output.close()
        if server is not None:
            server.shutdown()
            server.server_close()
        events_path.write_text(json.dumps(ack.EVENTS,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        world.cleanup()

    transcript = log_path.read_text(encoding='utf-8',errors='replace')
    observed = [e.get('event') for e in ack.EVENTS]
    missing = [name for name in REQUIRED if observed.count(name)!=1]
    native_ready = 'WEBEEBLOCKS_ALTITUDE_READY scene=altitude-v1 oracle=progression-altitude-3d-v1' in transcript
    actual_contact = re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=1 status=not-achieved\b[^\n]*\bcontact=1\b',transcript)
    low_success = re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=2 status=achieved\b[^\n]*\bcrossed=1\b[^\n]*\bcontact=0\b[^\n]*\bcompletion=1\b',
        transcript)
    # A separate third native attempt must reject the A1-style path:
    # takeoff at safe height followed by forward movement without ascent.
    blind_rejection = re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=3 status=not-achieved\b[^\n]*\bairborne=1\b[^\n]*\bcrossed=0\b',
        transcript)
    browser_dir = world.ROOT / 'ci-artifacts' / Path(
        os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR',
                       '/workspace/ci-artifacts/progression-neutral-start')
    ).name
    launch_file = browser_dir / 'browser-launch.log'
    launch = launch_file.read_text(encoding='utf-8',errors='replace') if launch_file.exists() else ''
    launched = 'BROWSER_LAUNCHED args=' in launch and 'altitude_canopy_probe.html' in launch
    # The roof collision MUST trip the unmodified native unsafe-attitude
    # fail-safe on attempt 1. Its one exact FATAL is the negative witness,
    # never permission to ignore other or later native safety failures.
    expected_fatal = 'WEBEEBLOCKS_RUNTIME_V2 FATAL unsafe attitude or action timeout'
    native_fatal_matches = list(re.finditer(
        r'[^\n]*WEBEEBLOCKS_RUNTIME_V2 FATAL[^\n]*',transcript))
    native_fatals = [match.group().strip() for match in native_fatal_matches]
    high_error_responses = list(re.finditer(
        re.escape('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR UNSAFE_OR_TIMEOUT'),
        transcript))
    positions = (
        actual_contact.start() if actual_contact else -1,
        native_fatal_matches[0].start() if native_fatal_matches else -1,
        high_error_responses[0].start() if len(high_error_responses) == 1 else -1,
        transcript.find('WEBEEBLOCKS_RUNTIME_V2 TRACE RESET'),
        low_success.start() if low_success else -1,
    )
    second_reset = transcript.find('WEBEEBLOCKS_RUNTIME_V2 TRACE RESET',
                                   positions[3]+1) if positions[3]>=0 else -1
    blind_sequence = bool(low_success and blind_rejection and
                          second_reset > low_success.start() and
                          blind_rejection.start() > second_reset)
    # Independently cross-check the true C oracle log and the result presented
    # by the actual Robot Window browser through the existing WWI channel.
    high_causes = [e.get('detail') or {} for e in ack.EVENTS
                   if e.get('event') == 'CANOPY_HIGH_REJECTED']
    blind_causes = [e.get('detail') or {} for e in ack.EVENTS
                    if e.get('event') == 'CANOPY_BLIND_NO_ASCENT_REJECTED']
    high_native_cause = re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=1 status=not-achieved\b[^\n]*\breason=obstacle-contact\b',
        transcript)
    blind_native_cause = re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=3 status=not-achieved\b[^\n]*\breason=(unsafe-clearance|obstacle-contact)\b',
        transcript)
    high_diagnosed = (len(high_causes) == 1 and
                      high_causes[0].get('reason') == 'obstacle-contact' and
                      high_causes[0].get('studentMessage') ==
                        'Mission non accomplie — Contact avec un obstacle' and
                      high_native_cause is not None)
    blind_diagnosed = (len(blind_causes) == 1 and
                       blind_causes[0].get('reason') in
                         ('unsafe-clearance','obstacle-contact') and
                       isinstance(blind_causes[0].get('studentMessage'),str) and
                       blind_causes[0]['studentMessage'].startswith('Mission non accomplie — ') and
                       blind_native_cause is not None and
                       blind_causes[0]['reason'] == blind_native_cause.group(1))
    # The no-ascent attempt may trigger the same original runtime safeguard.
    # Allow only that second, exactly identified FATAL and only AFTER reset;
    # all other fatal reasons and additional FATAL lines still fail closed.
    known_fatals = native_fatals == [expected_fatal] or (
        native_fatals == [expected_fatal,expected_fatal] and
        blind_sequence and native_fatal_matches[1].start() > second_reset)
    high_fail_safe_verified = (
        known_fatals and high_fail_safe_event_order(*positions)
    )
    fatal = ('CANOPY_ERROR' in observed or
             'WEBEEBLOCKS_ALTITUDE_FATAL' in transcript or
             not high_fail_safe_verified or
             not high_diagnosed or not blind_diagnosed or
             'ERROR:' in transcript)
    (ARTIFACT/'summary.json').write_text(json.dumps({
        'required_events_missing':missing,
        'native_ready':native_ready,'physical_roof_contact':bool(actual_contact),
        'low_climb_landing':bool(low_success),
        'no_ascent_native_rejection':bool(blind_sequence),
        'browser_launched':launched,
        'high_fail_safe_verified':high_fail_safe_verified,
        'high_native_reason_displayed':high_diagnosed,
        'blind_native_reason_displayed':blind_diagnosed,
        'fatal':fatal,'observed':observed
    },indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if (missing or not native_ready or not actual_contact or not low_success or
            not blind_sequence or not launched or fatal):
        print('FAIL native R2025a canopy flight '+json.dumps({
            'missing':missing,'native_ready':native_ready,'roof_contact':bool(actual_contact),
            'low_success':bool(low_success),
            'no_ascent_rejected':bool(blind_sequence),'browser_launched':launched,
            'high_fail_safe_verified':high_fail_safe_verified,
            'fatal':fatal,'events':ack.EVENTS[-5:]
        }),file=sys.stderr)
        print(transcript[-12000:],file=sys.stderr)
        return 1
    print('PASS R2025a A2: high TAKEOFF rejected, low+ascent landed, no-ascent rejected, RESET fresh')
    return 0


if __name__=='__main__':
    raise SystemExit(run())
