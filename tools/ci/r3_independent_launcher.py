#!/usr/bin/env python3
"""Disposable CI helper: launch a second Chrome profile after B1's native effect.

Independent profile B2 uses a new user-data-dir and a separate top-level
document, but the *same* running, unmodified Webots R2025a WebSocket server.
No UI fake transport, no shared localStorage and no use of CDP.
"""
import argparse
import json
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    deadline = time.monotonic() + 390
    while time.monotonic() < deadline:
        try:
            rows = [json.loads(x) for x in args.events.read_text().splitlines() if x.strip()]
        except (OSError, ValueError):
            time.sleep(0.2)
            continue
        if not any(x.get("event") == "R3_B_NATIVE_REFUSED" for x in rows):
            time.sleep(0.2)
            continue
        starts = [x.get("detail", {}) for x in rows if x.get("event") == "R3_A_OPENED_B_AFTER_CLEAR"]
        if len(starts) != 1:
            raise RuntimeError("Missing one genuine A→B URL provenance")
        url = starts[0].get("href", "")
        if not url.startswith("http://127.0.0.1:") and not url.startswith("http://localhost:"):
            raise RuntimeError("Refusing non-loopback Webots Robot Window URL")
        if "#" in url:
            raise RuntimeError("Unexpected existing URL fragment")
        target = url + "#webeeblocks-r3-profile-b2"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        output = args.evidence.with_name("b2-chrome.log").open("wb")
        argv = [
            "/usr/bin/google-chrome",
            "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-background-networking",
            "--no-first-run", "--no-default-browser-check",
            "--user-data-dir=/tmp/webeeblocks-r3-independent-profile",
            target,
        ]
        proc = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT)
        args.evidence.write_text(json.dumps({"pid": proc.pid, "url": target}) + "\n")
        print("R3_INDEPENDENT_PROFILE_LAUNCHED", proc.pid, flush=True)
        output.close()
        return 0
    raise RuntimeError("Never saw B1 native effect; refusing to launch independent profile")


if __name__ == "__main__":
    raise SystemExit(main())
