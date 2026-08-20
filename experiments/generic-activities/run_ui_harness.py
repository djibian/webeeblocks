#!/usr/bin/env python3
"""Run the disposable generic-activity UI harness in a real headless browser.

The script serves the repository root over localhost, opens the harness with an
installed Chrome/Chromium binary and inspects the final DOM. It does not modify
WebeeBlocks product files or require Webots.
"""

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
HARNESS_RELATIVE = pathlib.Path("experiments/generic-activities/ui_harness.html")


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

        url = f"http://127.0.0.1:{port}/{HARNESS_RELATIVE.as_posix()}"
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--virtual-time-budget=5000",
            "--dump-dom",
            url,
        ]
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        server.shutdown()

    dom = completed.stdout
    stderr = completed.stderr
    marker = "PASS real Blockly activity profile harness"
    if marker not in dom:
        print("FAIL real Blockly activity profile harness", file=sys.stderr)
        print("browser exit:", completed.returncode, file=sys.stderr)
        if stderr:
            print(stderr[-4000:], file=sys.stderr)
        if dom:
            print(dom[-8000:], file=sys.stderr)
        return 1

    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
