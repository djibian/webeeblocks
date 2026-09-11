#!/usr/bin/env python3
"""Single research qualification of the real C10 provider in official Webots."""

from __future__ import annotations

import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def prepare(project, evidence):
    source = project / "controllers/qt_provider_probe/file_broker.cpp"
    original = source.read_text()
    assert original.count("namespace {") == 1
    assert original.count("    std::fflush(stdout);") == 1
    patched = original.replace("namespace {", '#include "dialog_qualification.hpp"\n\nnamespace {')
    patched = patched.replace("    std::fflush(stdout);", "    std::fflush(stdout);\n    qualify_dialog(*mDialog);")
    source.write_text(patched)
    (evidence / "provider-original.cpp").write_text(original)
    (evidence / "provider-qualified.cpp").write_text(patched)
    (project / "worlds/qualification.wbt").write_text('''#VRML_SIM R2025a utf8
WorldInfo { basicTimeStep 32 }
Viewpoint { position 1 1 1 }
Robot {
  name "Q87 provider qualification"
  controller "qt_provider_probe"
  supervisor TRUE
  window "<none>"
}
''')


def inspect(project, evidence, webots):
    relocations = (evidence / "relocations.txt").read_text()
    dynamic = (evidence / "dynamic.txt").read_text()
    symbols = (evidence / "symbols.txt").read_text()
    closure = (evidence / "ldd.txt").read_text()
    copies = [line for line in relocations.splitlines() if "R_X86_64_COPY" in line]
    assert not any(re.search(r"\bQ[A-Za-z]|Qt_6", line) for line in copies), copies
    assert not re.search(r"\((RPATH|RUNPATH)\)", dynamic), dynamic
    for name in ("QCoreApplication::instance()", "qobject_cast<QApplication*>",
                 "QApplication::staticMetaObject", "webeeblocks::createQtFileDialogProvider()",
                 "wb_file_broker_create_qt", "qualify_dialog(QFileDialog&)"):
        assert name in symbols, name
    assert "not found" not in closure, closure
    for library in ("libQt6Core.so.6", "libQt6Gui.so.6", "libQt6Widgets.so.6"):
        assert f"{library} => {webots}/lib/webots/{library}" in closure, library
    assert f"libController.so => {webots}/lib/controller/libController.so" in closure
    binary = project / "controllers/qt_provider_probe/qt_provider_probe"
    write_json(evidence / "static-proof.json", {
        "qt_copy_relocations": [], "required_provider_roots_retained": True,
        "runtime_paths_added": False, "bundled_qt_and_controller_resolved": True,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "github_event_sha": os.environ.get("GITHUB_SHA"),
        "candidate_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    })


class Attributes(C.Structure):
    _fields_ = [(name, kind) for name, kind in (
        ("x", C.c_int), ("y", C.c_int), ("width", C.c_int), ("height", C.c_int),
        ("border_width", C.c_int), ("depth", C.c_int), ("visual", C.c_void_p), ("root", C.c_ulong),
        ("window_class", C.c_int), ("bit_gravity", C.c_int), ("win_gravity", C.c_int),
        ("backing_store", C.c_int), ("backing_planes", C.c_ulong), ("backing_pixel", C.c_ulong),
        ("save_under", C.c_int), ("colormap", C.c_ulong), ("map_installed", C.c_int),
        ("map_state", C.c_int), ("all_event_masks", C.c_long), ("your_event_mask", C.c_long),
        ("do_not_propagate_mask", C.c_long), ("override_redirect", C.c_int), ("screen", C.c_void_p))]


class XObserver:
    """Observe only the exact test controller's dialog in this private Xvfb."""

    def __init__(self):
        self.x = C.CDLL("libX11.so.6")
        self.xt = C.CDLL("libXtst.so.6")
        pointer, window, integer = C.c_void_p, C.c_ulong, C.c_int
        self.bind(self.x, "XOpenDisplay", pointer, C.c_char_p)
        self.bind(self.x, "XDefaultRootWindow", window, pointer)
        self.bind(self.x, "XQueryTree", integer, pointer, window, C.POINTER(window), C.POINTER(window), C.POINTER(C.POINTER(window)), C.POINTER(C.c_uint))
        self.bind(self.x, "XGetWindowAttributes", integer, pointer, window, C.POINTER(Attributes))
        self.bind(self.x, "XFetchName", integer, pointer, window, C.POINTER(C.c_char_p))
        self.bind(self.x, "XInternAtom", window, pointer, C.c_char_p, integer)
        self.bind(self.x, "XGetWindowProperty", integer, pointer, window, window, C.c_long, C.c_long, integer,
                  window, C.POINTER(window), C.POINTER(integer), C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(pointer))
        self.bind(self.x, "XFree", integer, pointer)
        self.bind(self.x, "XSetInputFocus", integer, pointer, window, integer, window)
        self.bind(self.x, "XGetInputFocus", integer, pointer, C.POINTER(window), C.POINTER(integer))
        self.bind(self.x, "XSync", integer, pointer, integer)
        self.bind(self.x, "XKeysymToKeycode", C.c_ubyte, pointer, window)
        self.bind(self.xt, "XTestFakeKeyEvent", integer, pointer, C.c_uint, integer, C.c_ulong)
        self.bind(self.xt, "XTestQueryExtension", integer, pointer, C.POINTER(integer), C.POINTER(integer), C.POINTER(integer), C.POINTER(integer))
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("the preserved Xvfb display is unavailable")
        args = [integer() for _ in range(4)]
        if not self.xt.XTestQueryExtension(self.display, *(C.byref(a) for a in args)):
            raise RuntimeError("XTEST is unavailable; no substitute cancellation")
        self.root = self.x.XDefaultRootWindow(self.display)
        self.pid_atom = self.x.XInternAtom(self.display, b"_NET_WM_PID", 0)

    @staticmethod
    def bind(library, name, result, *arguments):
        function = getattr(library, name)
        function.restype, function.argtypes = result, arguments

    def windows(self):
        root, parent, children, count = C.c_ulong(), C.c_ulong(), C.POINTER(C.c_ulong)(), C.c_uint()
        if not self.x.XQueryTree(self.display, self.root, C.byref(root), C.byref(parent), C.byref(children), C.byref(count)):
            raise RuntimeError("X11 window enumeration failed")
        try:
            return [children[i] for i in range(count.value)]
        finally:
            if children:
                self.x.XFree(children)

    def mapped_dialog(self, pid):
        for window in self.windows():
            title = C.c_char_p()
            if not self.x.XFetchName(self.display, window, C.byref(title)) or not title:
                continue
            try:
                matches = title.value == f"WebeeBlocks Q87 qualification {pid}".encode()
            finally:
                self.x.XFree(title)
            if not matches:
                continue
            actual_type, format_, count, remaining, data = C.c_ulong(), C.c_int(), C.c_ulong(), C.c_ulong(), C.c_void_p()
            result = self.x.XGetWindowProperty(self.display, window, self.pid_atom, 0, 1, 0, 6,
                                               C.byref(actual_type), C.byref(format_), C.byref(count), C.byref(remaining), C.byref(data))
            try:
                if result or actual_type.value != 6 or format_.value != 32 or count.value != 1 or remaining.value != 0 or not data:
                    continue
                if C.cast(data, C.POINTER(C.c_ulong))[0] != pid:
                    continue
            finally:
                if data:
                    self.x.XFree(data)
            attributes = Attributes()
            if self.x.XGetWindowAttributes(self.display, window, C.byref(attributes)) and attributes.map_state == 2:
                if attributes.width >= 200 and attributes.height >= 100:
                    return {"window": window, "pid": pid, "map_state": "IsViewable",
                            "width": attributes.width, "height": attributes.height}
        return None

    def cancel(self, witness):
        window = witness["window"]
        if self.mapped_dialog(witness["pid"]) != witness:
            raise RuntimeError("dialog changed before the cancellation effect")
        self.x.XSetInputFocus(self.display, window, 2, 0)
        self.x.XSync(self.display, 0)
        focus, revert = C.c_ulong(), C.c_int()
        self.x.XGetInputFocus(self.display, C.byref(focus), C.byref(revert))
        if focus.value != window:
            raise RuntimeError("exact dialog focus was not established")
        key = self.x.XKeysymToKeycode(self.display, 0xff1b)
        if not key or not self.xt.XTestFakeKeyEvent(self.display, key, 1, 0):
            raise RuntimeError("Escape key press not accepted by XTEST")
        if not self.xt.XTestFakeKeyEvent(self.display, key, 0, 0):
            raise RuntimeError("Escape key release not accepted by XTEST")
        self.x.XSync(self.display, 0)
        return {**witness, "cancel": "XTEST_ESCAPE", "focus_verified": True,
                "host_monotonic_s": time.monotonic()}


def descendant(pid, ancestor):
    for _ in range(12):
        if pid == ancestor:
            return True
        status = Path(f"/proc/{pid}/status").read_text()
        pid = int(re.search(r"^PPid:\s*(\d+)", status, re.M)[1])
        if pid <= 1:
            break
    return False


def evaluate(log, witness, code, unchanged, png_present):
    required = ["Q87 WB_INIT_RETURN", "Q87 PROVIDER_CALLED", "QT_APP_INITIALIZED", "QFILEDIALOG_CONSTRUCTED",
                "Q87 DIALOG_EXEC", "Q87 DIALOG_EXPOSED", "Q87 DIALOG_CANCELLED result=Rejected",
                "Q87 PROVIDER_RETURNED", "Q87 LOOP_RETURN steps=8", "Q87 CAPABILITIES_RETURN operationsReady=false",
                "Q87 PROVIDER_DESTROYED", "Q87 CONTROLLER_COMPLETE"]
    cursor = -1
    for marker in required:
        cursor = log.find(marker, cursor + 1)
        if cursor < 0:
            if "Q87 FATAL" in log and "Q87 PROVIDER_CALLED" in log:
                return "FAIL"
            return "UNPROVEN"
    exposed = re.search(r"Q87 DIALOG_EXPOSED pid=(\d+) wid=(\d+)", log)
    if not witness or not exposed or witness.get("cancel") != "XTEST_ESCAPE" or not witness.get("focus_verified") or witness.get("map_state") != "IsViewable":
        return "UNPROVEN"
    if int(exposed[1]) != witness["pid"] or int(exposed[2]) != witness["window"] or not png_present:
        return "UNPROVEN"
    if not unchanged or code != 0 or "Q87 FATAL" in log:
        return "FAIL"
    movement = re.search(r"Q87 LOOP_RETURN steps=8 before=([0-9.]+) after=([0-9.]+)", log)
    if not movement:
        return "UNPROVEN"
    advance = float(movement[2]) - float(movement[1])
    if not math.isfinite(advance) or not 0.255 <= advance <= 0.257:
        return "FAIL"
    return "PASS"


def snapshot(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}


def run(project, evidence, webots):
    static = json.loads((evidence / "static-proof.json").read_text())
    binary = (project / "controllers/qt_provider_probe/qt_provider_probe").resolve()
    if hashlib.sha256(binary.read_bytes()).hexdigest() != static["binary_sha256"]:
        raise RuntimeError("characterized controller binary changed")
    observer = XObserver()
    before = snapshot(project / "files")
    witness, error, process_proof = None, None, None
    with (evidence / "webots.log").open("w") as log:
        process = subprocess.Popen([str(webots / "webots"), "--stdout", "--stderr", "--batch", "--mode=realtime",
                                    str(project / "worlds/qualification.wbt")], stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 45
        try:
            while process.poll() is None and time.monotonic() < deadline:
                pid_file = evidence / "controller.pid"
                if not witness and pid_file.exists() and pid_file.read_text().strip():
                    pid = int(pid_file.read_text())
                    proc = Path(f"/proc/{pid}")
                    if proc.exists():
                        if (proc / "exe").resolve() != binary or not descendant(pid, process.pid):
                            raise RuntimeError("PID is not the exact official-Webots-launched probe")
                        process_proof = {"pid": pid, "binary": str(binary), "webots_ancestor_pid": process.pid}
                        mapped = observer.mapped_dialog(pid)
                        if mapped and (evidence / "dialog.png").exists():
                            maps = (proc / "maps").read_text()
                            (evidence / "controller-maps.txt").write_text(maps)
                            qt_paths = {line.split()[-1] for line in maps.splitlines() if "libQt6" in line or "libqxcb.so" in line}
                            if not qt_paths or not all(path.startswith(str(webots / "lib/webots") + "/") for path in qt_paths):
                                raise RuntimeError("live Qt/QPA maps differ from the pinned bundle")
                            if not any("libqxcb.so" in path for path in qt_paths):
                                raise RuntimeError("xcb plugin mapping not observed")
                            witness = observer.cancel(mapped)
                            write_json(evidence / "x11-witness.json", witness)
                time.sleep(0.05)
            if process.poll() is None:
                error = "official Webots/probe did not complete within 45 s"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
    text = (evidence / "webots.log").read_text()
    unchanged = snapshot(project / "files") == before
    png = evidence / "dialog.png"
    png_present = png.exists() and png.stat().st_size > 100
    result = evaluate(text, witness, process.returncode, unchanged, png_present)
    if error and result == "PASS":
        result = "UNPROVEN"
    if process_proof is None:
        result = "UNPROVEN"
    write_json(evidence / "result.json", {"result": result, "scope": "Qt provider display/cancel/return only",
        "static_proof": static, "process_proof": process_proof, "x11_witness": witness,
        "project_files_unchanged": unchanged, "webots_exit": process.returncode, "error": error,
        "display": os.environ.get("DISPLAY"), "qpa_override": os.environ.get("QT_QPA_PLATFORM"),
        "full_firefox_parity": "UNPROVEN"})
    print(text)
    print("Q87_QUALIFICATION_RESULT=" + result)
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    mode, project, evidence, *remaining = sys.argv[1:]
    project, evidence = Path(project), Path(evidence)
    if mode == "prepare":
        prepare(project, evidence)
    elif mode == "inspect":
        inspect(project, evidence, Path(remaining[0]))
    elif mode == "run":
        raise SystemExit(run(project, evidence, Path(remaining[0])))
    else:
        raise SystemExit("unknown qualification mode")
