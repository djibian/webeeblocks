"""One preregistered browser timing case; workflow stops the series on first refusal."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/ci"), str(ROOT)]
import run_progression_autonomous_mission as runner


def validate_delay(log, steps):
    begins = re.findall(r" RESET_DEFER_BEGIN id=(\d+) time=([0-9.]+) steps=(\d+)", log)
    releases = re.findall(r" RESET_DEFER_RELEASE id=(\d+) time=([0-9.]+)", log)
    if len(begins) != 1 or len(releases) != 1:
        raise ValueError("missing/duplicate deferred receipt")
    identifier, begin, recorded_steps = begins[0]
    release_id, end = releases[0]
    if (identifier != release_id or int(recorded_steps) != steps or
            abs(float(end) - float(begin) - steps * .032) > 1e-8):
        raise ValueError("wrong message or native delay")
    resets = re.findall(r" RESET_PHASE_BEGIN id=(\d+) time=([0-9.]+)", log)
    if len(resets) < 7 or resets[6][0] != identifier or abs(float(resets[6][1]) - float(end)) > 1e-8:
        raise ValueError("deferred message was not the seventh actual RESET receipt")
    return {"id": int(identifier), "incoming_time": float(begin), "receipt_time": float(end), "steps": steps}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, choices=(1, 8, 16), required=True)
    steps = parser.parse_args().steps
    out = ROOT / "ci-artifacts" / f"progression-reset-phase-delay{steps}"
    if out.exists() or runner.ARTIFACT_ROOT.exists():
        raise RuntimeError("refuse to erase an earlier acquisition")
    subprocess.run([sys.executable, str(Path(__file__).with_name("test_defer.py"))], check=True)
    os.environ["WEBEEBLOCKS_RESET_PHASE_TRACE"] = "1"
    os.environ["WEBEEBLOCKS_RESET_PHASE_DEFER_STEPS"] = str(steps)
    result = 1
    error = None
    try:
        result = runner.main()
    except Exception as exc:
        error = repr(exc)
    finally:
        if runner.ARTIFACT_ROOT.exists():
            shutil.move(str(runner.ARTIFACT_ROOT), str(out))
        else:
            out.mkdir(parents=True)
        if (out / "sha256.json").exists():
            (out / "sha256.json").rename(out / "acquisition-sha256.json")
        config = {"scope": "experimental timing intervention, not historical reconstruction or repair",
                  "steps": steps, "original_probe_exit": result, "exception": error,
                  "rule": "one case at each 1/8/16 steps; retain all; stop series on first refusal"}
        (out / "delay-case.json").write_text(json.dumps(config, indent=2) + "\n")
        try:
            delay = validate_delay((out / "webots.log").read_text(), steps)
            (out / "delay-receipt.json").write_text(json.dumps(delay, indent=2) + "\n")
        except Exception as exc:
            result = 1
            (out / "delay-error.txt").write_text(str(exc) + "\n")
        for name in ("campaign.py", "defer.py"):
            shutil.copyfile(Path(__file__).with_name(name), out / name)
        (out / "sha256.json").write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir() if p.is_file() and p.name != "sha256.json"}, indent=2) + "\n")
    return result


if __name__ == "__main__":
    sys.exit(main())
