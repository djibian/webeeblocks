#!/usr/bin/env python3
"""Fail-closed parent-delete true Qt frame safety evaluator.

The historical original-patch counterexample (run 40352255637) showed a
destructor followed by maximum on the same bar while setValue was active.
A strengthened candidate must prove the opposite with full ordering.
"""
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text())
    events = trace["events"]
    marks = {e["phase"]: e for e in events
             if e["kind"] == "marker" and e.get("phase") in (30,31,32,33,34,35)}
    if any(i not in marks for i in (30,31,32,33,34,35)):
        print("QT665_PARENT_SHUTDOWN=UNPROVEN missing markers")
        raise SystemExit(45)
    if len([e for e in events if e["kind"] == "marker"]) != 6:
        print("QT665_PARENT_SHUTDOWN=UNPROVEN repeated markers")
        raise SystemExit(46)
    bar = marks[30]["bar"]
    if any(marks[i]["bar"] != bar for i in marks):
        print("QT665_PARENT_SHUTDOWN=UNPROVEN object mismatch")
        raise SystemExit(47)
    if not (marks[30]["sequence"] < marks[31]["sequence"] <
            marks[32]["sequence"] < marks[34]["sequence"] <
            marks[33]["sequence"] < marks[35]["sequence"]):
        print("QT665_PARENT_SHUTDOWN=FAIL early child destruction or invalid ordering")
        raise SystemExit(48)
    if not marks[31]["inside_setValue"] or not marks[32]["inside_setValue"]:
        print("QT665_PARENT_SHUTDOWN=UNPROVEN callback not in true Qt setValue")
        raise SystemExit(49)
    if marks[34]["inside_setValue"] or marks[33]["inside_setValue"]:
        print("QT665_PARENT_SHUTDOWN=FAIL bar destroyed before setValue return")
        raise SystemExit(50)
    maxima = [e for e in events if e["kind"] == "maximum"
        and e.get("bar") == bar and e["inside_setValue"]
        and marks[32]["sequence"] < e["sequence"] < marks[34]["sequence"]]
    if not maxima:
        print("QT665_PARENT_SHUTDOWN=UNPROVEN no same-bar maximum after parent retirement")
        raise SystemExit(51)
    if trace["exit_code"] != 0:
        print("QT665_PARENT_SHUTDOWN=UNPROVEN executable failure")
        raise SystemExit(52)
    print("QT665_PARENT_LIVE_BAR_MAXIMUM_INSIDE_SET_VALUE=PASS")
    print("QT665_PARENT_DEFERRED_DELETE_AFTER_RETURN=PASS")
    print("QT665_PARENT_SHUTDOWN=PASS")

if __name__ == "__main__":
    main()
