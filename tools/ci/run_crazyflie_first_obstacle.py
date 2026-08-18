#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

IMAGE = "cyberbotics/webots:R2025a-ubuntu22.04"
CONTACT_RESULT = "ci-artifacts/crazyflie-obstacle-contact.txt"
L_RESULT = "ci-artifacts/crazyflie-l-course-result.txt"


def run_world(root: Path, artifacts: Path, label: str, world: str) -> tuple[int, str]:
    log_path = artifacts / f"{label}.log"
    inner = (
        "timeout -k 5s 90s xvfb-run -a webots --stdout --stderr --batch --mode=fast "
        f"/workspace/{world}"
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
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=105,
    )
    log_path.write_text(completed.stdout, encoding="utf-8")
    return completed.returncode, completed.stdout


def parse_last_result(path: Path, prefix: str) -> dict[str, str]:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"result missing: {path}")
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    if prefix not in line:
        raise RuntimeError(f"unexpected result: {line}")
    pairs = {}
    for token in line.split():
        if "=" in token:
            key, value = token.split("=", 1)
            pairs[key] = value
    return pairs


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    artifacts = root / "ci-artifacts" / "crazyflie-first-obstacle"
    artifacts.mkdir(parents=True, exist_ok=True)
    contact = root / CONTACT_RESULT
    l_result = root / L_RESULT

    summary = {
        "obstacle": {
            "center_x_m": 1.25,
            "transverse_m": 0.30,
            "thickness_m": 0.05,
            "height_m": 1.40,
            "crazyflie_radius_m": 0.05,
            "detour_nominal_clearance_m": 0.175,
        }
    }

    try:
        # Witness: a characterized 2 m forward primitive must hit the obstacle.
        contact.unlink(missing_ok=True)
        l_result.unlink(missing_ok=True)
        direct_code, direct_log = run_world(
            root, artifacts, "direct", "worlds/crazyflie_obstacle_direct.wbt"
        )
        if direct_code == 124:
            raise RuntimeError("direct witness timed out before collision")
        if "ERROR:" in direct_log:
            raise RuntimeError("direct witness contains a Webots ERROR; see direct.log")
        direct = parse_last_result(contact, "WEBEEBLOCKS_OBSTACLE_RESULT")
        if direct.get("status") != "COLLISION":
            raise RuntimeError(f"direct witness did not classify COLLISION: {direct}")
        summary["direct"] = {
            "expected": "COLLISION",
            "observed": "COLLISION",
            "webots_exit": direct_code,
            "contact_time_s": float(direct["time"]),
            "contact_xyz_m": [float(direct["x"]), float(direct["y"]), float(direct["z"])],
        }

        # Detour: the already-proven STOP L must clear the exact same obstacle,
        # cross both virtual gates and land successfully.
        contact.unlink(missing_ok=True)
        l_result.unlink(missing_ok=True)
        detour_code, detour_log = run_world(
            root, artifacts, "detour", "worlds/crazyflie_obstacle_detour.wbt"
        )
        if detour_code != 0:
            raise RuntimeError(f"detour Webots exit={detour_code}; see detour.log")
        if "ERROR:" in detour_log or "Traceback" in detour_log:
            raise RuntimeError("detour contains a Webots/Python error; see detour.log")
        if contact.exists():
            collision = parse_last_result(contact, "WEBEEBLOCKS_OBSTACLE_RESULT")
            raise RuntimeError(f"detour collided with obstacle: {collision}")
        detour = parse_last_result(l_result, "WEBEEBLOCKS_CF_L_RESULT")
        if detour.get("status") != "success" or detour.get("gates") != "2":
            raise RuntimeError(f"detour did not complete G1/G2/LAND: {detour}")
        summary["detour"] = {
            "expected": "SUCCESS",
            "observed": "SUCCESS",
            "webots_exit": detour_code,
            "gates": int(detour["gates"]),
            "endpoint_error_xy_m": float(detour["endpoint_error_xy"]),
            "yaw_error_deg": float(detour["yaw_error_deg"]),
            "total_s": float(detour["total_s"]),
        }

    except Exception as exc:
        (artifacts / "failure.txt").write_text(str(exc) + "\n", encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    (artifacts / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown = [
        "# First collision obstacle experiment",
        "",
        "Same physical obstacle in both runs: 0.30 m transverse × 0.05 m thick × 1.40 m high, center x=1.25 m.",
        "Nominal STOP-L clearance at the first corner: 0.175 m between the Crazyflie collision envelope and the obstacle.",
        "",
        "| Mission | Expected | Observed | Evidence |",
        "|---|---|---|---|",
        f"| direct forward 2.0 m | COLLISION | {summary['direct']['observed']} | contact t={summary['direct']['contact_time_s']:.3f} s |",
        f"| STOP L detour | SUCCESS | {summary['detour']['observed']} | G1→G2→LAND; endpoint={summary['detour']['endpoint_error_xy_m']:.6f} m; yaw={summary['detour']['yaw_error_deg']:.6f}° |",
        "",
        "No sensor block, condition, scoring rule, avoidance algorithm or PID/navigation tuning is part of this experiment.",
    ]
    (artifacts / "summary.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print((artifacts / "summary.md").read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
