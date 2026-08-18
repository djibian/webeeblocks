#!/usr/bin/env python3
import json
import math
import re
import subprocess
import sys
from pathlib import Path

IMAGE = "cyberbotics/webots:R2025a-ubuntu22.04"
SCENARIOS = [
    ("nominal", 0.0, 0.0),
    ("yaw_plus_5", 0.0, math.radians(5.0)),
    ("yaw_minus_5", 0.0, math.radians(-5.0)),
    ("y_plus_2cm", 0.02, 0.0),
    ("y_minus_2cm", -0.02, 0.0),
]
BACKENDS = {
    "A": {
        "world": "worlds/crazyflie_square.wbt",
        "result": "ci-artifacts/crazyflie-square-result.txt",
        "prefix": "WEBEEBLOCKS_CF_SQUARE_RESULT",
    },
    "B": {
        "world": "worlds/crazyflie_square_position.wbt",
        "result": "ci-artifacts/crazyflie-square-position-result.txt",
        "prefix": "WEBEEBLOCKS_CF_POSITION_RESULT",
    },
}
METRICS = ("error_xy", "yaw_error_deg", "altitude_min", "altitude_max", "total_s")


def render_world(source: str, y_offset: float, yaw: float, label: str) -> str:
    needle = 'Crazyflie {\n  name "Crazyflie"'
    if needle not in source:
        raise RuntimeError("Crazyflie block shape changed; perturbation harness refuses to guess")
    replacement = (
        "Crazyflie {\n"
        f"  translation 0 {y_offset:.9f} 0\n"
        f"  rotation 0 0 1 {yaw:.12f}\n"
        '  name "Crazyflie"'
    )
    text = source.replace(needle, replacement, 1)
    text = text.replace("WorldInfo {", "WorldInfo {\n  randomSeed 1\n  optimalThreadCount 1", 1)
    text = text.replace('name "Crazyflie"', 'name "Crazyflie"\n  synchronization TRUE', 1)
    return text.replace('experiment"', f'experiment — {label}"', 1)


def parse_result(line: str, prefix: str) -> dict:
    if prefix not in line:
        raise RuntimeError(f"unexpected result line: {line}")
    pairs = dict(re.findall(r"([A-Za-z_]+)=([^\s]+)", line))
    if pairs.get("status") != "success" or pairs.get("legs") != "4":
        raise RuntimeError(f"non-success result: {line}")
    parsed = {"status": pairs["status"], "legs": int(pairs["legs"])}
    for metric in METRICS:
        parsed[metric] = float(pairs[metric])
    return parsed


def run_case(root: Path, artifacts: Path, backend: str, scenario: str, y_offset: float, yaw: float) -> dict:
    cfg = BACKENDS[backend]
    source_path = root / cfg["world"]
    source = source_path.read_text(encoding="utf-8")
    generated = root / "worlds" / f".ci-ab-{backend}-{scenario}.wbt"
    generated.write_text(render_world(source, y_offset, yaw, f"{backend} {scenario}"), encoding="utf-8")

    result_path = root / cfg["result"]
    result_path.unlink(missing_ok=True)
    log_path = artifacts / f"{backend}-{scenario}.log"
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
    completed = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=105)
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"{backend}/{scenario}: Webots exit={completed.returncode}; see {log_path}")
    if "ERROR:" in completed.stdout:
        raise RuntimeError(f"{backend}/{scenario}: Webots ERROR present; see {log_path}")
    if "FAILED" in completed.stdout:
        raise RuntimeError(f"{backend}/{scenario}: controller failure marker present; see {log_path}")
    if not result_path.is_file() or result_path.stat().st_size == 0:
        raise RuntimeError(f"{backend}/{scenario}: fresh result file missing")
    line = result_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    result = parse_result(line, cfg["prefix"])
    result.update({
        "backend": backend,
        "scenario": scenario,
        "initial_y_m": y_offset,
        "initial_yaw_deg": math.degrees(yaw),
    })
    return result


def degradation(rows: list[dict], backend: str) -> dict:
    own = [row for row in rows if row["backend"] == backend]
    nominal = next(row for row in own if row["scenario"] == "nominal")
    details = []
    for row in own:
        details.append({
            "scenario": row["scenario"],
            "delta_error_xy": row["error_xy"] - nominal["error_xy"],
            "delta_yaw_error_deg": row["yaw_error_deg"] - nominal["yaw_error_deg"],
            "delta_total_s": row["total_s"] - nominal["total_s"],
            "extra_altitude_high": row["altitude_max"] - nominal["altitude_max"],
            "extra_altitude_low": nominal["altitude_min"] - row["altitude_min"],
        })
    return {
        "backend": backend,
        "nominal": {metric: nominal[metric] for metric in METRICS},
        "worst_degradation": {
            key: max(0.0, max(item[key] for item in details))
            for key in ("delta_error_xy", "delta_yaw_error_deg", "delta_total_s", "extra_altitude_high", "extra_altitude_low")
        },
        "by_scenario": details,
    }


def write_markdown(path: Path, rows: list[dict], degradations: list[dict]) -> None:
    lines = [
        "# Crazyflie A/B deterministic perturbation matrix",
        "",
        "Each scenario is a fresh Webots R2025a process. The 1 m square is relative to the measured initial pose.",
        "",
        "| Backend | Scenario | y0 (m) | yaw0 (deg) | XY closure (m) | yaw error (deg) | alt min (m) | alt max (m) | duration (s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['backend']} | {row['scenario']} | {row['initial_y_m']:.3f} | {row['initial_yaw_deg']:.1f} | "
            f"{row['error_xy']:.6f} | {row['yaw_error_deg']:.6f} | {row['altitude_min']:.6f} | "
            f"{row['altitude_max']:.6f} | {row['total_s']:.3f} |"
        )
    lines.extend(["", "## Worst degradation versus each backend's own nominal", ""])
    for item in degradations:
        w = item["worst_degradation"]
        lines.append(
            f"- **{item['backend']}**: XY +{w['delta_error_xy']:.6f} m; yaw +{w['delta_yaw_error_deg']:.6f}°; "
            f"duration +{w['delta_total_s']:.3f} s; altitude high +{w['extra_altitude_high']:.6f} m; "
            f"altitude low +{w['extra_altitude_low']:.6f} m."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    artifacts = root / "ci-artifacts" / "crazyflie-ab-matrix"
    artifacts.mkdir(parents=True, exist_ok=True)
    rows = []
    generated_worlds = []
    try:
        for scenario, y_offset, yaw in SCENARIOS:
            for backend in ("A", "B"):
                generated_worlds.append(root / "worlds" / f".ci-ab-{backend}-{scenario}.wbt")
                print(f"=== {backend} / {scenario} ===", flush=True)
                row = run_case(root, artifacts, backend, scenario, y_offset, yaw)
                rows.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
    except Exception as exc:
        (artifacts / "failure.txt").write_text(str(exc) + "\n", encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        for generated in generated_worlds:
            generated.unlink(missing_ok=True)

    degradations = [degradation(rows, "A"), degradation(rows, "B")]
    payload = {"scenarios": rows, "degradation": degradations}
    (artifacts / "matrix.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(artifacts / "matrix.md", rows, degradations)
    print((artifacts / "matrix.md").read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
