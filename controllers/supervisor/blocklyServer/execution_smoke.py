#!/usr/bin/env python3
import asyncio
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUPERVISOR_DIR = ROOT.parent
CONTROLLERS_DIR = SUPERVISOR_DIR.parent
CONTROLLER = (CONTROLLERS_DIR / "my_controller/my_controller.py").resolve()
BACKUP = ROOT / "my_controller.py.execution-smoke-backup"
MARKER = "WEBEEBLOCKS_CI_SUBMITTED_CONTROLLER_EXECUTED"
SMOKE_CODE = f"print('{MARKER}')\n"


def wait_for_port(host="127.0.0.1", port=8001, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"blocklyServer did not listen on {host}:{port}")


async def send_code():
    import websockets

    async with websockets.connect("ws://127.0.0.1:8001/test.py") as ws:
        await ws.send("SEND_CODE")
        await ws.send(SMOKE_CODE)

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if CONTROLLER.read_text(encoding="utf-8") == SMOKE_CODE:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("SEND_CODE did not install the execution smoke controller")


def prepare():
    if BACKUP.exists():
        raise RuntimeError(f"stale execution smoke backup exists: {BACKUP}")

    shutil.copy2(CONTROLLER, BACKUP)
    server = subprocess.Popen([str(ROOT / "blocklyServer")], cwd=SUPERVISOR_DIR)
    try:
        wait_for_port()
        asyncio.run(send_code())
        print(f"PASS: SEND_CODE installed controller marker {MARKER}")
    except BaseException:
        restore()
        raise
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=2)


def restore():
    if not BACKUP.exists():
        print("No execution smoke backup to restore.")
        return
    shutil.copy2(BACKUP, CONTROLLER)
    BACKUP.unlink()
    print("PASS: restored historical my_controller.py")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "restore"}:
        raise SystemExit("usage: execution_smoke.py {prepare|restore}")
    if sys.argv[1] == "prepare":
        prepare()
    else:
        restore()


if __name__ == "__main__":
    main()
