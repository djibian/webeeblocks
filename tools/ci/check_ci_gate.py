#!/usr/bin/env python3
"""Fail closed unless every selected reusable suite succeeded."""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    selection = json.loads(os.environ.get("CI_SELECTION", "{}"))
    needs = json.loads(os.environ.get("CI_NEEDS", "{}"))

    failures: list[str] = []
    if needs.get("select", {}).get("result") != "success":
        failures.append("selection job did not succeed")

    for suite in ("runtime", "webots"):
        selected = selection.get(suite) == "true"
        result = needs.get(suite, {}).get("result")
        if selected and result != "success":
            failures.append(f"selected {suite} suite result is {result!r}")
        if not selected and result not in ("skipped", None):
            failures.append(f"unselected {suite} suite unexpectedly returned {result!r}")

    print(json.dumps({"selection": selection, "results": needs}, indent=2))
    if failures:
        for failure in failures:
            print(f"CI Gate failure: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

