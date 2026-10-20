def main() -> int:
    cleanup()
    shutil.rmtree(ARTIFACT_ROOT, ignore_errors=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    checks = (
        [sys.executable, "tools/ci/test_runtime_v2_autonomous_observer.py"],
        [sys.executable, "tools/ci/test_reset_native_summary.py"],
        ["node", "tools/ci/test_progression_autonomous_contract.js"],
        ["node", "--check", "plugins/robot_windows/autonomous_probe/autonomous_probe.js"],
    )
    for command in checks:
        checked = run(list(command), capture=True)
        if checked.returncode:
            return fail("static Activity 8 contract failed", checked.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        'name "Crazyflie WebeeBlocks"',
        'name "Progression combined decisions evaluator"',
        '"combined-decisions-evaluator-v1"',
        'name "Progression autonomous strategy evaluator"',
        '"autonomous-evaluator-v1"',
    ):
        if marker not in source_world:
            return fail(f"missing Activity 8 evaluator world marker: {marker}")
    world = observed_world(source_world)
    # An unexpected existing controller is not ours to overwrite or remove.
    OBSERVER_DIRECTORY.mkdir()
    observer_script = OBSERVER_DIRECTORY / f"{OBSERVER_NAME}.py"
    try:
        shutil.copyfile(OBSERVER_SOURCE, observer_script)
        TEMP_WORLD.write_text(world, encoding="utf-8")
        (ARTIFACT_ROOT / "world.wbt").write_text(world, encoding="utf-8")
        provenance = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (TEMP_WORLD, OBSERVER_SOURCE,
                                   ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c")}
        (ARTIFACT_ROOT / "native-reset-provenance.json").write_text(
            json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        TEMP_PROJECT.write_text("Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n", encoding="utf-8")

        built = build_runtime_for_probe()
        (ARTIFACT_ROOT / "build.log").write_text(built.stdout or "", encoding="utf-8")
        if built.returncode:
            return fail("Runtime v2/Activity 8 evaluator build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
artifact_dir=/workspace/ci-artifacts/progression-autonomous-mission
events="$artifact_dir/browser-events.jsonl"
mkdir -p "$artifact_dir" /root/.config/Cyberbotics
printf "%s\n" \
  "[RobotWindow]" \
  "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" \
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py \
  --output "$events" &
server=$!
trap "kill $server 2>/dev/null || true" EXIT
sleep 0.5
# Activity 8 proves simulated mission state, not wall-clock pacing. Fast mode
# preserves the same deterministic 32 ms steps while keeping the real rendered
# Robot Window/browser lifecycle that carries Runtime-v2 commands.
timeout -k 5s 1500s xvfb-run -a webots --stdout --stderr --batch --mode=fast /workspace/worlds/ci_progression_autonomous.wbt &
webots_runner=$!
while kill -0 "$webots_runner" 2>/dev/null; do
  if grep -Fq 'AUTONOMOUS_MISSION_TEST_COMPLETE' "$events" 2>/dev/null; then
    kill "$webots_runner" 2>/dev/null || true
    set +e
    wait "$webots_runner"
    set -e
    exit 0
  fi
  if grep -Eq '"event"[[:space:]]*:[[:space:]]*"(ERROR|WINDOW_ERROR|UNHANDLED_REJECTION)"' "$events" 2>/dev/null; then
    kill "$webots_runner" 2>/dev/null || true
    set +e
    wait "$webots_runner"
    set -e
    exit 0
  fi
  sleep 0.25
done
set +e
wait "$webots_runner"
runner_rc=$?
set -e
exit "$runner_rc"
'''.strip()
        result = execute_native()
        webots_log = result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(result.returncode) + "\n", encoding="utf-8")
        phase_complete = True
        if os.environ.get("WEBEEBLOCKS_RESET_PHASE_TRACE") == "1":
            import importlib.util
            analyzer_path = ROOT / "experiments/runtime-reset-phase/analyze.py"
            spec = importlib.util.spec_from_file_location("reset_phase_analyze", analyzer_path)
            analyzer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(analyzer)
            try:
                phase_summary = analyzer.summarize(webots_log)
                phase_complete = (len(phase_summary["resets"]) == 14 and
                                  all(row["terminal"].endswith(" OK") for row in phase_summary["resets"]))
            except Exception as exc:
                phase_summary = {"status": "UNPROVEN", "error": str(exc)}
                phase_complete = False
            (ARTIFACT_ROOT / "reset-phase-summary.json").write_text(json.dumps(phase_summary, indent=2) + "\n")
        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if result.returncode == 124:
            detail = webots_log[-16000:]
            if event_path.exists():
                detail += "\nBROWSER EVENTS AT TIMEOUT:\n" + event_path.read_text(encoding="utf-8")[-10000:]
            return fail("Webots Activity 8 proof exceeded the 1500s local budget", detail)
        if result.returncode != 0:
            return fail(f"Webots Activity 8 proof exited with {result.returncode}", webots_log[-16000:])
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing Activity 8 browser evidence", webots_log[-16000:])

        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid Activity 8 browser evidence: {exc}")
        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            return fail("Activity 8 browser probe reported an error", json.dumps(errors[0], ensure_ascii=False) + "\n" + webots_log[-16000:])

        required = (
            "AUTONOMOUS_PROBE_READY",
            "AUTONOMOUS_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE",
            "AUTONOMOUS_DEPARTURE_SMALL_RANGE",
            "AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_RESET_FRESH",
            "AUTONOMOUS_DEPARTURE_LARGE_RANGE",
            "AUTONOMOUS_INTEGRATED_LARGE_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_LARGE_BE_FORWARD_RESET_FRESH",
            "AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_RESET_FRESH",
            "AUTONOMOUS_INTEGRATED_LARGE_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_FIXED_ROUTE_FRESH",
            "AUTONOMOUS_FIXED_ROUTE_NOT_ACHIEVED",
            "AUTONOMOUS_NO_MEMORY_FRESH",
            "AUTONOMOUS_NO_MEMORY_LARGE_NOT_ACHIEVED",
            "AUTONOMOUS_FRONT_ONLY_FRESH",
            "AUTONOMOUS_FRONT_ONLY_RIGHT_NOT_ACHIEVED",
            "AUTONOMOUS_INCOMPLETE_FRESH",
            "AUTONOMOUS_INCOMPLETE_NOT_ACHIEVED",
            "AUTONOMOUS_DOWNSTREAM_INFERENCE_SMALL_BE_FRESH",
            "AUTONOMOUS_DOWNSTREAM_INFERENCE_SMALL_BE_ACHIEVED",
            "AUTONOMOUS_DOWNSTREAM_INFERENCE_LARGE_BE_FRESH",
            "AUTONOMOUS_DOWNSTREAM_INFERENCE_LARGE_BE_NOT_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BB_RIGHT_FRESH",
            "AUTONOMOUS_ALT_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_BB_RIGHT_FRESH",
            "AUTONOMOUS_ALT_LARGE_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BE_FORWARD_FRESH",
            "AUTONOMOUS_ALT_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_BE_FORWARD_FRESH",
            "AUTONOMOUS_ALT_LARGE_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_FINAL_RESET_FRESH",
            "AUTONOMOUS_MISSION_TEST_COMPLETE",
        )
        names = [event.get("event") for event in events]
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing Activity 8 causal events: {missing}", json.dumps(names))
        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        if details["AUTONOMOUS_PROBE_READY"] != {"ready": True}:
            return fail(f"Activity 8 probe did not become ready: {details['AUTONOMOUS_PROBE_READY']}")
        if details["AUTONOMOUS_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE"] != {"code":"OUTCOME_UNAVAILABLE"}:
            return fail("Activity 8 failure probe synthesized an outcome without irreversible failure")

        small_detail = details["AUTONOMOUS_DEPARTURE_SMALL_RANGE"]
        large_detail = details["AUTONOMOUS_DEPARTURE_LARGE_RANGE"]
        small_range = small_detail.get("meters") if isinstance(small_detail, dict) else None
        large_range = large_detail.get("meters") if isinstance(large_detail, dict) else None
        numeric = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
        if not numeric(small_range) or not numeric(large_range):
            return fail(f"invalid Activity 8 departure range evidence: small={small_detail} large={large_detail}")
        if not small_range > 1.0 or not large_range < 1.0 or not small_range > large_range + 0.5:
            return fail(
                "Activity 8 owned parcel signal does not causally distinguish the two classes",
                f"small_range={small_range} large_range={large_range}",
            )

        for fresh in (name for name in required if name.endswith("_FRESH")):
            if details[fresh] != {"code":"OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {fresh}: {details[fresh]}")

        for achieved in (
            "AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_LARGE_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_LARGE_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_DOWNSTREAM_INFERENCE_SMALL_BE_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_BE_FORWARD_ACHIEVED",
        ):
            if details[achieved] != {"status":"achieved"}:
                return fail(f"unexpected achieved Activity 8 event {achieved}: {details[achieved]}")
        for negative in (
            "AUTONOMOUS_FIXED_ROUTE_NOT_ACHIEVED",
            "AUTONOMOUS_FRONT_ONLY_RIGHT_NOT_ACHIEVED",
        ):
            if details[negative] not in (
                {"status":"not-achieved"},
                {"status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT"},
            ):
                return fail(f"unexpected causal Activity 8 failure {negative}: {details[negative]}")
        for ordinary_negative in (
            "AUTONOMOUS_NO_MEMORY_LARGE_NOT_ACHIEVED",
            "AUTONOMOUS_INCOMPLETE_NOT_ACHIEVED",
            "AUTONOMOUS_DOWNSTREAM_INFERENCE_LARGE_BE_NOT_ACHIEVED",
        ):
            if details[ordinary_negative] != {"status":"not-achieved"}:
                return fail(f"unexpected completed Activity 8 failure {ordinary_negative}: {details[ordinary_negative]}")
        if details["AUTONOMOUS_MISSION_TEST_COMPLETE"] != {
            "integrated":["achieved", "achieved", "achieved", "achieved"],
            "fixed_route":"not-achieved",
            "no_memory":"not-achieved",
            "front_only":"not-achieved",
            "incomplete":"not-achieved",
            "downstream_inference":["achieved", "not-achieved"],
            "alternate":["achieved", "achieved", "achieved", "achieved"],
        }:
            return fail(f"unexpected Activity 8 summary: {details['AUTONOMOUS_MISSION_TEST_COMPLETE']}")

        # Both parcel classes must lose the reference after their departure
        # reading, before forward motion to the first decision/detour begins.
        for attempt in (1, 2):
            attempt_start = webots_log.find(f"WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt={attempt} ")
            hidden = webots_log.find(
                f"WEBEEBLOCKS_AUTONOMOUS_REFERENCE_UNAVAILABLE attempt={attempt} ", attempt_start)
            departure_read = webots_log.find("TRACE RANGE front value=", attempt_start)
            first_forward = webots_log.find("TRACE MOVE forward distance=0.200000000", attempt_start)
            if not (0 <= attempt_start < departure_read < hidden < first_forward):
                return fail(f"Activity 8 attempt {attempt} did not hide its reference between departure sensing and the first detour", webots_log)

        markers = (
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=1 pattern=small-BE-forward parcel=small reference_x=1.150",
            "WEBEEBLOCKS_AUTONOMOUS_REFERENCE_UNAVAILABLE attempt=1 reference_hidden=1 mask_x=0.250",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=2 pattern=large-BE-forward parcel=large reference_x=0.350",
            "WEBEEBLOCKS_AUTONOMOUS_REFERENCE_UNAVAILABLE attempt=2 reference_hidden=1 mask_x=0.250",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=3 pattern=small-BB-right",
            "WEBEEBLOCKS_AUTONOMOUS_ROUTE attempt=3 route=right valid=1",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=3 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=4 pattern=large-BB-right",
            "WEBEEBLOCKS_AUTONOMOUS_ROUTE attempt=4 route=right valid=1",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=4 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=5 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=6 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=7",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=7 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_TIMEOUT attempt=8",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=8 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=9 pattern=small-BE-forward",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=9 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=10 pattern=large-BE-forward",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=10 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=11 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=12 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=13 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=14 status=achieved",
        )
        for marker in markers:
            if marker not in webots_log:
                return fail(f"missing Activity 8 Webots marker: {marker}", webots_log[-16000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-16000:])

        try:
            validate_observer_trace(ARTIFACT_ROOT / "native-reset-state.jsonl",
                                    required_attempts=(7, 8))
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            return fail(f"native reset diagnostic evidence unavailable: {exc}")

        if not phase_complete:
            return fail("requested internal RESET observations incomplete; preserve raw trace")

        print("PASS Activity 8 autonomous synthesis: the mission owns and removes its parcel signal, pairs identical downstream worlds with both parcel classes, proves downstream sensing cannot replace departure memory, accepts two distinct stored-value strategies, and rejects fixed-route, front-only and incomplete shortcuts from observable world state in real R2025a")
        return 0
    finally:
        # Supplemental forensic report only; no reset/CI decision is taken here.
        # On a failing probe the raw trace, or its explicit absence, remains primary.
        try:
            from reset_native_summary import summarize
            forensic_report = summarize(ARTIFACT_ROOT / "native-reset-state.jsonl")
        except Exception as exc:
            forensic_report = {"schema": "webeeblocks-reset-native-forensics-v1",
                               "status": "UNPROVEN", "error": str(exc)}
        (ARTIFACT_ROOT / "native-reset-summary.json").write_text(
            json.dumps(forensic_report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        # Preserve byte identity even for a failing/partial native campaign.
        digests = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in ARTIFACT_ROOT.iterdir() if path.is_file()}
        (ARTIFACT_ROOT / "sha256.json").write_text(
            json.dumps(digests, indent=2) + "\n", encoding="utf-8")
        cleanup()
        observer_script.unlink(missing_ok=True)
        OBSERVER_DIRECTORY.rmdir()
