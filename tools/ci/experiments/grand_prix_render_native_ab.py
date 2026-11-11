"""One-shot paired Webots R2025a render experiment. No flight authority changes.

Uses the existing native READY/TAKEOFF/service-loss/LAND/RESET test harness,
the unmodified production NativeRouteEvaluator and production pilot sources.
This is NOT a pupil mission or a product acceptance test. The only experimental
variable is Webots --no-rendering, with the normal arm at 100% resolution.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
from unittest.mock import patch

from tools.ci import run_grand_prix_route_evaluator_native as native

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "ci-artifacts/grand-prix-render-native-ab"
TRIALS = (("A", 1), ("B", 1), ("B", 2), ("A", 2), ("A", 3), ("B", 3))
COURSE = "gp-route-v2-L2000-2500-3000-TGD-s105-H2"


def digest(path):
    with open(path, "rb") as stream:
        h = hashlib.sha256()
        for part in iter(lambda: stream.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def percentile(data, p):
    ordered = sorted(data)
    return ordered[max(0, math.ceil(len(ordered) * p) - 1)]


def read_webots_performance(path):
    if not path.is_file():
        raise RuntimeError("Webots --log-performance failed to write raw stage log")
    lines = path.read_text(errors="replace").splitlines()
    headers = next((line.split() for line in lines if
                    line.startswith("<mode> <stepsCount> ")), None)
    averages = next((line.split() for line in lines if
                     re.match(r"^AVG\s+\d+\s+", line)), None)
    if headers is None or averages is None or len(headers) != len(averages):
        raise RuntimeError("Webots native performance headers/AVG absent or malformed")
    data = dict(zip(headers, averages))
    for key in ("<physics(ms)>", "<mainRendering(ms)>", "<mainFPS>"):
        if key not in data:
            raise RuntimeError("Webots native stage not reported: " + key)
    return {key: float(data[key]) for key in (
        "<physics(ms)>", "<mainRendering(ms)>", "<mainFPS>")}


def read_trial(path):
    case = list(path.glob("flight-reset-invocation-*"))
    if len(case) != 1:
        raise RuntimeError("expected one complete native flight-reset witness")
    case = case[0]
    raw = json.loads((case / "native.json").read_text())
    native.check_native(raw)
    rows = [json.loads(line) for line in (case / "native.trace").read_text().splitlines()]
    if not rows or any(type(x.get("time_ms")) is not int for x in rows):
        raise RuntimeError("native 8ms trace missing")
    if any(b["time_ms"] - a["time_ms"] != 8 for a, b in zip(rows, rows[1:])):
        raise RuntimeError("non-contiguous 8ms Webots trace")
    if any(x.get("step_wall_s", -1) < 0 or x.get("tick_wall_s", -1) < 0
           for x in rows):
        raise RuntimeError("invalid native step/tick duration")
    if raw["configuration"] != COURSE or raw["timestep_ms"] != 8:
        raise RuntimeError("wrong world/physical step")
    return raw, rows, digest(case / "world.wbt"), case


def run_trial(home, env, arm, repetition, mode):
    directory = OUTPUT / (f"{mode}-{repetition}-{arm}")
    if directory.exists():
        raise RuntimeError("refuse existing run directory: " + str(directory))
    directory.mkdir(parents=True)
    report = {"arm": arm, "repeat": repetition, "mode": mode, "status": "UNPROVEN"}
    native.OUT = directory
    performance = directory / "webots-performance.log"
    original = subprocess.Popen

    def launch(command, *args, **kwargs):
        if not isinstance(command, list) or Path(command[0]) != home / "webots":
            raise RuntimeError("unexpected native launch, refusing intervention")
        if command.count("--mode=fast" if mode == "fast" else "--mode=realtime") != 1:
            raise RuntimeError("incorrect Webots speed mode")
        if "--no-rendering" in command:
            raise RuntimeError("driver attempted to disable the baseline render")
        if command[-1].endswith(".wbt") is False:
            raise RuntimeError("world file not last command argument")
        # Both arms use the same default full-size viewport. The original
        # minimized flag is removed in BOTH arms to keep A truly rendered.
        revised = [arg for arg in command[:-1] if arg != "--minimize"]
        revised.append("--log-performance=" + str(performance) + ",0")
        if arm == "B":
            revised.append("--no-rendering")
        revised.append(command[-1])
        report["command"] = revised
        return original(revised, *args, **kwargs)

    report_file = directory / "trial.json"
    try:
        if env.get("WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE", "100") != "100":
            raise RuntimeError("experimental source scale forbidden")
        # Existing native harness: production evaluator class, production pilot
        # observation and all READY/LAND/RESET assertions remain unchanged.
        with patch.object(native.subprocess, "Popen", side_effect=launch):
            native.run_case(home, env, "flight-reset")
        evidence, rows, world_hash, case = read_trial(directory)
        stages = read_webots_performance(performance)
        report.update(status="NATIVE_WITNESS_PASS", world_sha256=world_hash,
                      stages=stages, evidence=evidence,
                      sample_count=len(rows),
                      first_ms=rows[0]["time_ms"], last_ms=rows[-1]["time_ms"],
                      trace_sha256=digest(case / "native.trace"),
                      performance_sha256=digest(performance))
        return report, rows
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        report_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def common_phase(reports, traces):
    # Strictly the SAME observed simulation clock interval for every arm,
    # excluding launch/exit and never concatenating different physical epochs.
    first = max(max(t[0]["time_ms"] for t in traces), 1008)
    last = min(min(t[-1]["time_ms"] for t in traces), 4000)
    if last - first < 1000 or first % 8 or last % 8:
        raise RuntimeError("native runs lack a shared >=1-second stable interval")
    summaries = []
    for report, rows in zip(reports, traces):
        selected = [r for r in rows if first <= r["time_ms"] <= last]
        if len(selected) != (last-first)//8+1:
            raise RuntimeError("gap in matched native phase")
        steps = [r["step_wall_s"] * 1000 for r in selected]
        ticks = [r["tick_wall_s"] * 1000 for r in selected]
        cycles = [a+b for a,b in zip(steps,ticks)]
        elapsed = (selected[-1]["wall_elapsed_s"] -
                   selected[0]["wall_elapsed_s"] +
                   selected[0]["step_wall_s"] + selected[0]["tick_wall_s"])
        if elapsed <= 0:
            raise RuntimeError("invalid wall-clock envelope")
        summary = dict(arm=report["arm"], repeat=report["repeat"],
                       start_ms=first, end_ms=last, count=len(selected),
                       speed_x=round(len(selected)*.008/elapsed,6),
                       wall_ms_per_cycle=round(elapsed*1000/len(selected),6),
                       step_mean_ms=round(statistics.mean(steps),6),
                       evaluator_tick_mean_ms=round(statistics.mean(ticks),6),
                       cycle_p99_ms=round(percentile(cycles,.99),6),
                       step_p99_ms=round(percentile(steps,.99),6),
                       tick_p99_ms=round(percentile(ticks,.99),6))
        summaries.append(summary)
    pairs = []
    for repetition in (1,2,3):
        a = next(s for s in summaries if s["repeat"] == repetition and s["arm"]=="A")
        b = next(s for s in summaries if s["repeat"] == repetition and s["arm"]=="B")
        pairs.append(dict(pair=repetition,
                          speed_delta_x=round(b["speed_x"]-a["speed_x"],6),
                          speed_ratio=round(b["speed_x"]/a["speed_x"],6),
                          cycle_ms_saved=round(a["wall_ms_per_cycle"]-b["wall_ms_per_cycle"],6),
                          tick_ms_saved=round(a["evaluator_tick_mean_ms"]-b["evaluator_tick_mean_ms"],6)))
    return dict(phase_ms=[first,last],trials=summaries,pairs=pairs,
                paired_speed_ratio_median=round(statistics.median(p["speed_ratio"] for p in pairs),6),
                paired_cycle_ms_saved_median=round(statistics.median(p["cycle_ms_saved"] for p in pairs),6))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fast","realtime"), default="fast")
    args = parser.parse_args()
    home = Path(os.environ["WEBOTS_HOME"]).resolve()
    if (home/"resources/version.txt").read_text().strip() != "R2025a":
        raise RuntimeError("exact Webots R2025a required")
    if (not (home/"webots").is_file() or
            not (home/"bin/webots-bin").is_file()):
        raise RuntimeError("native Webots executable missing")
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Xvfb display required to render the A arm")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ, WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE="true",
               LP_NUM_THREADS="2", WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true")
    env.pop("WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE",None)
    env.pop("WEBOTS_EXPERIMENT_RENDER_DUTY",None)
    subprocess.run([sys.executable, "-m", "tools.grand_prix.prepare_route_runtime"],
                   cwd=ROOT, env=env, check=True,timeout=90)
    subprocess.run(["make","-C",str(ROOT/"controllers/grand_prix_route_flight"),"release"],
                   cwd=ROOT,env=env,check=True,timeout=180)
    subprocess.run(["make","-C",str(ROOT/"controllers/grand_prix_route_publisher_probe"),"release"],
                   cwd=ROOT,env=env,check=True,timeout=180)
    reports,traces=[],[]
    for arm,repetition in TRIALS:
        print("GP_RENDER_AB_START",args.mode,repetition,arm,flush=True)
        # Use the source's original --mode=fast if possible. For realtime,
        # patch only the command mode, not the pilot or evaluator.
        if args.mode == "realtime":
            original = subprocess.Popen
            def realtime(command,*argv,**kw):
                if "--mode=fast" in command:
                    command=[("--mode=realtime" if x=="--mode=fast" else x) for x in command]
                return original(command,*argv,**kw)
            with patch.object(native.subprocess,"Popen",side_effect=realtime):
                report,trace=run_trial(home,env,arm,repetition,args.mode)
        else:
            report,trace=run_trial(home,env,arm,repetition,args.mode)
        reports.append(report)
        traces.append(trace)
    if len({x["world_sha256"] for x in reports})!=1:
        raise RuntimeError("different native world across arms")
    result=common_phase(reports,traces)
    result.update(schema="gp-render-native-ab-diagnostic-v1",
                  status="MEASURED_ONLY",
                  scope="native pilot and historical evaluator test fixture; no Blockly pupil program",
                  mode=args.mode, display="Xvfb software OpenGL, A native 100%, B --no-rendering",
                  webots_sha256=digest(home/"bin/webots-bin"),
                  controller_sha256=digest(ROOT/"controllers/grand_prix_route_flight/grand_prix_route_flight"),
                  host=dict(os=platform.platform(),cpu=platform.processor(),
                            threads=os.cpu_count()),raw=[x["trace_sha256"] for x in reports],
                  limitations="No Windows Lenovo, pupil Blockly, visible hardware monitor FPS, or WREN draw/swap substage; Webots mainRendering covers main renderer only; flight-reset harness has diagnostic control cues")
    (OUTPUT/"summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("GP_RENDER_AB_RESULT",json.dumps(result,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
