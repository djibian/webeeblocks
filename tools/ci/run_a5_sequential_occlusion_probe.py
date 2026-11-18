#!/usr/bin/env python3
"""A5 PRIVATE: real Webots Multi-ranger around two successive Ls, no pupil or motors."""
from pathlib import Path
import hashlib, json, math, os, re, signal, subprocess, sys, time
import prepare_classroom_altitude_scene_ack as classroom

ROOT=classroom.ROOT
ARTIFACT=ROOT/"ci-artifacts/a5-sequential-occlusion"
MARKER="# WEBEEBLOCKS_A5_SEQUENTIAL_OCCLUSION_CI_ONLY"
SOURCE='controller "crazyflie_classroom_v2"'
PROBE='controller "progression_a5_seq_occ_probe"'
PHASES=(("before_far",.40,0.),("before_near",.70,0.),
        ("before_peek",.60,.45),  # accessible ahead of the first L
        ("before_corner",.98,.45),  # clearance near but before L1 plane
        ("after_far",2.00,.60),("after_near",2.30,.60))
CHANNELS=("front","back","left","right","up")
RAYS=re.compile(
    r"(?m)^A5_SEQ_OCC_RAYS variant=([AB]) "
    r"phase=(before_far|before_near|before_peek|before_corner|after_far|after_near) "
    r"front=([0-9.]+) back=([0-9.]+) left=([0-9.]+) "
    r"right=([0-9.]+) up=([0-9.]+) "
    r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=([0-9.]+)$")
DONE=re.compile(r"(?m)^A5_SEQ_OCC_DONE variant=([AB]) samples=6 "
                r"native_multiranger=true supervisor_only=true "
                r"motorized=false pupil_pass=false$")
FATAL="A5_SEQ_OCC_FATAL"

def scene_file(v):
    if type(v) is not str or v not in ("A","B"):
        raise ValueError("only private variants A and B")
    return ROOT/f"worlds/scenes/reactive-L-sequential-occlusion-{v.lower()}-private.wbo"

def compose(v,scene=None):
    if type(v) is not str or v not in ("A","B"):
        raise ValueError("unsupported private variant")
    base=classroom.compose(classroom.SOURCE.read_text(encoding="utf8"))
    body=scene_file(v).read_text(encoding="utf8") if scene is None else scene
    other="B" if v=="A" else "A"
    if (base.count(SOURCE)!=1 or base.count(classroom.MARKER)!=1 or
        base.count('Floor { size 4 4 }')!=1 or
        base.count('name "Crazyflie WebeeBlocks"')!=1 or
        body.count(f"DEF WEBEEBLOCKS_A5_SEQ_OCC_{v}_SCENE Group")!=1 or
        f"WEBEEBLOCKS_A5_SEQ_OCC_{other}_SCENE" in body or
        body.count(" Solid {")!=7 or body.count("boundingObject Box")!=7 or
        any(f"DEF A5_SEQ_{name} Solid" not in body
            for name in ("L1_POST","L1_ARM","L2_POST","L2_ARM",
                         "CORRIDOR_POS","CORRIDOR_NEG","TERMINAL")) or
        "Robot {" in body or 'controller "' in body or
        "WEBEEBLOCKS_LEGACY_SCENE" in body):
        raise ValueError("untrusted original classroom world or collision L")
    base=base.replace(SOURCE,PROBE,1).replace(classroom.MARKER,MARKER,1)
    base=base.replace('Floor { size 4 4 }','Floor { size 8 4 }',1)
    result=base.rstrip()+"\n"+body.rstrip()+"\n"
    if result.count(PROBE)!=1 or result.count(MARKER)!=1 or \
       SOURCE in result or 'controller "crazyflie_runtime_v2"' in result:
        raise ValueError("native test-only controller not unique")
    return result

def validate_observations(data):
    """Pure fail-closed comparator; synthetic arrays here are NOT Webots evidence."""
    if set(data)!={"A","B"}:raise AssertionError("missing actual variant")
    for v in ("A","B"):
        if set(data[v])!={p for p,_,_ in PHASES}:
            raise AssertionError("missing/duplicate native phase")
        for phase,_,_ in PHASES:
            rays=data[v][phase]
            if set(rays)!=set(CHANNELS) or any(
                type(rays[ch]) not in (int,float) or
                not math.isfinite(rays[ch]) or not 0<=rays[ch]<=2.001
                for ch in CHANNELS):
                raise AssertionError("missing/invalid genuine range channel")
    for phase in ("before_far","before_near","before_peek","before_corner"):
        for ch in CHANNELS:
            delta=abs(data["A"][phase][ch]-data["B"][phase][ch])
            if delta>.025:
                raise AssertionError(f"L2 information leaks before L1: {phase}/{ch} {delta}")
    for phase in ("after_far","after_near"):
        a=data["A"][phase]["front"]
        b=data["B"][phase]["front"]
        if not (.05<a<1.9 and .05<b<1.9 and .30<=b-a<=.80):
            raise AssertionError(f"L2 not discriminable after L1: {phase} {a},{b}")
    return True

def run_one(v):
    folder=ARTIFACT/v
    folder.mkdir(parents=True,exist_ok=True)
    wbt=ROOT/f"worlds/ci_a5_seq_occ_{v.lower()}.wbt"
    project=ROOT/f"worlds/.ci_a5_seq_occ_{v.lower()}.wbproj"
    world=compose(v)
    if wbt.exists() or project.exists() or wbt.is_symlink() or project.is_symlink():
        raise FileExistsError("native private WBT/proj exists")
    log=folder/"webots.log"
    process=None
    try:
        wbt.write_text(world,encoding="utf8")
        project.write_text("Webots Project File version R2025a\n"
                           "robotWindow: Crazyflie WebeeBlocks\n",encoding="utf8")
        (folder/"world.sha256").write_text(
            hashlib.sha256(world.encode()).hexdigest()+"\n",encoding="utf8")
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf8") as stream:
            process=subprocess.Popen(
                ["timeout","-k","5s","85s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(wbt)],
                cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline=time.monotonic()+78
            while time.monotonic()<deadline:
                stream.flush()
                text=log.read_text(encoding="utf8",errors="replace")
                if FATAL in text or DONE.search(text) or process.poll() is not None:break
                time.sleep(.25)
    finally:
        if process:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait(timeout=5)
        if wbt.exists():
            if wbt.is_symlink() or wbt.read_text(encoding="utf8")!=world:
                raise RuntimeError("refuse mutated private WBT cleanup")
            wbt.unlink()
        if project.exists():
            data=project.read_text(encoding="utf8")
            if project.is_symlink() or len(data)>65536 or not data.startswith(
                "Webots Project File version R2025a\n"):
                raise RuntimeError("refuse altered Webots project cleanup")
            project.unlink()
    text=log.read_text(encoding="utf8",errors="replace")
    rows=RAYS.findall(text)
    if FATAL in text or DONE.findall(text)!=[v] or len(rows)!=len(PHASES):
        print(text[-6000:],file=sys.stderr,flush=True)
        raise AssertionError("real Webots sensor evidence absent")
    observed={}
    for row,(phase,x,y) in zip(rows,PHASES):
        actual,label,*values=row
        read=list(map(float,values))
        if actual!=v or label!=phase or len(read)!=8:
            raise AssertionError("unexpected native range identity/order")
        px,py,pz=read[5:]
        if not all(map(math.isfinite,(px,py,pz))) or \
           abs(px-x)>.035 or abs(py-y)>.035 or abs(pz-.5)>.09:
            raise AssertionError("native XYZ pose mismatch")
        observed[phase]=dict(zip(CHANNELS,read[:5]))
    (folder/"samples.json").write_text(json.dumps({
        "variant":v,"rays":observed,"original_crazyflie":True,
        "motorized":False,"pupil_wbb":False,"mission_oracle":False},
        sort_keys=True,indent=2)+"\n",encoding="utf8")
    return observed

def main():
    evidence={v:run_one(v) for v in ("A","B")}
    validate_observations(evidence)
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "native_five_rays":True,
        "same_rays_at_two_selected_early_poses":True,
        "later_front_discriminates_second_L":True,
        "no_global_occlusion_claim":True,
        "motorized":False,"pupil_wbb":False,"mission_oracle":False
    },sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("A5_SEQ_OCC_NATIVE_PASS five_rays=true early=4 later=2 "
          "motorized=false pupil_wbb=false",flush=True)

if __name__=="__main__":main()
