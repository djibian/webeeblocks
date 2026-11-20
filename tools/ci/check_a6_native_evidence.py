#!/usr/bin/env python3
"""Fail-closed cross-variant A6 native R2025a witness check; never a fake simulator."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "ci-artifacts/grand-prix-u-geometry"


def records(log):
    result = []
    for line in log.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            result.append(event)
    return result


def main():
    checks = []
    for variant in range(1, 6):
        folder = ARTIFACTS / f"route-a6-v{variant}-native"
        wbb = folder / "a6-witness.wbb"
        log = folder / "wwi.log"
        native = folder / "webots.log"
        if not all(item.is_file() for item in (wbb, log, native)):
            raise RuntimeError(f"A6 V{variant}: real native evidence missing")
        payload = wbb.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        project = json.loads(payload)
        if (project.get("format") != "webeeblocks-project" or
                project.get("activity", {}).get("id") != "grand-prix-a6-native-experimental-v1"):
            raise RuntimeError(f"A6 V{variant}: not the genuine A6 .wbb")
        events = records(log.read_text(encoding="utf-8"))
        manifest = [e for e in events if e.get("event") == "A6_WBB"]
        if (len(manifest) != 1 or manifest[0].get("sha256") != digest or
                manifest[0].get("bytes") != len(payload)):
            raise RuntimeError(f"A6 V{variant}: WBB bytes and native WWI attestations disagree")
        sensors = [e for e in events if e.get("event") == "A6_SENSOR"]
        front = [e.get("value") for e in sensors if e.get("direction") == "front"]
        left = [e.get("value") for e in sensors if e.get("direction") == "left"]
        right = [e.get("value") for e in sensors if e.get("direction") == "right"]
        if (len(left) != 1 or len(right) != 1 or len(front) != (2 if variant <= 3 else 1) or
                not (.65 < front[0] < 1.75)):
            raise RuntimeError(f"A6 V{variant}: missing required native rays")
        if variant <= 3:
            if not (.20 < left[0] < .45 and .20 < right[0] < .45):
                raise RuntimeError(f"A6 V{variant}: both open-H uprights not observed")
        elif left[0] < 1.9 or right[0] < 1.9:
            raise RuntimeError(f"A6 V{variant}: closed H should not expose two uprights")
        outcomes = [e for e in events if "status" in e]
        if (outcomes != [{"status": "achieved"},
                         {"status": "not-achieved", "reason": "envelope-contact"}]):
            raise RuntimeError(f"A6 V{variant}: positive/negative mission outcomes differ")
        trace = native.read_text(encoding="utf-8", errors="replace")
        # Bind each independent LAND to the correct native attempt.
        # A total of two OKs alone would not prove STOP worked after RESET:
        # both could have occurred on the same stale/failed incarnation.
        phases = {1: [], 2: [], 3: []}
        active_attempt = None
        for line in trace.splitlines():
            if line.startswith("GP_U_ADMISSION attempt="):
                parts = line.split()
                if len(parts) != 3 or not parts[1].startswith("attempt="):
                    raise RuntimeError(f"A6 V{variant}: malformed native admission")
                try:
                    active_attempt = int(parts[1][len("attempt="):])
                except ValueError as exc:
                    raise RuntimeError(f"A6 V{variant}: invalid native attempt") from exc
                if active_attempt not in phases or phases[active_attempt]:
                    raise RuntimeError(f"A6 V{variant}: duplicate/unexpected native admission")
                phases[active_attempt].append("admission")
            elif line.startswith("GP_U_DEADLINE "):
                if active_attempt not in phases:
                    raise RuntimeError(f"A6 V{variant}: orphan forced LAND")
                phases[active_attempt].append("forced")
            elif line.startswith("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 "):
                if active_attempt not in phases:
                    raise RuntimeError(f"A6 V{variant}: orphan LAND reply")
                phases[active_attempt].append(
                    "land_ok" if line == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 OK"
                    else "land_error")
        if phases != {
            1: ["admission"],
            2: ["admission", "forced", "land_ok"],
            3: ["admission", "forced", "land_ok"],
        } or "WEBEEBLOCKS_RUNTIME_V2 FATAL unsafe attitude" in trace:
            raise RuntimeError(
                f"A6 V{variant}: collision/STOP LAND not independently settled: {phases}")
        checks.append((variant, digest, front[0]))
    if len({digest for _, digest, _ in checks}) != 1:
        raise RuntimeError("A6 variants did not execute the EXACT SAME .wbb bytes")
    initial = {variant: front for variant, _, front in checks}
    for opened, closed in ((2, 4), (3, 5)):
        if abs(initial[opened] - initial[closed]) > .05:
            raise RuntimeError(f"A6 V{opened}/V{closed}: native aligned frontal ambiguity falsified")
    print("PASS five complete native A6 variants, identical real .wbb SHA256",
          checks[0][1], "bilateral rays, negative contact, RESET and independent LAND")
    print("NATIVE_A6_FRONTAL_PAIRS",
          json.dumps({"V2_V4": [initial[2], initial[4]],
                      "V3_V5": [initial[3], initial[5]]}))


if __name__ == "__main__":
    main()
