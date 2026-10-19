"""Forensic, read-only summary of the #637 autonomous R2025a observer trace.

This is diagnostic evidence only. Neither a teleport nor an attempt identifier
establishes a RESET acknowledgement, physical stability, or a CI PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HEADER = {"type": "header", "version": 1, "step_ms": 32,
          "scope": "read-only-native-state-not-runtime-ack"}
PREFIX = "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 "


def _numeric_position(sample):
    position = sample.get("position")
    if (not isinstance(position, list) or len(position) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in position)):
        return None
    return position


def summarize(path: Path) -> dict:
    """Report raw timing/kinematics per identity; do not decide RESET validity."""
    digest = hashlib.sha256()
    groups = {}
    previous_time = 0.0
    previous_position = None
    previous_identity = None
    previous_sample = None
    total = 0
    with Path(path).open("rb") as stream:
        for line_no, raw in enumerate(stream, 1):
            digest.update(raw)
            try:
                sample = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError(f"invalid JSONL line {line_no}: {exc}") from exc
            if line_no == 1:
                if sample != HEADER:
                    raise ValueError("unrecognized R2025a observer header")
                continue
            now = sample.get("time")
            if (sample.get("type") != "sample" or type(now) not in (int, float)
                    or not math.isfinite(now) or now <= previous_time):
                raise ValueError(f"invalid or non-monotonic time on line {line_no}")
            identity = sample.get("custom_data")
            if not isinstance(identity, str):
                raise ValueError(f"missing customData on line {line_no}")
            attempt = None
            if identity.startswith(PREFIX) and identity[len(PREFIX):].isdigit():
                attempt = int(identity[len(PREFIX):])
            if not isinstance(sample.get("contacts"), list):
                raise ValueError(f"missing contacts on line {line_no}")
            if not isinstance(sample.get("velocity"), list) or len(sample["velocity"]) != 6:
                raise ValueError(f"incomplete native velocity on line {line_no}")
            if not isinstance(sample.get("orientation"), list) or len(sample["orientation"]) != 9:
                raise ValueError(f"incomplete orientation on line {line_no}")
            pos = _numeric_position(sample)
            key = str(attempt) if attempt is not None else "unattributed"
            row = groups.setdefault(key, {"samples": 0, "first_time": now,
                                          "last_time": now, "samples_with_contacts": 0,
                                          "first_contact": None, "last_contact": None,
                                          "largest_observed_xyz_jump": None,
                                          "last_sample": None})
            row["samples"] += 1
            row["last_time"] = now
            row["last_sample"] = {"time": now, "position": sample.get("position"),
                                  "orientation": sample["orientation"],
                                  "velocity": sample["velocity"],
                                  "contacts": sample["contacts"]}
            if sample["contacts"]:
                row["samples_with_contacts"] += 1
                if row["first_contact"] is None:
                    row["first_contact"] = {"time": now, "position": sample.get("position"),
                                            "velocity": sample["velocity"],
                                            "contacts": sample["contacts"]}
                row["last_contact"] = {"time": now, "position": sample.get("position"),
                                        "velocity": sample["velocity"],
                                        "contacts": sample["contacts"]}
            if pos is not None and previous_position is not None and previous_identity == key:
                jump = math.dist(pos, previous_position)
                old = row["largest_observed_xyz_jump"]
                if old is None or jump > old["distance_m"]:
                    row["largest_observed_xyz_jump"] = {
                        "distance_m": jump, "from": previous_sample,
                        "to": {"time": now, "position": pos, "orientation": sample["orientation"],
                               "velocity": sample["velocity"], "contacts": sample["contacts"]}}
            previous_time, previous_identity, previous_position = now, key, pos
            previous_sample = {"time": now, "position": pos,
                               "orientation": sample["orientation"],
                               "velocity": sample["velocity"], "contacts": sample["contacts"]}
            total += 1
    if not total:
        raise ValueError("no native observer samples")
    return {"schema": "webeeblocks-reset-native-forensics-v1",
            "scope": "observations_only; not RESET request/ACK or stability oracle",
            "source_sha256": digest.hexdigest(), "samples": total,
            "step_ms": HEADER["step_ms"], "attempts": groups}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(summarize(args.trace), indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
