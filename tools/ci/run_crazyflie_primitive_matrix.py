#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path

IMAGE = "cyberbotics/webots:R2025a-ubuntu22.04"
MISSIONS = [
    ("T-short", "forward", "0.50"),
    ("T-long", "forward", "1.50"),
    ("Y-small", "turn", "45"),
    ("Y-large", "turn", "135"),
    ("S-ref", None, None),
]
BACKENDS = {
    "A": {
        "world": "worlds/crazyflie_square.wbt",
        "controller": "crazyflie_square",
        "primitive_result": "ci-artifacts/crazyflie-primitive-A.txt",
        "primitive_prefix": "WEBEEBLOCKS_CF_PRIMITIVE_A",
        "square_result": "ci-artifacts/crazyflie-square-result.txt",
        "square_prefix": "WEBEEBLOCKS_CF_SQUARE_RESULT",
    },
    "B": {
        "world": "worlds/crazyflie_square_position.wbt",
        "controller": "crazyflie_square_position",
        "primitive_result": "ci-artifacts/crazyflie-primitive-B.txt",
        "primitive_prefix": "WEBEEBLOCKS_CF_PRIMITIVE_B",
        "square_result": "ci-artifacts/crazyflie-square-position-result.txt",
        "square_prefix": "WEBEEBLOCKS_CF_POSITION_RESULT",
    },
}


def render_world(source: str, controller: str, kind: str | None, value: str | None, label: str) -> str:
    needle = f'  controller "{controller}"\n'
    if needle not in source:
        raise RuntimeError(f"controller field not found for {controller}")
    if kind is not None:
        args = f'  controllerArgs [\n    "{kind}"\n    "{value}"\n  ]\n'
        source = source.replace(needle, needle + args, 1)
    source = source.replace("WorldInfo {", "WorldInfo {\n  randomSeed 1\n  optimalThreadCount 1", 1)
    source = source.replace('name "Crazyflie"', 'name "Crazyflie"\n  synchronization TRUE', 1)
    return source.replace('experiment"', f'experiment — {label}"', 1)


def parse_pairs(line: str, prefix: str) -> dict:
    if prefix not in line:
        raise RuntimeError(f"unexpected result line: {line}")
    pairs = dict(re.findall(r"([A-Za-z_]+)=([^\s]+)", line))
    if pairs.get("status") != "success":
        raise RuntimeError(f"non-success result: {line}")
    return pairs


def run_case(root: Path, artifacts: Path, backend: str, mission: str, kind: str | None, value: str | None) -> dict:
    cfg = BACKENDS[backend]
    source = (root / cfg["world"]).read_text(encoding="utf-8")
    generated = root / "worlds" / f".ci-primitive-{backend}-{mission}.wbt"
    generated.write_text(render_world(source, cfg["controller"], kind, value, f"{backend} {mission}"), encoding="utf-8")

    primitive_path = root / cfg["primitive_result"]
    square_path = root / cfg["square_result"]
    primitive_path.unlink(missing_ok=True)
    square_path.unlink(missing_ok=True)
    log_path = artifacts / f"{backend}-{mission}.log"
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
        completed = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=105)
        log_path.write_text(completed.stdout, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"{backend}/{mission}: Webots exit={completed.returncode}; see {log_path}")
        if "ERROR:" in completed.stdout or "FAILED" in completed.stdout:
            raise RuntimeError(f"{backend}/{mission}: Webots/controller error; see {log_path}")

        if kind is None:
            if not square_path.is_file() or square_path.stat().st_size == 0:
                raise RuntimeError(f"{backend}/{mission}: fresh square result missing")
            pairs = parse_pairs(square_path.read_text(encoding="utf-8").strip().splitlines()[-1], cfg["square_prefix"])
            return {
                "backend": backend,
                "mission": mission,
                "kind": "square",
                "error_xy": float(pairs["error_xy"]),
                "yaw_error_deg": float(pairs["yaw_error_deg"]),
                "duration_s": float(pairs["total_s"]),
            }

        if not primitive_path.is_file() or primitive_path.stat().st_size == 0:
            raise RuntimeError(f"{backend}/{mission}: fresh primitive result missing")
        pairs = parse_pairs(primitive_path.read_text(encoding="utf-8").strip().splitlines()[-1], cfg["primitive_prefix"])
        row = {
            "backend": backend,
            "mission": mission,
            "kind": pairs["kind"],
            "command": float(pairs["command"]),
            "yaw_error_deg": float(pairs["yaw_error_deg"]),
            "duration_s": float(pairs["primitive_s"]),
        }
        if kind == "forward":
            row["longitudinal_error_m"] = float(pairs["longitudinal_error"])
            row["lateral_error_m"] = float(pairs["lateral_error"])
        else:
            row["drift_xy_m"] = float(pairs["drift_xy"])
        return row
    finally:
        generated.unlink(missing_ok=True)


def write_markdown(path: Path, rows: list[dict]) -> None:
    lines = [
        "# Crazyflie primitive A/B matrix",
        "",
        "Metrics for T/Y are captured at primitive completion, before LAND.",
        "",
        "| Backend | Mission | Kind | Command | Long err (m) | Lateral err (m) | Yaw err (deg) | Drift XY (m) | Primitive/mission (s) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['backend']} | {row['mission']} | {row['kind']} | {row.get('command', 0):.3f} | "
            f"{row.get('longitudinal_error_m', 0):.6f} | {row.get('lateral_error_m', 0):.6f} | "
            f"{row['yaw_error_deg']:.6f} | {row.get('drift_xy_m', row.get('error_xy', 0)):.6f} | {row['duration_s']:.3f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    artifacts = root / "ci-artifacts" / "crazyflie-primitive-matrix"
    artifacts.mkdir(parents=True, exist_ok=True)
    rows = []
    try:
        for mission, kind, value in MISSIONS:
            for backend in ("A", "B"):
                print(f"=== {backend} / {mission} ===", flush=True)
                row = run_case(root, artifacts, backend, mission, kind, value)
                rows.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
    except Exception as exc:
        (artifacts / "failure.txt").write_text(str(exc) + "\n", encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    (artifacts / "matrix.json").write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(artifacts / "matrix.md", rows)
    print((artifacts / "matrix.md").read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
