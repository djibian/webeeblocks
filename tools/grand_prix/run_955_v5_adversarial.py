#!/usr/bin/env python3
"""Native product-binary R2025a witness; never mutates compiled route C.

Every tested world executes the same release binary assembled from this exact
HEAD. A separate product-compiled read-only GP_PRODUCT_SAMPLE observer captures
real Supervisor contacts, flight phase, native z/vz and touchdown latch.
The production evaluator and simulator physics are not replaced or patched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.launch_linux import (
    ensure_webots_assets, ensure_blockly_assets, webots_home)
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.route_courses_v2 import reference_course

FLIGHT = ROOT / "controllers/grand_prix_route_flight"
COURSES = {
    "route_h1":1, "route_h3":9, "route_h3_contact":9,
    "route_h3_low":9, "route_lh":5, "outcome_replay_h1":1,
}
SCENARIOS = (
    "primitives", "ceiling", "ceiling_safe_ascent", "ceiling_large_ascent",
    "ceiling_takeoff", "route_lh", "route_h1", "route_h3",
    "route_h3_contact", "route_h3_low", "stop", "reset", "deadline",
    "env_02_allow","env_03_edge","env_04_edge","env_05_edge",
    "env_05_refuse","env_04_refuse","env_05_vplus_allow","env_05_vplus_refuse",
    "env_vplus_small_rebound","env_vplus_large_rebound",
    "outcome_replay_h1")
FIELD = re.compile(r"([a-z][a-z0-9_]*)=([^\s]+)")
FLOATS = ("t","x","y","z","vz","yaw","ref","target")
NATIVE_TOUCH = re.compile(r"TRACE LAND_TOUCHDOWN time=([0-9.]+)")
NATIVE_READY = re.compile(r"GP_U_LAND_GROUND_READY t=([0-9.]+)")
NATIVE_ACK = "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1"


def digest(path:Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_sha(expected:str):
    got = subprocess.check_output(["git","rev-parse","HEAD"],text=True,cwd=ROOT).strip()
    if not re.fullmatch("[a-f0-9]{40}",expected) or expected!=got:
        raise RuntimeError(f"exact-HEAD mismatch: expected {expected}, got {got}")
    if subprocess.check_output(["git","status","--porcelain","--untracked-files=no"],
                               text=True,cwd=ROOT).strip():
        raise RuntimeError("dirty tracked source")
    return got


def compile_native(home:Path):
    env=dict(os.environ,WEBOTS_HOME=str(home))
    script = ROOT / "tools/grand_prix/prepare_route_runtime.py"
    subprocess.run(["python3",str(script)],cwd=ROOT,env=env,check=True,timeout=120)
    subprocess.run(["make","-C",str(FLIGHT),"clean"],cwd=ROOT,env=env,check=True,timeout=120)
    subprocess.run(["python3",str(script)],cwd=ROOT,env=env,check=True,timeout=120)
    subprocess.run(["make","-C",str(FLIGHT),"release"],cwd=ROOT,env=env,check=True,timeout=180)
    binary=FLIGHT / "grand_prix_route_flight"
    source=FLIGHT / "build/runtime_u.c"
    compiled=source.read_text()
    for marker in (
        "GP_PRODUCT_SAMPLE",
        "land_touchdown && gp_land_contact_since",
        "GP_CEILING_PREFLIGHT_V1 command=VERTICAL",
        "GP_CEILING_PREFLIGHT_V1 command=TAKEOFF",
        "gp_route_takeoff_next(&gp_route_takeoff,",
        "gp_u_deadline(now, gp_pose_confirmed)",
        "gp_route_observe_native("
    ):
        if marker not in compiled:
            raise RuntimeError("missing product-native guard/witness: "+marker)
    return {"product_binary_sha256":digest(binary),
            "generated_source_sha256":digest(source),
            "native_evaluator_sha256":digest(ROOT/"controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py"),
            "shared_runtime_sha256":digest(ROOT/"controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c")}


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


def stop_tree(p):
    if p is None or p.poll() is not None:
        return
    try: os.killpg(p.pid,signal.SIGTERM)
    except ProcessLookupError: return
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try: os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        p.wait(timeout=5)


def analyze_native(log:str, events:list[dict], scenario:str):
    lines=log.splitlines()
    rows=[]
    for line in lines:
        idx=line.find("GP_PRODUCT_SAMPLE ")
        if idx<0:continue
        tokens=dict(FIELD.findall(line[idx+len("GP_PRODUCT_SAMPLE "):]))
        r={k:float(tokens[k]) for k in FLOATS}
        r["cmd"]=tokens["cmd"]
        for k in ("contact","touchdown","airborne"):r[k]=int(tokens[k])
        if not all(math.isfinite(r[k]) for k in FLOATS):raise ValueError("non-finite raw sample")
        if r["contact"] not in (-1,0,1):raise ValueError("invalid native contact")
        if rows and r["t"]<=rows[-1]["t"]:raise ValueError("non-monotonic native samples")
        rows.append(r)
    if not rows:raise ValueError("no genuine GP_PRODUCT_SAMPLE in exact binary")
    paired=[]
    last_touch=None
    ready_unpaired=[]
    for line in lines:
        t=NATIVE_TOUCH.search(line)
        if t:
            last_touch=float(t.group(1))
        l=NATIVE_READY.search(line)
        if l:
            ack=float(l.group(1))
            if last_touch is None or last_touch>ack+1e-7:
                ready_unpaired.append(ack)
            else:
                paired.append({"touchdown_s":last_touch,"ready_s":ack,
                               "elapsed_s":round(ack-last_touch,6)})
            last_touch=None
    trace_land=sum(NATIVE_ACK in line for line in lines)
    ack_from_wwi=sum(e.get("kind")=="response" and
             isinstance(e.get("value"),str) and
             " OK" in e["value"] for e in events)
    # Sampled contact may alternate; never equate missing observations to contact.
    contacts=[r["contact"] for r in rows if r["cmd"]=="LAND"]
    transitions=sum(x!=y for x,y in zip(contacts,contacts[1:]))
    pos_landing=[e for e in events if e.get("kind")=="route-native-outcome"
                and isinstance(e.get("value"),dict) and
                e["value"].get("status")=="achieved"]
    neg=[x.strip()[-550:] for x in lines if "GP_ROUTE_EVALUATOR_CLOSED" in x]
    n_ready=sum("GP_U_LAND_GROUND_READY " in x for x in lines)
    verdict={"status":"RAW_PRODUCT_NATIVE_NOT_V5_PASS","samples":len(rows),
       "modes":list(dict.fromkeys(r["cmd"] for r in rows)),
       "max_altitude_m":max(r["z"] for r in rows),
       "min_ceiling_clearance_m":1.165-max(r["z"] for r in rows),
       "max_abs_vz_m_s":max(abs(r["vz"]) for r in rows),
       "touchdown_ready_pairs":paired,
       "unpaired_land_ready":ready_unpaired,
       "native_landed_count":trace_land,
       "ready_count":n_ready,
       "land_ack_not_before_true_touchdown":(
           len(ready_unpaired)==0 and len(paired)==n_ready and trace_land==n_ready),
       "land_contact_transitions_32ms":transitions,
       "land_contact_samples_1":contacts.count(1),
       "land_contact_samples_0":contacts.count(0),
       "land_contact_unknown":contacts.count(-1),
       "land_touchdown_latched_samples":sum(r["touchdown"]==1 for r in rows if r["cmd"]=="LAND"),
       "positive_native_oracle":bool(pos_landing),
       "oracle_revocations":neg,
       "max_native_sample_gap_s":max((b["t"]-a["t"] for a,b in zip(rows,rows[1:])),default=0),
       "unexpected_wwi_transport_error":any(e.get("kind") in ("wall-timeout","socket-error")
                for e in events),
       "scenario_completed":any(e.get("kind")=="scenario-finished" for e in events),
       "native_response_count":ack_from_wwi,
    }
    if scenario in ("route_lh","route_h1","route_h3"):
        verdict["qualified"]=(verdict["scenario_completed"] and
           verdict["positive_native_oracle"] and
           verdict["land_ack_not_before_true_touchdown"])
    elif scenario in ("route_h3_contact","route_h3_low"):
        expected = "envelope-contact" if scenario.endswith("contact") else "low-outside-zone"
        verdict["expected_negative_reason"]=expected
        verdict["qualified"]=(verdict["scenario_completed"] and any(
            "reason="+expected in x for x in neg) and
            verdict["land_ack_not_before_true_touchdown"])
    elif scenario.startswith("env_"):
        request=next((e["value"] for e in events
            if e.get("kind")=="envelope-request" and
            isinstance(e.get("value"),dict)),{})
        decision=next((e["value"] for e in events
            if e.get("kind")=="envelope-result" and
            isinstance(e.get("value"),dict)),{})
        amount=request.get("amplitude_m")
        expected=request.get("expected")
        verdict["requested_amplitude_m"]=amount
        verdict["expected_admission"]=expected
        verdict["observed_admission"]=decision.get("verdict")
        guard_lines=[line for line in lines
            if "GP_CEILING_PREFLIGHT_V1 command=VERTICAL" in line]
        if guard_lines:
            g=dict(FIELD.findall(guard_lines[-1]))
            if all(k in g for k in ("z","vz","target","top","headroom","ceiling")):
                vals={k:float(g[k]) for k in ("z","vz","target","top","headroom","ceiling")}
                verdict["exact_native_preflight"]=vals
                v=max(vals["vz"],0)
                predicted=.095 + .30*amount + .064*v + v*v/.50
                verdict["preflight_formula_error_m"]=abs(vals["headroom"]-predicted)
                verdict["target_minus_admissible_m"]=vals["target"]-vals["top"]
        # Accepted VERTICAL up is observed at the first C physics control
        # sample with the new reference above the actual z (no C injection).
        upward=[row for row in rows if row["cmd"]=="VERTICAL" and
                row["target"] > row["z"] + .08]
        if upward:
            witness=upward[0]
            vz=max(0,witness["vz"])
            amplitude_margin=.095+.30*amount
            estimated_top=1.165-(amplitude_margin+.064*vz+vz*vz/.50)
            verdict["accepted_first_native_upward_sample"]={
                "t_s":witness["t"],"z_m":witness["z"],"vz_m_s":witness["vz"],
                "target_m":witness["target"],
                "estimated_top_m":estimated_top,
                "estimated_target_minus_top_m":witness["target"]-estimated_top}
        sample=verdict.get("exact_native_preflight") or (
            verdict.get("accepted_first_native_upward_sample") or {})
        native_vz=sample.get("vz",sample.get("vz_m_s",None))
        verdict["upward_velocity_at_admission_or_first_native_sample_m_s"]=native_vz
        positive_required=request.get("positive_vz_required",False)
        verdict["positive_vz_witness"]= (
            isinstance(native_vz,(int,float)) and native_vz>.020)
        qualifies=(verdict["scenario_completed"] and
            isinstance(amount,(int,float)) and .10<=amount<=.50 and
            (expected=="either" or decision.get("verdict")==("allowed" if expected=="allow" else "refused")) and
            verdict["min_ceiling_clearance_m"]>=0 and
            not any("reason=altitude" in line and "GP_ROUTE_EVALUATOR_CLOSED" in line
                for line in lines) and
            verdict["land_ack_not_before_true_touchdown"] and n_ready>=1 and
            not verdict["unexpected_wwi_transport_error"] and
            (not positive_required or verdict["positive_vz_witness"]))
        if expected=="allow":
            qualifies=qualifies and bool(upward) and not guard_lines
        else:
            qualifies=(qualifies and len(guard_lines)==1 and
                verdict.get("preflight_formula_error_m",float("inf"))<1e-6 and
                verdict.get("target_minus_admissible_m",-1)>0)
        verdict["qualified"]=bool(qualifies)
    elif scenario=="outcome_replay_h1":
        positive=[e for e in events if e.get("kind")=="old-positive-attested"
                  and isinstance(e.get("value"),dict) and
                  e["value"].get("status")=="achieved"]
        refusal=[e["value"] for e in events
                 if e.get("kind")=="old-success-probe-refused" and
                 isinstance(e.get("value"),dict)]
        accepted_old=[e for e in events if e.get("kind")=="old-success-probe"
            and isinstance(e.get("value"),dict) and
            isinstance(e["value"].get("returned"),dict) and
            e["value"]["returned"].get("status")=="achieved"]
        admissions=[re.search(r"GP_U_ADMISSION attempt=(\d+) start_ms=(\d+)",line)
            for line in lines if "GP_U_ADMISSION" in line]
        admissions=[(int(m.group(1)),int(m.group(2))) for m in admissions if m]
        first_epoch_revoked=any(
            "GP_ROUTE_EVALUATOR_CLOSED attempt=1" in line and
            "reason=invalid-native-observation" in line for line in lines)
        verdict["prior_native_achieved_observed"]=bool(positive)
        verdict["old_achieved_replayed"]=bool(accepted_old)
        verdict["new_attempt_admission_records"]=admissions
        verdict["first_attempt_native_observation_revoked"]=first_epoch_revoked
        verdict["old_success_denials"]=refusal
        verdict["qualified"]=(verdict["scenario_completed"] and
          verdict["positive_native_oracle"] and bool(positive) and
          first_epoch_revoked and not accepted_old and
          len(refusal)==2 and
          {e.get("name") for e in refusal}=={
             "immediately-after-reset","after-new-attempt-admitted"} and
          len(admissions)>=2 and admissions[0][0]!=admissions[1][0] and
          verdict["land_ack_not_before_true_touchdown"] and
          n_ready>=1 and not verdict["unexpected_wwi_transport_error"])
    elif scenario in ("stop","deadline"):
        verdict["qualified"]=(verdict["scenario_completed"] and
            verdict["land_ack_not_before_true_touchdown"] and n_ready>=1)
    elif scenario=="primitives":
        verdict["qualified"]=(verdict["scenario_completed"] and n_ready>=1 and
            verdict["land_ack_not_before_true_touchdown"] and
            any(e.get("kind")=="step-ok" and
               isinstance(e.get("value"),dict) and
               e["value"].get("name")=="strict-reset-after-land" for e in events))
    elif scenario=="reset":
        verdict["qualified"]=(verdict["scenario_completed"] and
            any(e.get("kind")=="strict-airborne-reset-refused" and
            e.get("value")=="LANDING_UNCONFIRMED" for e in events))
    elif scenario in ("ceiling","ceiling_large_ascent","ceiling_takeoff","ceiling_safe_ascent"):
        code="INVALID_TAKEOFF" if scenario=="ceiling_takeoff" else "VERTICAL_LIMIT"
        refused=any(e.get("kind") in ("preventive-ceiling-refusal",
            "preventive-large-vertical-refusal","preventive-takeoff-refusal")
            and e.get("value")==code for e in events)
        allowed=any(e.get("kind")=="step-ok" and
            isinstance(e.get("value"),dict) and
            e["value"].get("name")=="vertical-safe-up-0.10" for e in events)
        verdict["qualified"]=(verdict["scenario_completed"] and
             verdict["min_ceiling_clearance_m"]>=0 and
             verdict["land_ack_not_before_true_touchdown"] and n_ready>=1 and
             (allowed if scenario=="ceiling_safe_ascent" else refused))
    else:verdict["qualified"]=False
    return verdict,rows


def run_one(home:Path,scenario:str,output:Path,sha:str):
    course=reference_course(COURSES.get(scenario,5))
    out=output/scenario
    out.mkdir(parents=True,exist_ok=False)
    world=ROOT/"worlds"/("ci_gp_product_"+uuid.uuid4().hex[:16]+".wbt")
    scene=active_course_world(course).replace(
        "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/","webots://")
    world.write_text(scene)
    (out/"world.wbt").write_text(scene)
    logs=out/"webots.log";events_file=out/"events.jsonl";node_log=out/"node.log"
    webots=node=None
    status={"scenario":scenario,"course":course.identifier,
            "course_index":COURSES.get(scenario,5),"exact_source_sha":sha,
            "world_sha256":digest(out/"world.wbt"),"oracle_modified":False}
    try:
        with tempfile.TemporaryDirectory(prefix="wb-gp-product-") as tmp:
            env=dict(os.environ,WEBOTS_HOME=str(home),WBB_GP_PRODUCT_TRACE="1",
              LIBGL_ALWAYS_SOFTWARE="true",
              WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true")
            for key,part in (("XDG_CONFIG_HOME","config"),
                             ("XDG_CACHE_HOME","cache"),("XDG_RUNTIME_DIR","runtime")):
                sub=Path(tmp)/part;sub.mkdir(mode=0o700);env[key]=str(sub)
            port=available_port()
            cmd=["xvfb-run","-a",str(home/"webots"),"--batch","--mode=fast",
                "--no-rendering","--minimize","--stdout","--stderr",
                f"--port={port}",str(world)]
            with logs.open("w") as fp,node_log.open("w") as nodefp:
                webots=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=fp,
                      stderr=subprocess.STDOUT,start_new_session=True)
                deadline=time.monotonic()+70
                while time.monotonic()<deadline:
                    if webots.poll() is not None:
                        raise RuntimeError("Webots exited before native READY")
                    if "WEBEEBLOCKS_RUNTIME_V2 READY" in logs.read_text(errors="replace"):
                        break
                    time.sleep(.20)
                else:raise RuntimeError("no native runtime READY")
                node=subprocess.Popen(["node",str(ROOT/"tools/grand_prix/v5_native_adversarial_stimulus.js"),
                        str(port),scenario,str(events_file)],cwd=ROOT,env=env,
                        stdout=nodefp,stderr=subprocess.STDOUT,start_new_session=True)
                status["stimulus_exit"]=node.wait(timeout=630)
    except Exception as e:
        status["error"]=type(e).__name__+": "+str(e)
    finally:
        stop_tree(node);stop_tree(webots);world.unlink(missing_ok=True)
    raw=logs.read_text(errors="replace") if logs.exists() else ""
    events=[]
    if events_file.exists():
        for line in events_file.read_text().splitlines():
            try:events.append(json.loads(line))
            except Exception as e:status["event_parse_error"]=str(e)
    status["events"]=events
    try:
        observed,rows=analyze_native(raw,events,scenario)
        status.update(observed)
        # The native logs are primary evidence; sample data remain unmodified.
        import csv
        with (out/"native-product-contacts.csv").open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader();writer.writerows(rows)
    except Exception as e:
        status["qualified"]=False
        status["trace_error"]=type(e).__name__+": "+str(e)
    status["webots_log_sha256"]=digest(logs) if logs.exists() else None
    status["events_sha256"]=digest(events_file) if events_file.exists() else None
    (out/"summary.json").write_text(json.dumps(status,indent=2,sort_keys=True)+"\n")
    print("GP_PRODUCT_NATIVE "+json.dumps({k:status.get(k) for k in
            ("scenario","qualified","stimulus_exit","max_altitude_m",
             "land_ack_not_before_true_touchdown","ready_count","trace_error",
             "error")}),flush=True)
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head",required=True)
    parser.add_argument("--webots-home")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--scenarios",nargs="+",choices=SCENARIOS,required=True)
    args=parser.parse_args()
    sha=check_sha(args.expected_head)
    home=webots_home(args.webots_home)
    if (home/"resources/version.txt").read_text().strip()!="R2025a":
        raise RuntimeError("wrong Webots release")
    ensure_webots_assets(home);ensure_blockly_assets()
    build=compile_native(home)
    EXPECTED_PRODUCT_BINARY="88288e0f14c10e4a5d75ec55d08f9b25f9b35b2310955c16fa1aef24f3894aa8"
    EXPECTED_GENERATED_SOURCE="9e93b1771989ddbc7ac50977d6fdc0293a3c439a3c48a1101c8ba934a42264ed"
    if (build["product_binary_sha256"]!=EXPECTED_PRODUCT_BINARY or
        build["generated_source_sha256"]!=EXPECTED_GENERATED_SOURCE):
        raise RuntimeError("not the exact qualified PR955 product binary: "+json.dumps(build))
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    results=[]
    for scenario in args.scenarios:
        results.append(run_one(home,scenario,output,sha))
    report={"provenance":sha,"build":build,"results":results,
        "safety_relaxation":False,"oracle_modified":False,
        "full_pedagogical_acceptance":False,
        "all_qualified":all(x.get("qualified") is True for x in results)}
    (output/"index.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("GP_PRODUCT_NATIVE_REPORT "+json.dumps({
        "head":sha,"binary":build["product_binary_sha256"],
        "qualified":report["all_qualified"],"total":len(results)}),flush=True)
    return 0 if report["all_qualified"] else 2

if __name__=="__main__":
    raise SystemExit(main())
