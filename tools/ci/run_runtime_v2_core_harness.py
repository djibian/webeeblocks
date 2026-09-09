#!/usr/bin/env python3
from __future__ import annotations
import html, http.server, json, os, pathlib, re, shutil, socketserver, subprocess, sys, threading, time
HERE=pathlib.Path(__file__).resolve().parent; REPO_ROOT=HERE.parents[1]; HARNESS=pathlib.Path('tools/ci/runtime_v2_core_harness.html')
def browser_binary():
    for candidate in (os.environ.get('CHROME_BIN'),'google-chrome','google-chrome-stable','chromium','chromium-browser'):
        if candidate and shutil.which(candidate): return shutil.which(candidate) or candidate
    raise RuntimeError('no Chrome/Chromium binary found; set CHROME_BIN')
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
def main():
    os.chdir(REPO_ROOT)
    up_range_test=subprocess.run([sys.executable,'tools/ci/test_runtime_v2_up_range.py'],text=True,capture_output=True)
    if up_range_test.returncode:
        print('FAIL Runtime v2 upward Multi-ranger wiring contract',file=sys.stderr);print(up_range_test.stdout,file=sys.stderr);print(up_range_test.stderr,file=sys.stderr);return up_range_test.returncode
    print(up_range_test.stdout.strip())
    color_led_visual_test=subprocess.run([sys.executable,'tools/ci/test_color_led_deck_visual.py'],text=True,capture_output=True)
    if color_led_visual_test.returncode:
        print('FAIL Color LED deck visual contract',file=sys.stderr);print(color_led_visual_test.stdout,file=sys.stderr);print(color_led_visual_test.stderr,file=sys.stderr);return color_led_visual_test.returncode
    print(color_led_visual_test.stdout.strip())
    expected_starters = {
        '01-sequence.wbb':'progression-sequence-v1',
        '02-precise-movement.wbb':'progression-precise-movement-v1',
        '03-repeat.wbb':'progression-repeat-v1',
        '04-simple-decision.wbb':'progression-simple-decision-v1',
        '05-reactive.wbb':'progression-reactive-v1',
        '06-multi-perception.wbb':'progression-combined-decisions-v1',
        '07-memory.wbb':'progression-memory-v1',
        '08-autonomous-strategy.wbb':'progression-autonomous-strategy-v1',
    }
    starter_dir=pathlib.Path('activities/progression')
    actual_starters=sorted(path.name for path in starter_dir.glob('*.wbb'))
    if actual_starters != list(expected_starters):
        print('FAIL progression starter order', actual_starters, file=sys.stderr); return 1
    for filename, activity_id in expected_starters.items():
        project=json.loads((starter_dir / filename).read_text(encoding='utf-8'))
        if project.get('activity',{}).get('id') != activity_id:
            print(f'FAIL progression starter mapping {filename}', file=sys.stderr); return 1
    print('PASS ordered progression starter files map one-to-one to activity profiles')
    variable_test=subprocess.run(['node','tools/ci/test_runtime_v2_variables.js'],text=True,capture_output=True)
    if variable_test.returncode:
        print('FAIL Runtime v2 variables/memory contract',file=sys.stderr);print(variable_test.stdout,file=sys.stderr);print(variable_test.stderr,file=sys.stderr);return variable_test.returncode
    print(variable_test.stdout.strip())
    physical_capability_test=subprocess.run(['node','tools/ci/test_physical_capability_contract.js'],text=True,capture_output=True)
    if physical_capability_test.returncode:
        print('FAIL read-only physical capability contract',file=sys.stderr);print(physical_capability_test.stdout,file=sys.stderr);print(physical_capability_test.stderr,file=sys.stderr);return physical_capability_test.returncode
    print(physical_capability_test.stdout.strip())
    physical_probe_test=subprocess.run([sys.executable,'tools/ci/test_physical_capability_probe.py'],text=True,capture_output=True)
    if physical_probe_test.returncode:
        print('FAIL read-only Crazyradio capability evidence',file=sys.stderr);print(physical_probe_test.stdout,file=sys.stderr);print(physical_probe_test.stderr,file=sys.stderr);return physical_probe_test.returncode
    print(physical_probe_test.stdout.strip())
    physical_supervisor_test=subprocess.run([sys.executable,'tools/ci/test_physical_supervisor_state.py'],text=True,capture_output=True)
    if physical_supervisor_test.returncode:
        print('FAIL connection-epoch physical supervisor freshness',file=sys.stderr);print(physical_supervisor_test.stdout,file=sys.stderr);print(physical_supervisor_test.stderr,file=sys.stderr);return physical_supervisor_test.returncode
    print(physical_supervisor_test.stdout.strip())
    physical_landing_completion_test=subprocess.run([sys.executable,'tools/ci/test_physical_landing_completion.py'],text=True,capture_output=True)
    if physical_landing_completion_test.returncode:
        print('FAIL controlled physical landing completion evidence',file=sys.stderr);print(physical_landing_completion_test.stdout,file=sys.stderr);print(physical_landing_completion_test.stderr,file=sys.stderr);return physical_landing_completion_test.returncode
    print(physical_landing_completion_test.stdout.strip())
    physical_yaw_test=subprocess.run([sys.executable,'tools/ci/test_physical_yaw_observer.py'],text=True,capture_output=True)
    if physical_yaw_test.returncode:
        print('FAIL fresh physical yaw observation',file=sys.stderr);print(physical_yaw_test.stdout,file=sys.stderr);print(physical_yaw_test.stderr,file=sys.stderr);return physical_yaw_test.returncode
    print(physical_yaw_test.stdout.strip())
    physical_watchdog_test=subprocess.run([sys.executable,'tools/ci/test_physical_watchdog_liveness.py'],text=True,capture_output=True)
    if physical_watchdog_test.returncode:
        print('FAIL physical watchdog activation/liveness guard',file=sys.stderr);print(physical_watchdog_test.stdout,file=sys.stderr);print(physical_watchdog_test.stderr,file=sys.stderr);return physical_watchdog_test.returncode
    print(physical_watchdog_test.stdout.strip())
    powered_session_test=subprocess.run([sys.executable,'tools/ci/test_physical_powered_session_authority.py'],text=True,capture_output=True)
    if powered_session_test.returncode:
        print('FAIL trusted physical powered-session/reset authority',file=sys.stderr);print(powered_session_test.stdout,file=sys.stderr);print(powered_session_test.stderr,file=sys.stderr);return powered_session_test.returncode
    print(powered_session_test.stdout.strip())
    current_program_provenance_test=subprocess.run([sys.executable,'tools/ci/test_current_program_provenance_authority.py'],text=True,capture_output=True)
    if current_program_provenance_test.returncode:
        print('FAIL separate current-program provenance authority',file=sys.stderr);print(current_program_provenance_test.stdout,file=sys.stderr);print(current_program_provenance_test.stderr,file=sys.stderr);return current_program_provenance_test.returncode
    print(current_program_provenance_test.stdout.strip())
    physical_http_test=subprocess.run([sys.executable,'tools/ci/test_physical_capability_http_bridge.py'],text=True,capture_output=True)
    if physical_http_test.returncode:
        print('FAIL read-only physical capability HTTP bridge',file=sys.stderr);print(physical_http_test.stdout,file=sys.stderr);print(physical_http_test.stderr,file=sys.stderr);return physical_http_test.returncode
    print(physical_http_test.stdout.strip())
    physical_submission_test=subprocess.run(['node','tools/ci/test_physical_submission_bridge.js'],text=True,capture_output=True)
    if physical_submission_test.returncode:
        print('FAIL session-bound physical submission bridge',file=sys.stderr);print(physical_submission_test.stdout,file=sys.stderr);print(physical_submission_test.stderr,file=sys.stderr);return physical_submission_test.returncode
    print(physical_submission_test.stdout.strip())
    teacher_authorization_test=subprocess.run([sys.executable,'tools/ci/test_teacher_run_authorization.py'],text=True,capture_output=True)
    if teacher_authorization_test.returncode:
        print('FAIL host-only teacher run authorization binding',file=sys.stderr);print(teacher_authorization_test.stdout,file=sys.stderr);print(teacher_authorization_test.stderr,file=sys.stderr);return teacher_authorization_test.returncode
    print(teacher_authorization_test.stdout.strip())
    physical_high_level_semantics_test=subprocess.run([sys.executable,'tools/ci/test_physical_high_level_semantics.py'],text=True,capture_output=True)
    if physical_high_level_semantics_test.returncode:
        print('FAIL physical HighLevelCommander semantic adapter',file=sys.stderr);print(physical_high_level_semantics_test.stdout,file=sys.stderr);print(physical_high_level_semantics_test.stderr,file=sys.stderr);return physical_high_level_semantics_test.returncode
    print(physical_high_level_semantics_test.stdout.strip())
    physical_high_level_timing_test=subprocess.run([sys.executable,'tools/ci/test_physical_high_level_timing.py'],text=True,capture_output=True)
    if physical_high_level_timing_test.returncode:
        print('FAIL physical HighLevelCommander timing policy',file=sys.stderr);print(physical_high_level_timing_test.stdout,file=sys.stderr);print(physical_high_level_timing_test.stderr,file=sys.stderr);return physical_high_level_timing_test.returncode
    print(physical_high_level_timing_test.stdout.strip())
    physical_high_level_ack_test=subprocess.run([sys.executable,'tools/ci/test_physical_high_level_ack.py'],text=True,capture_output=True)
    if physical_high_level_ack_test.returncode:
        print('FAIL pure SETPOINT_HL acknowledgement freshness domain',file=sys.stderr);print(physical_high_level_ack_test.stdout,file=sys.stderr);print(physical_high_level_ack_test.stderr,file=sys.stderr);return physical_high_level_ack_test.returncode
    print(physical_high_level_ack_test.stdout.strip())
    physical_safelink_test=subprocess.run([sys.executable,'tools/ci/test_physical_safelink_precondition.py'],text=True,capture_output=True)
    if physical_safelink_test.returncode:
        print('FAIL live radio SafeLink duplicate-suppression precondition',file=sys.stderr);print(physical_safelink_test.stdout,file=sys.stderr);print(physical_safelink_test.stderr,file=sys.stderr);return physical_safelink_test.returncode
    print(physical_safelink_test.stdout.strip())
    physical_execution_domain_test=subprocess.run([sys.executable,'tools/ci/test_physical_execution_domain.py'],text=True,capture_output=True)
    if physical_execution_domain_test.returncode:
        print('FAIL trusted physical reset/effect exclusion domain',file=sys.stderr);print(physical_execution_domain_test.stdout,file=sys.stderr);print(physical_execution_domain_test.stderr,file=sys.stderr);return physical_execution_domain_test.returncode
    print(physical_execution_domain_test.stdout.strip())
    browser=browser_binary()
    with socketserver.TCPServer(('127.0.0.1',0),QuietHandler) as server:
        port=server.server_address[1]; threading.Thread(target=server.serve_forever,daemon=True).start(); time.sleep(.05); url=f'http://127.0.0.1:{port}/{HARNESS.as_posix()}'
        process=subprocess.Popen([browser,'--headless=new','--disable-gpu','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--virtual-time-budget=5000','--dump-dom',url],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        timed_out=False
        try: stdout,stderr=process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timed_out=True; process.kill(); stdout,stderr=process.communicate()
        server.shutdown()
    marker='PASS Runtime v2 modern Blockly reactive semantics -> AST -> fail-closed preflight -> shared interpreter'
    rendered=re.search(r'<pre id="result" data-status="PASS">([^<]+)</pre>',stdout)
    rendered_text=html.unescape(rendered.group(1)).strip() if rendered else None
    if rendered_text!=marker:
        print('FAIL Runtime v2 product core',file=sys.stderr); print('browser exit:',process.returncode,file=sys.stderr); print(stderr[-4000:],file=sys.stderr); print(stdout[-8000:],file=sys.stderr); return 1
    if not timed_out and process.returncode:
        print(f'FAIL Runtime v2 product core: browser exited {process.returncode}',file=sys.stderr); print(stderr[-4000:],file=sys.stderr); return 1
    if timed_out: print('WARN: headless browser required forced shutdown after emitting the exact Runtime v2 PASS DOM marker.',file=sys.stderr)
    print(marker); return 0
if __name__=='__main__': raise SystemExit(main())
