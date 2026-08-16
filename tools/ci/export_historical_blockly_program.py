#!/usr/bin/env python3
"""Export one preserved Blockly fixture using the real vendored Blockly 2020 runtime."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path

from run_historical_blockly_oracle import (
    EXPECTED_PYTHON_SHA256,
    ROBOT_WINDOW_DIR,
    build_harness,
    run_browser,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("program", choices=tuple(EXPECTED_PYTHON_SHA256))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", dir=ROBOT_WINDOW_DIR, encoding="utf-8", delete=False
    ) as handle:
        handle.write(build_harness())
        harness_path = Path(handle.name)

    try:
        result = run_browser(harness_path)
    finally:
        harness_path.unlink(missing_ok=True)

    if not result.get("ok"):
        raise RuntimeError(f"Blockly browser execution failed: {result.get('error')}")

    generated = result.get("programs")
    if not isinstance(generated, dict):
        raise RuntimeError("Blockly browser result is malformed")
    entry = generated.get(args.program)
    if not isinstance(entry, dict) or not isinstance(entry.get("code"), str):
        raise RuntimeError(f"missing generated Python for {args.program}")

    code = entry["code"]
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expected = EXPECTED_PYTHON_SHA256[args.program]
    if digest != expected:
        raise RuntimeError(
            f"generated Python drift for {args.program}: sha256={digest}, expected={expected}"
        )

    compile(code, f"<Blockly:{args.program}>", "exec")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(code, encoding="utf-8")
    print(
        f"PASS: exported {args.program} to {args.output} "
        f"({len(code.encode('utf-8'))} bytes, sha256={digest})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
