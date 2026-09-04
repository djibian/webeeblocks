#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "worlds" / ".ci-empty-local.wbt"
TEMP_WORLD = ROOT / "worlds" / "ci_restart_smoke.wbt"
CONTROLLER = ROOT / "controllers" / "my_controller" / "my_controller.py"
BACKUP = Path(__file__).resolve().parent / "my_controller.py.restart-smoke-backup"
INITIAL = "WEBEEBLOCKS_CI_RESTART_INITIAL"

INITIAL_CODE = (
    "from controller import Robot\n"
    "robot = Robot()\n"
    f"print('{INITIAL}', flush=True)\n"
    "while robot.step(int(robot.getBasicTimeStep())) != -1:\n"
    "    pass\n"
)


def prepare():
    if BACKUP.exists() or TEMP_WORLD.exists():
        raise RuntimeError("stale restart smoke fixture exists")
    shutil.copy2(CONTROLLER, BACKUP)
    CONTROLLER.write_text(INITIAL_CODE, encoding="utf-8")
    source = WORLD.read_text(encoding="utf-8")
    old = 'controller "supervisor"'
    if source.count(old) != 1:
        restore()
        raise RuntimeError(f"expected exactly one {old!r} in {WORLD.name}")
    TEMP_WORLD.write_text(source.replace(old, 'controller "ci_restart_supervisor"', 1), encoding="utf-8")
    print(f"PASS: prepared {TEMP_WORLD.name} and initial controller marker")


def restore():
    if BACKUP.exists():
        shutil.copy2(BACKUP, CONTROLLER)
        BACKUP.unlink()
    TEMP_WORLD.unlink(missing_ok=True)
    print("PASS: restored restart smoke fixtures")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "restore"}:
        raise SystemExit("usage: restart_smoke.py {prepare|restore}")
    prepare() if sys.argv[1] == "prepare" else restore()


if __name__ == "__main__":
    main()
