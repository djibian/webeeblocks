#!/usr/bin/env python3
import json
import math
import re
import subprocess
import sys
from pathlib import Path

IMAGE = "cyberbotics/webots:R2025a-ubuntu22.04"
WORLD = "worlds/crazyflie_square_position.wbt"
CONTROLLER = "crazyflie_square_position"
RESULT = "ci-artifacts/crazyflie-primitive-B.txt"
PREFIX = "WEBEEBLOCKS_CF_PRIMITIVE_B"
CASES = [
    ("F-0.10", "forward", "0.10"),
    ("F-2.00", "forward", "2.00"),
    ("Y--90", "turn", "-90"),
    ("Y-180", "turn", "180"),
]


def render_world(source: str, kind: str, value: str, label: str) -> str:
    needle = f'  controller "{CONTROLLER}"\n'
    if needle not in source:
        raise RuntimeError("backend B controller field not found")
    args = f'  controllerArgs [\n    "{kind}"\n    "{value}"\n  ]\n'
    source = source.replace(needle, needle + args, 1)
    source = source.replace("WorldInfo {", "WorldInfo {\n  randomSeed 1\n  optimalThreadCount 1", 1)
    source = source.replace('name "Crazyflie"', 'name "Crazyflie"\n  synchronization TRUE', 1)
    return source.replace('experiment"', f'experiment — B edge {label}"', 1)


def parse_pairs(line: str) -> dict:
    if PREFIX not in line:
        raise RuntimeError(f"unexpected result line: {line}")
    pairs = dict(re.findall(r"([A-Za-z_]+)=([^\s]+)", line))
    if pairs.get("status") != "success":
        raise RuntimeError(f"non-success result: {line}")
    return pairs


def require_endpoint(pairs: dict, label: str, kind: str) -> None:
    required = [
        "kind", "command", "yaw_error_deg", "primitive_s",
        "residual_speed", "residual_yaw_rate", "residual_vz",
        "residual_altitude_error", "final_x", "final_y", "final_z", "final_yaw",
    ]
    if kind == "turn":
        required.append("signed_yaw_travel_deg")
    missing = [key for key in required if key not in pairs]
    if missing:
        raise RuntimeError(f"{label}: endpoint fields missing: {missing}")
    if float(pairs["residual_speed"]) >= 0.12:
        raise RuntimeError(f"{label}: residual horizontal speed not settled")
    if abs(float(pairs["residual_yaw_rate"])) >= 0.10:
        raise RuntimeError(f"{label}: residual yaw rate not settled")
    if abs(float(pairs["residual_vz"])) >= 0.15:
        raise RuntimeError(f"{label}: residual vertical speed not settled")
    if abs(float(pairs["residual_altitude_error"])) >= 0.05:
        raise RuntimeError(f"{label}: residual altitude error not settled")


def result_row(label: str, kind: str, pairs: dict) -> dict:
    require_endpoint(pairs, label, kind)
    command = float(pairs["command"])
    row = {
        "case": label,
        "kind": kind,
        "command": command,
        "termination": "SUCCESS",
        "duration_s": float(pairs["primitive_s"]),
        "yaw_error_deg": float(pairs["yaw_error_deg"]),
        "residual_speed_m_s": float(pairs["residual_speed"]),
        "residual_yaw_rate_rad_s": float(pairs["residual_yaw_rate"]),
        "residual_vz_m_s": float(pairs["residual_vz"]),
        "residual_altitude_error_m": float(pairs["residual_altitude_error"]),
        "final_x_m": float(pairs["final_x"]),
        "final_y_m": float(pairs["final_y"]),
        "final_z_m": float(pairs["final_z"]),
        "final_yaw_rad": float(pairs["final_yaw"]),
    }
    if kind == "forward":
        signed_error = float(pairs["longitudinal_error"])
        lateral = float(pairs["lateral_error"])
        achieved = command + signed_error
        row.update({
            "signed_error": signed_error,
            "parasitic_motion": lateral,
            "endpoint_overshoot": max(0.0, signed_error),
            "achieved": achieved,
        })
        if achieved <= 0.0:
            row["termination"] = "PATHOLOGICAL_WRONG_SIGN"
    else:
        signed_error = float(pairs["yaw_error_deg"])
        drift = float(pairs["drift_xy"])
        achieved = command + signed_error
        signed_yaw_travel = float(pairs["signed_yaw_travel_deg"])
        direction = 1.0 if command > 0.0 else -1.0
        yaw_travel_tolerance = max(15.0, 0.25 * abs(command))
        row.update({
            "signed_error": signed_error,
            "parasitic_motion": drift,
            "endpoint_overshoot": max(0.0, direction * signed_error),
            "achieved": achieved,
            "signed_yaw_travel_deg": signed_yaw_travel,
            "yaw_travel_error_deg": signed_yaw_travel - command,
        })
        if direction * signed_yaw_travel <= 0.0:
            row["termination"] = "PATHOLOGICAL_WRONG_TURN_DIRECTION"
        elif abs(signed_yaw_travel - command) > yaw_travel_tolerance:
            row["termination"] = "PATHOLOGICAL_YAW_TRAVEL"
    return row


def run_case(root: Path, artifacts: Path, label: str, kind: str, value: str) -> dict:
    source = (root / WORLD).read_text(encoding="utf-8")
    generated = root / "worlds" / f".ci-b-edge-{label}.wbt"
    generated.write_text(render_world(source, kind, value, label), encoding="utf-8")
    result_path = root / RESULT
    result_path.unlink(missing_ok=True)
    log_path = artifacts / f"{label}.log"
    relative_world = generated.relative_to(root).as_posix()
    inner = (
        "timeout -k 5s 90s xvfb-run -a webots --stdout --stderr --batch --mode=fast "
        f"/workspace/{relative_world}"
    )
    command = [
        "docker", "run", "--rm",
        "-e", "LIBGL_ALWAYS_SOFTWARE=true",
        "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
        "-v", f"{root}:/workspace",
        "-w", "/workspace",
        IMAGE,
        "bash", "-lc", inner,
    ]
    try:
        completed = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=105)
        log_path.write_text(completed.stdout, encoding="utf-8")
        if completed.returncode != 0:
            return {"case": label, "kind": kind, "command": float(value),
                    "termination": f"PATHOLOGICAL_WEBOTS_EXIT_{completed.returncode}"}
        if "ERROR:" in completed.stdout or "WEBEEBLOCKS_CF_POSITION_FAILED" in completed.stdout:
            return {"case": label, "kind": kind, "command": float(value),
                    "termination": "PATHOLOGICAL_CONTROLLER_FAILURE"}
        if not result_path.is_file() or result_path.stat().st_size == 0:
            return {"case": label, "kind": kind, "command": float(value),
                    "termination": "PATHOLOGICAL_MISSING_RESULT"}
        pairs = parse_pairs(result_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        return result_row(label, kind, pairs)
    except subprocess.TimeoutExpired:
        return {"case": label, "kind": kind, "command": float(value),
                "termination": "PATHOLOGICAL_HARNESS_TIMEOUT"}
    except Exception as exc:
        return {"case": label, "kind": kind, "command": float(value),
                "termination": "PATHOLOGICAL_INVALID_RESULT", "detail": str(exc)}
    finally:
        generated.unlink(missing_ok=True)


def write_markdown(path: Path, rows: list[dict]) -> None:
    lines = [
        "# Backend B edge characterization",
        "",
        "No PID/gain/cap/navigation tuning. Each case is a fresh Webots R2025a process.",
        "`endpoint_overshoot` is overshoot remaining at the common stabilized endpoint; transient peak overshoot is not instrumented by this gate.",
        "For turns, `signed_yaw_travel_deg` is the unwrapped yaw actually traversed from TURN start through the stabilized endpoint.",
        "",
        "| Case | Kind | Command | Termination | Achieved | Signed err | Yaw travel | Parasitic motion | Endpoint overshoot | Alt err | Time (s) |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        def f(key: str) -> str:
            value = row.get(key)
            return "N/A" if value is None else f"{value:.6f}"
        lines.append(
            f"| {row['case']} | {row['kind']} | {row['command']:.3f} | {row['termination']} | "
            f"{f('achieved')} | {f('signed_error')} | {f('signed_yaw_travel_deg')} | "
            f"{f('parasitic_motion')} | {f('endpoint_overshoot')} | "
            f"{f('residual_altitude_error_m')} | {f('duration_s')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    artifacts = root / "ci-artifacts" / "crazyflie-b-edge-matrix"
    artifacts.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, kind, value in CASES:
        print(f"=== B / {label} ===", flush=True)
        row = run_case(root, artifacts, label, kind, value)
        rows.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)

    payload = {"rows": rows}
    (artifacts / "matrix.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(artifacts / "matrix.md", rows)
    print((artifacts / "matrix.md").read_text(encoding="utf-8"), flush=True)

    pathological = [row for row in rows if row["termination"] != "SUCCESS"]
    if pathological:
        (artifacts / "failure.txt").write_text(json.dumps(pathological, indent=2) + "\n", encoding="utf-8")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
