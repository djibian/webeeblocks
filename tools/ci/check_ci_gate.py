#!/usr/bin/env python3
"""Fail closed unless every selected reusable suite succeeded."""

from __future__ import annotations

import json
import os
import sys


def evaluate_gate(selection: object, needs: object) -> list[str]:
    if not isinstance(selection, dict) or set(selection) != {"runtime", "webots"}:
        return ["invalid CI evidence: selection must name runtime and webots"]
    failures: list[str] = []
    for suite, selected in selection.items():
        if not isinstance(selected, str) or selected not in ("true", "false"):
            failures.append(f"invalid CI evidence: selection for {suite} is {selected!r}")
    if not isinstance(needs, dict) or set(needs) != {"select", "runtime", "webots"}:
        return failures + ["invalid CI evidence: needs must name select, runtime and webots"]
    for job, evidence in needs.items():
        if not isinstance(evidence, dict) or not isinstance(evidence.get("result"), str):
            failures.append(f"invalid CI evidence: missing result for {job}")
    if failures:
        return failures

    if needs["select"]["result"] != "success":
        failures.append("selection job did not succeed")
    for suite in ("runtime", "webots"):
        expected = "success" if selection[suite] == "true" else "skipped"
        result = needs[suite]["result"]
        if result != expected:
            failures.append(f"{suite}: expected {expected}, observed {result!r}")
    return failures


def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main() -> int:
    try:
        selection = json.loads(os.environ["CI_SELECTION"], object_pairs_hook=unique_keys)
        needs = json.loads(os.environ["CI_NEEDS"], object_pairs_hook=unique_keys)
    except (KeyError, ValueError) as error:
        print(f"CI Gate failure: invalid CI evidence: {error}", file=sys.stderr)
        return 1

    print(json.dumps({"selection": selection, "results": needs}, indent=2))
    failures = evaluate_gate(selection, needs)
    if failures:
        for failure in failures:
            print(f"CI Gate failure: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
