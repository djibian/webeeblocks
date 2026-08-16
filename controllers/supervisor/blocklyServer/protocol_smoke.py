#!/usr/bin/env python3
import asyncio
import shutil
import socket
import subprocess
import time
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent
PROGRAMS = (ROOT / "../Blockly_Programs").resolve()
CONTROLLER = (ROOT / "../my_controller/my_controller.py").resolve()
SMOKE_NAME = "__ci_protocol_smoke__"
SMOKE_XML = PROGRAMS / f"{SMOKE_NAME}.xml"
SMOKE_CODE = "print('webeeblocks-ci-protocol-smoke')\n"


def wait_for_port(host="127.0.0.1", port=8001, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"blocklyServer did not listen on {host}:{port}")


async def exercise_protocol():
    uri = "ws://127.0.0.1:8001/test.py"
    async with websockets.connect(uri) as ws:
        await ws.send("LIST_SAVES")
        saves = await ws.recv()
        if not isinstance(saves, str):
            raise AssertionError("LIST_SAVES did not return text")

        xml = "<xml><block type=\"text\"></block></xml>"
        await ws.send("SAVE")
        await ws.send(SMOKE_XML.name)
        await ws.send(xml)

        await ws.send("RESTORE_SAVE")
        await ws.send(SMOKE_XML.name)
        restored = await ws.recv()
        if restored != xml:
            raise AssertionError(f"RESTORE_SAVE mismatch: {restored!r}")

        await ws.send("SEND_CODE")
        await ws.send(SMOKE_CODE)

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if CONTROLLER.read_text(encoding="utf-8") == SMOKE_CODE:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("SEND_CODE did not update my_controller.py")


def main():
    backup = ROOT / "my_controller.py.ci-backup"
    shutil.copy2(CONTROLLER, backup)
    server = subprocess.Popen([str(ROOT / "blocklyServer")], cwd=ROOT)
    try:
        wait_for_port()
        asyncio.run(exercise_protocol())
        print("PASS: LIST_SAVES, SAVE, RESTORE_SAVE and SEND_CODE")
    finally:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=2)
        shutil.copy2(backup, CONTROLLER)
        backup.unlink(missing_ok=True)
        SMOKE_XML.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
