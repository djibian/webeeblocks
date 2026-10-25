#!/usr/bin/env python3
"""Read-only, request-bound first-contact summary of native progression LAND logs.

Coordinates/velocities are Webots observations, motor fields are commands.
Neither contact points nor motor commands measure impact forces. No mission
outcome, controller decision, success or root cause is inferred here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

LAND = "WEBEEBLOCKS_SEQUENCE_CI_LAND"
NATIVE = "WEBEEBLOCKS_SEQUENCE_CI_LAND_NATIVE"
FLIGHT = ("t", "x", "y", "z", "vx", "vy", "vz", "roll", "pitch",
          "des_vx", "des_vy", "des_z", "motor1", "motor2", "motor3", "motor4")


def fields(line: str, marker: str) -> dict[str, str]:
    parts = line.split()
    if not parts or parts[0] != marker:
        raise ValueError("wrong trace marker")
    found = {}
    for item in parts[1:]:
        if "=" not in item:
            raise ValueError("invalid trace field")
        key, value = item.split("=", 1)
        if not key or not value or key in found:
            raise ValueError("missing or duplicate trace field")
        found[key] = value
    return found


def integer(value: str) -> int:
    number = int(value)
    if number < 0 or str(number) != value:
        raise ValueError("invalid native integer")
    return number


def finite(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite native observation")
    return number


def summarize(log: str, request_id: int) -> dict:
    if request_id < 1:
        raise ValueError("request_id must be positive")
    pending = None
    rows = []
    last_time = None
    for line in log.splitlines():
        if line.startswith(LAND + " "):
            if pending is not None:
                raise ValueError("unpaired LAND sample")
            part = fields(line, LAND)
            if not set(("id", *FLIGHT)).issubset(part):
                raise ValueError("incomplete LAND flight sample")
            pending = {"id": integer(part["id"])}
            pending.update({key: finite(part[key]) for key in FLIGHT})
        elif line.startswith(NATIVE + " "):
            if pending is None:
                raise ValueError("orphan native contact sample")
            part = fields(line, NATIVE)
            if not {"id", "t", "status", "contacts", "shown"}.issubset(part):
                raise ValueError("incomplete native contact sample")
            if integer(part["id"]) != pending["id"] or abs(finite(part["t"]) - pending["t"]) > 1e-9:
                raise ValueError("LAND/contact sample identity mismatch")
            if part["status"] not in ("OBSERVED", "UNPROVEN"):
                raise ValueError("unknown native observation status")
            # Webots may return -1 for an unavailable contact list.
            # This is missing evidence, never a proof of zero contacts.
            if (part["contacts"], part["shown"], part["status"]) == ("-1", "-1", "UNPROVEN"):
                count, shown = None, -1
            else:
                count, shown = integer(part["contacts"]), integer(part["shown"])
                if shown != min(count, 6):
                    raise ValueError("inconsistent contact count")
            if part["status"] == "OBSERVED":
                if "velocity" not in part:
                    raise ValueError("missing native velocity")
                velocities = part["velocity"].split(",")
                if len(velocities) != 6:
                    raise ValueError("incomplete supervisor velocity")
                for item in velocities:
                    finite(item)
                for index in range(shown):
                    point = part.get("cp" + str(index))
                    if point is None or ":" not in point:
                        raise ValueError("missing contact geometry")
                    node_id, coords = point.split(":", 1)
                    integer(node_id)
                    axes = coords.split(",")
                    if len(axes) != 3:
                        raise ValueError("incomplete contact geometry")
                    for item in axes:
                        finite(item)
            pending.update(status=part["status"], contacts=count)
            if last_time is not None and pending["t"] <= last_time:
                raise ValueError("nonmonotonic native LAND time")
            last_time = pending["t"]
            rows.append(pending)
            pending = None
    if pending is not None:
        raise ValueError("truncated LAND/contact evidence")
    selected = [item for item in rows if item["id"] == request_id]
    if not selected:
        raise ValueError("no complete samples for the requested LAND id")
    first_index = next((i for i, item in enumerate(selected)
                        if item["status"] == "OBSERVED" and item["contacts"] > 0), None)
    def concise(item):
        if item is None:
            return None
        return {key: item[key] for key in ("id", "t", "x", "y", "z", "vx",
                                           "vy", "vz", "pitch", "contacts", "status")}
    first = selected[first_index] if first_index is not None else None
    after = (selected[first_index + 1] if first_index is not None and
             first_index + 1 < len(selected) else None)
    return {
        "schema": "webeeblocks-native-land-contact-observation-v1",
        "source_sha256": hashlib.sha256(log.encode("utf-8")).hexdigest(),
        "request_id": request_id,
        "samples": len(selected),
        "unproven_samples": sum(item["status"] == "UNPROVEN" for item in selected),
        "first_observed_contact": concise(first),
        "next_sample": concise(after),
        "unknown_before_first_observed_contact": any(
            item["status"] == "UNPROVEN" for item in selected[:first_index]
        ) if first_index is not None else any(
            item["status"] == "UNPROVEN" for item in selected
        ),
        "scope": "read-only contact/kinematics; no impulse, causality, oracle or PASS",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("webots_log", type=Path)
    parser.add_argument("--request-id", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.webots_log.read_bytes().decode("utf-8"),
                               args.request_id), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
