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

# The parent-specific semantic oracle runs AFTER the debugger exits;
# unlike the positive modal discriminator it expects markers 30..35.
if exit_code != 0:
    print("QT665_PARENT_GDB_INFERIOR=FAIL")
    gdb.execute('quit 62')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"exit_code": exit_code, "events": events}, indent=2))
print("QT665_PARENT_GDB_TRACE_CAPTURED=PASS")
gdb.execute('quit 0')
