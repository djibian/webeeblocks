# GDB 12.1 discriminator for QT665. Not a smoke/no-SIGSEGV test.
# Run only on generated qt665-guarded-methods built from patched R2025a.
import gdb
import json
import os
from pathlib import Path

events = []
next_sequence = 0
out = Path(os.environ.get("QT665_TRACE_PATH", "qt665-trace.json"))
exit_code = None

def stack():
    names = []
    frame = gdb.newest_frame()
    while frame is not None:
        try:
            names.append(str(frame.name() or "<unknown>"))
            frame = frame.older()
        except gdb.error:
            break
    return names

def emit(kind, **kw):
    global next_sequence
    next_sequence += 1
    names = stack()
    item = {
        "sequence": next_sequence,
        "kind": kind,
        "inside_setValue": any("QProgressDialog::setValue" in name for name in names),
        "inside_window_progress": any("WbMainWindow::setWorldLoadingProgress" in name for name in names),
        "stack": names[:28],
    }
    item.update(kw)
    events.append(item)
    print("QT665_EVENT " + json.dumps(item, sort_keys=True), flush=True)

class Marker(gdb.Breakpoint):
    def __init__(self):
        super().__init__("qt665_marker", internal=False)
        self.silent = True

    def stop(self):
        f = gdb.selected_frame()
        phase = int(f.read_var("phase"))
        dialog = int(f.read_var("dialog"))
        bar = int(f.read_var("bar"))
        emit("marker", phase=phase, dialog=dialog, bar=bar)
        return False

class Maximum(gdb.Breakpoint):
    def __init__(self):
        super().__init__("QProgressBar::maximum() const", internal=False)
        self.silent = True

    def stop(self):
        # Linux x86_64 System V ABI: this is in RDI at entry.
        this = int(gdb.parse_and_eval("$rdi"))
        names = stack()
        if any("QProgressDialog::setValue" in name for name in names):
            emit("maximum", bar=this)
        return False

def exited(event):
    global exit_code
    exit_code = getattr(event, "exit_code", None)
    print("QT665_INFERIOR_EXIT=" + str(exit_code), flush=True)

gdb.events.exited.connect(exited)
gdb.execute("set pagination off")
gdb.execute("set confirm off")
gdb.execute("set breakpoint pending on")
gdb.execute("set print thread-events off")
gdb.execute("set disable-randomization off")
Marker()
Maximum()
gdb.execute("run")

def check():
    issues = []
    marks = {event["phase"]: event for event in events
             if event["kind"] == "marker"}
    positive = [10, 11, 12, 13, 14, 15]
    negative = [20, 21, 22, 23, 24, 25]
    for phase in positive + negative:
        if phase not in marks:
            issues.append("missing_marker_" + str(phase))
    if len([e for e in events if e["kind"] == "marker"]) != 12:
        issues.append("markers_not_exactly_once")
    if all(p in marks for p in positive):
        a = [marks[p] for p in positive]
        if len({m["bar"] for m in a}) != 1 or len({m["dialog"] for m in a}) != 1:
            issues.append("positive_identity_changed")
        if not (a[0]["sequence"] < a[1]["sequence"] < a[2]["sequence"] <
                a[3]["sequence"] < a[4]["sequence"] < a[5]["sequence"]):
            issues.append("positive_order")
        if not marks[11]["inside_setValue"] or not marks[12]["inside_setValue"]:
            issues.append("positive_callback_not_inside_true_Qt_setValue")
        if marks[13]["inside_setValue"] or marks[14]["inside_setValue"]:
            issues.append("return_or_destruction_inside_setValue")
        relevant = [e for e in events if e["kind"] == "maximum"
                    and e["bar"] == marks[10]["bar"]
                    and marks[12]["sequence"] < e["sequence"] < marks[13]["sequence"]]
        if not relevant:
            issues.append("no_old_bar_maximum_after_retirement_inside_setValue")
        if relevant and not all(e["sequence"] < marks[14]["sequence"] for e in relevant):
            issues.append("maximum_after_destruction")
    if all(p in marks for p in negative):
        b = [marks[p] for p in negative]
        if len({m["bar"] for m in b}) != 1:
            issues.append("negative_identity_changed")
        if not all(x["sequence"] < y["sequence"] for x, y in zip(b, b[1:])):
            issues.append("negative_order")
        if marks[21]["inside_setValue"] or marks[22]["inside_setValue"]:
            issues.append("negative_callback_inside_setValue_should_be_outer")
        if not marks[21]["inside_window_progress"]:
            issues.append("negative_not_in_outer_window_progress")
        false_max = [e for e in events if e["kind"] == "maximum"
                     and e["bar"] == marks[20]["bar"]
                     and marks[21]["sequence"] < e["sequence"] < marks[23]["sequence"]]
        if false_max:
            issues.append("negative_would_false_positive")
    if exit_code != 0:
        issues.append("cpp_executable_nonzero_or_unknown")
    return issues

issues = check()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"verdict": "PASS" if not issues else "FAIL",
                           "problems": issues, "exit_code": exit_code,
                           "events": events}, indent=2))
print("QT665_CAUSAL_DISCRIMINATOR=" + ("PASS" if not issues else "FAIL"))
for issue in issues:
    print("QT665_DISCRIMINATOR_PROBLEM=" + issue)
gdb.execute("quit " + ("0" if not issues else "41"))
