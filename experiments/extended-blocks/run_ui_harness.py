#!/usr/bin/env python3
"""Execute the disposable extended-block harness in the real bundled Blockly 2020."""

from __future__ import annotations

import http.server
import os
import pathlib
import shutil
import socketserver
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
HARNESS = pathlib.Path("experiments/extended-blocks/ui_harness.html")


def browser_binary() -> str:
    for candidate in (
        os.environ.get("CHROME_BIN"),
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        if candidate and shutil.which(candidate):
            return shutil.which(candidate) or candidate
    raise RuntimeError("no Chrome/Chromium binary found; set CHROME_BIN")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        pass


def main() -> int:
    browser = browser_binary()
    os.chdir(REPO_ROOT)
    with socketserver.TCPServer(("127.0.0.1", 0), QuietHandler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.05)
        url = f"http://127.0.0.1:{port}/{HARNESS.as_posix()}"
        completed = subprocess.run(
            [browser, "--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
             "--virtual-time-budget=4000", "--dump-dom", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        server.shutdown()

    marker = "PASS real Blockly 2020 extended semantic AST"
    if marker not in completed.stdout:
        print("FAIL real Blockly 2020 extended semantic AST", file=sys.stderr)
        print("browser exit:", completed.returncode, file=sys.stderr)
        if completed.stderr:
            print(completed.stderr[-4000:], file=sys.stderr)
        if completed.stdout:
            print(completed.stdout[-8000:], file=sys.stderr)
        return 1
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
