#!/usr/bin/env python3
"""Bounded pre-controller Webots process census for one original CI execution.

Observation only. Do not inspect command lines, environments, memory or process
arguments; a missing census is not evidence of healthy native startup.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

VISIBLE = frozenset({
    "Xvfb", "xvfb-run", "webots", "webots-bin", "crazyflie_runtime", "crazyflie_runti",
    "runtime_v2_outc", "runtime_v2_outcome_probe", "chrome", "chrome-wrapper",
    "google-chrome", "chromium", "chromium-browser",
})
RESOURCE_FILES = ("pids.current", "pids.events", "memory.current", "memory.events")


def read_limited(path: Path, maximum: int = 4096) -> str | None:
    try:
        with path.open("rb") as stream:
            return stream.read(maximum + 1)[:maximum].decode("utf-8", "replace")
    except OSError:
        return None


def parse_stat(value: str) -> dict | None:
    # /proc/PID/stat can contain spaces and ')' in the comm field.
    if ") " not in value or "(" not in value:
        return None
    try:
        fields = value.rsplit(") ", 1)[1].split()
        return {
            "state": fields[0], "ppid": int(fields[1]),
            "start_ticks": int(fields[19]),
        }
    except (ValueError, IndexError):
        return None


def snapshot(proc: Path = Path("/proc"),
             cgroup: Path = Path("/sys/fs/cgroup")) -> dict:
    membership = read_limited(proc / "self/cgroup")
    resources = {name: read_limited(cgroup / name) for name in RESOURCE_FILES}
    result = {"status": "ok", "membership_observed": bool(membership),
              "processes": [], "resources": resources, "scan_errors": 0}
    if not membership:
        result["status"] = "partial"
        return result
    try:
        entries = sorted((p for p in proc.iterdir() if p.name.isdecimal()),
                         key=lambda p: int(p.name))
    except OSError:
        result["status"] = "partial"
        return result
    for path in entries:
        name = read_limited(path / "comm", 128)
        if name is None:
            result["scan_errors"] += 1
            continue
        if name.strip() not in VISIBLE:
            continue
        other = read_limited(path / "cgroup")
        stat = read_limited(path / "stat", 4096)
        parsed = parse_stat(stat or "")
        if other is None or parsed is None:
            result["scan_errors"] += 1
            continue
        if other != membership:
            continue
        result["processes"].append({
            "pid": int(path.name), "comm": name.strip(), **parsed,
        })
    if result["scan_errors"]:
        result["status"] = "partial"
    return result


def observe(output: Path, interval: float, max_samples: int) -> None:
    started = time.monotonic()
    with output.open("x", encoding="utf-8") as stream:
        for index in range(max_samples):
            state = snapshot()
            state["sample"] = index
            state["elapsed_s"] = round(time.monotonic() - started, 3)
            stream.write(json.dumps(state, sort_keys=True) + "\n")
            stream.flush()
            if index + 1 < max_samples:
                time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--max-samples", type=int, default=84)
    args = parser.parse_args()
    if (args.interval < 0.25 or args.interval > 2.0
            or args.max_samples < 1 or args.max_samples > 100):
        parser.error("unbounded startup observation")
    observe(args.output, args.interval, args.max_samples)
