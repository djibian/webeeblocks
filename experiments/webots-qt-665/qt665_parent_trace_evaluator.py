#!/usr/bin/env python3
"""Evaluate counterexample without accepting mere SIGSEGV or missing frames."""
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    evidence = json.loads(args.trace.read_text())
    events = evidence["events"]
    marks = {e["phase"]: e for e in events
             if e["kind"] == "marker" and e.get("phase") in (30,31,32,33,34)}
    if any(i not in marks for i in (30,31,33)):
        print("QT665_PARENT_COUNTEREXAMPLE=UNPROVEN missing entry/callback/destructor")
        raise SystemExit(45)
    before, call, deleted = [marks[i] for i in (30,31,33)]
    if not before["sequence"] < call["sequence"] < deleted["sequence"]:
        print("QT665_PARENT_COUNTEREXAMPLE=UNPROVEN invalid ordering")
        raise SystemExit(46)
    if not call["inside_setValue"] or not deleted["inside_setValue"]:
        print("QT665_PARENT_COUNTEREXAMPLE=UNPROVEN no genuine protected modal stack")
        raise SystemExit(47)
    if any(marks[i]["bar"] != before["bar"] for i in (31,33)):
        print("QT665_PARENT_COUNTEREXAMPLE=UNPROVEN object mismatch")
        raise SystemExit(48)
    maxima = [e for e in events if e["kind"] == "maximum" 
        and e.get("bar") == before["bar"] and e["inside_setValue"]
        and e["sequence"] > deleted["sequence"]]
    print("QT665_PARENT_DESTRUCTION_DURING_SET_VALUE=CONFIRMED")
    print("QT665_PARENT_OLD_BAR_MAXIMUM_AFTER_DESTRUCTION=" +
          ("CONFIRMED" if maxima else "NOT_OBSERVED"))
    # The parent destruction itself is a safety counterexample regardless of
    # whether execution reached maximum after the invalidation.
    print("QT665_PARENT_COUNTEREXAMPLE=CONFIRMED")

if __name__ == "__main__":
    main()
