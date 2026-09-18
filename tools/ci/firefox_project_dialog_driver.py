#!/usr/bin/env python3
"""Drive the exact Qt project-file dialogs in the private CI Xvfb display."""

from __future__ import annotations

import argparse
import ctypes as C
import json
from pathlib import Path
import time


X_BAD_WINDOW = 3


class Attributes(C.Structure):
    _fields_ = [(name, kind) for name, kind in (
        ("x", C.c_int), ("y", C.c_int), ("width", C.c_int), ("height", C.c_int),
        ("border_width", C.c_int), ("depth", C.c_int), ("visual", C.c_void_p), ("root", C.c_ulong),
        ("window_class", C.c_int), ("bit_gravity", C.c_int), ("win_gravity", C.c_int),
        ("backing_store", C.c_int), ("backing_planes", C.c_ulong), ("backing_pixel", C.c_ulong),
        ("save_under", C.c_int), ("colormap", C.c_ulong), ("map_installed", C.c_int),
        ("map_state", C.c_int), ("all_event_masks", C.c_long), ("your_event_mask", C.c_long),
        ("do_not_propagate_mask", C.c_long), ("override_redirect", C.c_int), ("screen", C.c_void_p))]


class XErrorEvent(C.Structure):
    _fields_ = [
        ("type", C.c_int),
        ("display", C.c_void_p),
        ("resourceid", C.c_ulong),
        ("serial", C.c_ulong),
        ("error_code", C.c_ubyte),
        ("request_code", C.c_ubyte),
        ("minor_code", C.c_ubyte),
    ]


XErrorHandler = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(XErrorEvent))


def classify_window_probe_error(error, window):
    """Return stale only for BadWindow on the exact volatile XID being probed."""
    if error is None:
        return False
    error_code, resourceid, request_code, minor_code = error
    if error_code == X_BAD_WINDOW and resourceid == window:
        return True
    raise RuntimeError(
        "unexpected X11 error while probing window "
        f"{window:#x}: code={error_code} resource={resourceid:#x} "
        f"request={request_code} minor={minor_code}"
    )


class XDriver:
    def __init__(self):
        self.x = C.CDLL("libX11.so.6")
        self.xt = C.CDLL("libXtst.so.6")
        pointer, window, integer = C.c_void_p, C.c_ulong, C.c_int
        self.bind(self.x, "XOpenDisplay", pointer, C.c_char_p)
        self.bind(self.x, "XDefaultRootWindow", window, pointer)
        self.bind(self.x, "XQueryTree", integer, pointer, window, C.POINTER(window), C.POINTER(window), C.POINTER(C.POINTER(window)), C.POINTER(C.c_uint))
        self.bind(self.x, "XGetWindowAttributes", integer, pointer, window, C.POINTER(Attributes))
        self.bind(self.x, "XFetchName", integer, pointer, window, C.POINTER(C.c_char_p))
        self.bind(self.x, "XFree", integer, pointer)
        self.bind(self.x, "XSetInputFocus", integer, pointer, window, integer, window)
        self.bind(self.x, "XSync", integer, pointer, integer)
        self.bind(self.x, "XKeysymToKeycode", C.c_ubyte, pointer, window)
        self.bind(self.x, "XCreateSimpleWindow", window, pointer, window, integer, integer, C.c_uint, C.c_uint, C.c_uint, C.c_ulong, C.c_ulong)
        self.bind(self.x, "XDestroyWindow", integer, pointer, window)
        self.bind(self.xt, "XTestFakeKeyEvent", integer, pointer, C.c_uint, integer, C.c_ulong)
        self.bind(self.xt, "XTestQueryExtension", integer, pointer, C.POINTER(integer), C.POINTER(integer), C.POINTER(integer), C.POINTER(integer))
        # XSetErrorHandler returns the previous process-global handler. Use a raw
        # pointer so the exact previous handler can be restored after each scoped
        # volatile-window query.
        self.x.XSetErrorHandler.restype = C.c_void_p
        self.x.XSetErrorHandler.argtypes = [C.c_void_p]
        self._probe_error = None
        self._probe_handler = XErrorHandler(self._capture_probe_error)
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("Xvfb display unavailable")
        args = [integer() for _ in range(4)]
        if not self.xt.XTestQueryExtension(self.display, *(C.byref(a) for a in args)):
            raise RuntimeError("XTEST unavailable")
        self.root = self.x.XDefaultRootWindow(self.display)

    @staticmethod
    def bind(library, name, result, *arguments):
        function = getattr(library, name)
        function.restype, function.argtypes = result, arguments

    def _capture_probe_error(self, _display, event):
        value = event.contents
        self._probe_error = (
            int(value.error_code),
            int(value.resourceid),
            int(value.request_code),
            int(value.minor_code),
        )
        return 0

    def _volatile_window_query(self, window, operation):
        # XQueryTree returns a snapshot. A child can disappear before its name or
        # attributes are queried. Scope error interception to this single query,
        # force asynchronous errors through XSync, then restore the prior handler.
        # Only BadWindow for this exact XID is treated as a stale snapshot entry.
        self._probe_error = None
        previous = self.x.XSetErrorHandler(C.cast(self._probe_handler, C.c_void_p))
        try:
            result = operation()
            self.x.XSync(self.display, 0)
        finally:
            self.x.XSetErrorHandler(previous)
        error = self._probe_error
        self._probe_error = None
        if classify_window_probe_error(error, window):
            return None
        return result

    def windows(self):
        root, parent, children, count = C.c_ulong(), C.c_ulong(), C.POINTER(C.c_ulong)(), C.c_uint()
        if not self.x.XQueryTree(self.display, self.root, C.byref(root), C.byref(parent), C.byref(children), C.byref(count)):
            raise RuntimeError("X11 window enumeration failed")
        try:
            return [children[i] for i in range(count.value)]
        finally:
            if children:
                self.x.XFree(children)

    def mapped_window(self, title):
        wanted = title.encode()
        for window in self.windows():
            actual = C.c_char_p()
            fetched = self._volatile_window_query(
                window,
                lambda: self.x.XFetchName(self.display, window, C.byref(actual)),
            )
            if fetched is None:
                continue
            if not fetched or not actual:
                continue
            try:
                matches = actual.value == wanted
            finally:
                self.x.XFree(actual)
            if not matches:
                continue
            attributes = Attributes()
            got_attributes = self._volatile_window_query(
                window,
                lambda: self.x.XGetWindowAttributes(self.display, window, C.byref(attributes)),
            )
            if got_attributes is None:
                continue
            if got_attributes and attributes.map_state == 2:
                if attributes.width >= 200 and attributes.height >= 100:
                    return window
        return None

    def key(self, keysym, down):
        code = self.x.XKeysymToKeycode(self.display, keysym)
        if not code or not self.xt.XTestFakeKeyEvent(self.display, code, 1 if down else 0, 0):
            raise RuntimeError(f"XTEST key event failed for keysym {keysym:#x}")

    def chord(self, modifier, key):
        self.key(modifier, True)
        self.key(key, True)
        self.key(key, False)
        self.key(modifier, False)

    def type_ascii(self, text):
        for char in text:
            value = ord(char)
            if value < 0x20 or value > 0x7e or char.isupper() or char == '_':
                raise RuntimeError(f"unsupported deterministic path character: {char!r}")
            self.key(value, True)
            self.key(value, False)

    def focus(self, window):
        self.x.XSetInputFocus(self.display, window, 2, 0)
        self.x.XSync(self.display, 0)

    def accept_path(self, window, path):
        self.focus(window)
        self.chord(0xffe3, ord('a'))
        self.type_ascii(path)
        self.key(0xff0d, True)
        self.key(0xff0d, False)
        self.x.XSync(self.display, 0)

    def cancel(self, window):
        self.focus(window)
        self.key(0xff1b, True)
        self.key(0xff1b, False)
        self.x.XSync(self.display, 0)


def wait_window(driver, title, deadline):
    while time.monotonic() < deadline:
        window = driver.mapped_window(title)
        if window:
            return window
        time.sleep(0.05)
    raise RuntimeError(f"timed out waiting for dialog: {title}")


def wait_closed(driver, title, window, deadline):
    while time.monotonic() < deadline:
        current = driver.mapped_window(title)
        if current != window:
            return
        time.sleep(0.05)
    raise RuntimeError(f"dialog did not close: {title}")


def prepare_invalid_projects(roundtrip: Path, malformed: Path, unsupported: Path, unknown: Path):
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if roundtrip.exists() and roundtrip.stat().st_size:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("roundtrip.wbb was not written by Save As")
    payload = json.loads(roundtrip.read_text(encoding="utf-8"))
    malformed.write_text("{bad json", encoding="utf-8")
    bad_version = json.loads(json.dumps(payload))
    bad_version["version"] = 999
    unsupported.write_text(json.dumps(bad_version, separators=(",", ":")), encoding="utf-8")
    bad_activity = json.loads(json.dumps(payload))
    bad_activity["activity"]["id"] = "unknown-profile"
    unknown.write_text(json.dumps(bad_activity, separators=(",", ":")), encoding="utf-8")


def run_self_test():
    window = 0x20001B
    assert classify_window_probe_error(None, window) is False
    assert classify_window_probe_error((X_BAD_WINDOW, window, 20, 0), window) is True
    for error in (
        (X_BAD_WINDOW, window + 1, 20, 0),
        (2, window, 20, 0),
    ):
        try:
            classify_window_probe_error(error, window)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"unexpected X11 error was suppressed: {error}")
    print("PASS: only exact-XID BadWindow is tolerated by volatile dialog discovery.")
    return 0


def call_with_sentinel_handler(driver, operation):
    """Run one probe while proving _volatile_window_query restores its caller handler."""
    leaked_errors = []

    def capture(_display, event):
        value = event.contents
        leaked_errors.append((int(value.error_code), int(value.resourceid)))
        return 0

    sentinel = XErrorHandler(capture)
    sentinel_pointer = C.cast(sentinel, C.c_void_p).value
    previous = driver.x.XSetErrorHandler(C.cast(sentinel, C.c_void_p))
    result = None
    caught = None
    try:
        result = operation()
    except Exception as error:  # re-raised after restoring the process-global handler
        caught = error
    current = driver.x.XSetErrorHandler(previous)
    if current != sentinel_pointer:
        raise AssertionError("scoped X11 probe did not restore the previous error handler")
    if leaked_errors:
        raise AssertionError(f"probe error escaped scoped handler: {leaked_errors}")
    if caught is not None:
        raise caught
    return result


def run_x11_self_test(driver):
    """Exercise the real Xlib handler boundary against deterministic X server errors."""
    stale = driver.x.XCreateSimpleWindow(
        driver.display, driver.root, 0, 0, 8, 8, 0, 0, 0,
    )
    if not stale:
        raise RuntimeError("failed to create deterministic stale-window fixture")
    driver.x.XDestroyWindow(driver.display, stale)
    driver.x.XSync(driver.display, 0)

    actual = C.c_char_p()
    result = call_with_sentinel_handler(
        driver,
        lambda: driver._volatile_window_query(
            stale,
            lambda: driver.x.XFetchName(driver.display, stale, C.byref(actual)),
        ),
    )
    if result is not None:
        if actual:
            driver.x.XFree(actual)
        raise AssertionError("destroyed XID was not classified as a stale window")

    try:
        call_with_sentinel_handler(
            driver,
            lambda: driver._volatile_window_query(
                driver.root,
                lambda: driver.x.XSetInputFocus(driver.display, driver.root, 99, 0),
            ),
        )
    except RuntimeError as error:
        if "code=3" in str(error):
            raise AssertionError(f"expected non-BadWindow X error, got: {error}") from error
    else:
        raise AssertionError("non-BadWindow X error was suppressed by scoped probe")

    print(
        "PASS: real scoped Xlib probe consumes exact stale BadWindow, restores handler, "
        "and surfaces other X errors.",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root')
    parser.add_argument('--timeout', type=float, default=75.0)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    if not args.root:
        parser.error('--root is required unless --self-test is used')
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    roundtrip_path = (root / 'roundtrip.wbb').resolve()
    malformed_path = (root / 'malformed.wbb').resolve()
    unsupported_path = (root / 'unsupported.wbb').resolve()
    unknown_path = (root / 'unknown-activity.wbb').resolve()
    roundtrip = str(roundtrip_path)
    malformed = str(malformed_path)
    unsupported = str(unsupported_path)
    unknown = str(unknown_path)
    for value in (roundtrip, malformed, unsupported, unknown):
        if '_' in value or any(c.isupper() for c in value):
            raise RuntimeError('test path must remain lowercase ASCII without underscore')

    plan = [
        ('Enregistrer le projet WebeeBlocks', 'accept', roundtrip),
        ('Enregistrer le projet WebeeBlocks', 'cancel', None),
        ('Ouvrir un projet WebeeBlocks', 'cancel', None),
        ('Ouvrir un projet WebeeBlocks', 'accept', roundtrip),
        ('Ouvrir un projet WebeeBlocks', 'accept', malformed),
        ('Ouvrir un projet WebeeBlocks', 'accept', unsupported),
        ('Ouvrir un projet WebeeBlocks', 'accept', unknown),
    ]
    driver = XDriver()
    run_x11_self_test(driver)
    overall = time.monotonic() + args.timeout
    for index, (title, action, path) in enumerate(plan, 1):
        window = wait_window(driver, title, overall)
        if action == 'accept':
            driver.accept_path(window, path)
        else:
            driver.cancel(window)
        wait_closed(driver, title, window, overall)
        print(f'DIALOG_STEP_OK {index} {action} {title}', flush=True)
        if index == 4:
            prepare_invalid_projects(roundtrip_path, malformed_path, unsupported_path, unknown_path)
            print('INVALID_PROJECT_FIXTURES_READY', flush=True)
    print('FIREFOX_DIALOG_PLAN_COMPLETE', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
