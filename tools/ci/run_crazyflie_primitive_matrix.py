#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path

from localize_webots_world import localize

IMAGE = "cyberbotics/webots:R2025a-ubuntu22.04"
WEBOTS_REPOSITORY = "https://github.com/cyberbotics/webots.git"
WEBOTS_SHA = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
WEBOTS_CHECKOUT = ".ci-webots-r2025a"
REQUIRED_PROJECT_ASSETS = (
    "projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto",
    "projects/objects/backgrounds/protos/TexturedBackground.proto",
    "projects/objects/backgrounds/protos/TexturedBackgroundLight.proto",
    "projects/objects/floors/protos/Floor.proto",
)
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


def run_checked(command: list[str], *, cwd: Path, timeout: int = 180) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stdout}"
        )


def prepare_pinned_webots_projects(root: Path) -> Path:
    checkout = root / WEBOTS_CHECKOUT
    if not checkout.exists():
        checkout.mkdir()
        run_checked(["git", "init"], cwd=checkout)
        run_checked(["git", "remote", "add", "origin", WEBOTS_REPOSITORY], cwd=checkout)
        run_checked(
            ["git", "fetch", "--depth=1", "origin", WEBOTS_SHA],
            cwd=checkout,
            timeout=300,
        )
        run_checked(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=checkout)

    if not (checkout / ".git").is_dir():
        raise RuntimeError(f"{checkout} exists but is not a Git checkout")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if head != WEBOTS_SHA:
        raise RuntimeError(
            f"pinned Webots checkout mismatch: expected {WEBOTS_SHA}, found {head}"
        )

    missing = [asset for asset in REQUIRED_PROJECT_ASSETS if not (checkout / asset).is_file()]
    if missing:
        raise RuntimeError(f"pinned Webots project assets missing: {missing}")
    return checkout / "projects"


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


def prepare_generated_world(
    source: Path,
    target: Path,
    controller: str,
    kind: str | None,
    value: str | None,
    label: str,
) -> None:
    localize(source, target, expected=4)
    target.write_text(
        render_world(
            target.read_text(encoding="utf-8"), controller, kind, value, label
        ),
        encoding="utf-8",
    )


def build_webots_command(
    root: Path, webots_projects: Path, relative_world: str
) -> list[str]:
    inner = (
        "timeout -k 5s 90s xvfb-run -a webots --stdout --stderr --batch --mode=fast "
        f"/workspace/{relative_world}"
    )
    return [
        "docker", "run", "--rm",
        "--network", "none",
        "-e", "LIBGL_ALWAYS_SOFTWARE=true",
        "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
        "-v", f"{root}:/workspace",
        "-v", f"{webots_projects}:/usr/local/webots/projects:ro",
        "-w", "/workspace",
        IMAGE,
        "bash", "-lc", inner,
    ]


def parse_pairs(line: str, prefix: str) -> dict:
    if prefix not in line:
        raise RuntimeError(f"unexpected result line: {line}")
    pairs = dict(re.findall(r"([A-Za-z_]+)=([^\s]+)", line))
    if pairs.get("status") != "success":
        raise RuntimeError(f"non-success result: {line}")
    return pairs


def require_common_endpoint(pairs: dict, backend: str, mission: str) -> None:
    required = (
        "residual_speed", "residual_yaw_rate", "residual_vz",
        "final_x", "final_y", "final_z", "final_yaw",
    )
    missing = [key for key in required if key not in pairs]
    if missing:
        raise RuntimeError(f"{backend}/{mission}: common endpoint fields missing: {missing}")
    if float(pairs["residual_speed"]) >= 0.12:
        raise RuntimeError(f"{backend}/{mission}: residual horizontal speed not settled")
    if abs(float(pairs["residual_yaw_rate"])) >= 0.10:
        raise RuntimeError(f"{backend}/{mission}: residual yaw rate not settled")
    if abs(float(pairs["residual_vz"])) >= 0.15:
        raise RuntimeError(f"{backend}/{mission}: residual vertical speed not settled")
    if backend == "B":
        if "residual_altitude_error" not in pairs:
            raise RuntimeError(f"{backend}/{mission}: residual altitude error missing")
        if abs(float(pairs["residual_altitude_error"])) >= 0.05:
            raise RuntimeError(f"{backend}/{mission}: residual altitude error not settled")


def run_case(
    root: Path,
    artifacts: Path,
    webots_projects: Path,
    backend: str,
    mission: str,
    kind: str | None,
    value: str | None,
) -> dict:
    cfg = BACKENDS[backend]
    source_path = root / cfg["world"]
    generated = root / "worlds" / f".ci-primitive-{backend}-{mission}.wbt"
    prepare_generated_world(
        source_path, generated, cfg["controller"], kind, value, f"{backend} {mission}"
    )

    primitive_path = root / cfg["primitive_result"]
    square_path = root / cfg["square_result"]
    primitive_path.unlink(missing_ok=True)
    square_path.unlink(missing_ok=True)
    log_path = artifacts / f"{backend}-{mission}.log"
    relative_world = generated.relative_to(root).as_posix()
    command = build_webots_command(root, webots_projects, relative_world)
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
        require_common_endpoint(pairs, backend, mission)
        row = {
            "backend": backend,
            "mission": mission,
            "kind": pairs["kind"],
            "command": float(pairs["command"]),
            "yaw_error_deg": float(pairs["yaw_error_deg"]),
            "duration_s": float(pairs["primitive_s"]),
            "residual_speed_m_s": float(pairs["residual_speed"]),
            "residual_yaw_rate_rad_s": float(pairs["residual_yaw_rate"]),
            "residual_vz_m_s": float(pairs["residual_vz"]),
            "final_x_m": float(pairs["final_x"]),
            "final_y_m": float(pairs["final_y"]),
            "final_z_m": float(pairs["final_z"]),
            "final_yaw_rad": float(pairs["final_yaw"]),
        }
        if backend == "B":
            row["residual_altitude_error_m"] = float(pairs["residual_altitude_error"])
        if backend == "A":
            row["threshold_error"] = float(pairs["threshold_error"])
            row["max_overshoot"] = float(pairs["max_overshoot"])
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
        "T/Y metrics are captured only after the common 0.5 s kinematic stability boundary, before LAND.",
        "",
        "| Backend | Mission | Kind | Command | Long err (m) | Lateral err (m) | Yaw err (deg) | Drift XY (m) | Residual speed | Residual yaw rate | Residual vz | Alt err (m) | Time (s) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['backend']} | {row['mission']} | {row['kind']} | {row.get('command', 0):.3f} | "
            f"{row.get('longitudinal_error_m', 0):.6f} | {row.get('lateral_error_m', 0):.6f} | "
            f"{row['yaw_error_deg']:.6f} | {row.get('drift_xy_m', row.get('error_xy', 0)):.6f} | "
            f"{row.get('residual_speed_m_s', 0):.6f} | {row.get('residual_yaw_rate_rad_s', 0):.6f} | "
            f"{row.get('residual_vz_m_s', 0):.6f} | {row.get('residual_altitude_error_m', 0):.6f} | {row['duration_s']:.3f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    artifacts = root / "ci-artifacts" / "crazyflie-primitive-matrix"
    artifacts.mkdir(parents=True, exist_ok=True)
    rows = []
    try:
        webots_projects = prepare_pinned_webots_projects(root)
        for mission, kind, value in MISSIONS:
            for backend in ("A", "B"):
                print(f"=== {backend} / {mission} ===", flush=True)
                row = run_case(root, artifacts, webots_projects, backend, mission, kind, value)
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
