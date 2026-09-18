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


def classify_x_errors(errors, *, context, allow_bad_window=False):
    """Return False only for an allowed stale-window race; raise otherwise."""
    if not errors:
        return True
    if allow_bad_window and all(error[0] == X_BAD_WINDOW for error in errors):
        return False
    rendered = ", ".join(
        f"code={code} resource={resource:#x} request={request} minor={minor}"
        for code, resource, request, minor in errors
    )
    raise RuntimeError(f"X11 error during {context}: {rendered}")


class XDriver:
    def __init__(self):
        self.x = C.CDLL("libX11.so.6")
        self.xt = C.CDLL("libXtst.so.6")
        pointer, window, integer = C.c_void_p, C.c_ulong, C.c_int
        self._error_handler_type = C.CFUNCTYPE(C.c_int, pointer, C.POINTER(XErrorEvent))
        self._x_errors = []
        self._error_handler = self._error_handler_type(self._capture_x_error)
        self.bind(self.x, "XOpenDisplay", pointer, C.c_char_p)
        self.bind(self.x, "XDefaultRootWindow", window, pointer)
        self.bind(self.x, "XQueryTree", integer, pointer, window, C.POINTER(window), C.POINTER(window), C.POINTER(C.POINTER(window)), C.POINTER(C.c_uint))
        self.bind(self.x, "XGetWindowAttributes", integer, pointer, window, C.POINTER(Attributes))
        self.bind(self.x, "XFetchName", integer, pointer, window, C.POINTER(C.c_char_p))
        self.bind(self.x, "XFree", integer, pointer)
        self.bind(self.x, "XSetErrorHandler", C.c_void_p, self._error_handler_type)
        self.bind(self.x, "XSetInputFocus", integer, pointer, window, integer, window)
        self.bind(self.x, "XSync", integer, pointer, integer)
        self.bind(self.x, "XKeysymToKeycode", C.c_ubyte, pointer, window)
        self.bind(self.xt, "XTestFakeKeyEvent", integer, pointer, C.c_uint, integer, C.c_ulong)
        self.bind(self.xt, "XTestQueryExtension", integer, pointer, C.POINTER(integer), C.POINTER(integer), C.POINTER(integer), C.POINTER(integer))
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("Xvfb display unavailable")
        self.x.XSetErrorHandler(self._error_handler)
        args = [integer() for _ in range(4)]
        if not self.xt.XTestQueryExtension(self.display, *(C.byref(a) for a in args)):
            raise RuntimeError("XTEST unavailable")
        self.root = self.x.XDefaultRootWindow(self.display)

    @staticmethod
    def bind(library, name, result, *arguments):
        function = getattr(library, name)
        function.restype, function.argtypes = result, arguments

    def _capture_x_error(self, _display, event):
        self._x_errors.append((
            int(event.contents.error_code),
            int(event.contents.resourceid),
            int(event.contents.request_code),
            int(event.contents.minor_code),
        ))
        return 0

    def _begin_x_request(self):
        self._x_errors.clear()

    def _finish_x_request(self, context, *, allow_bad_window=False):
        self.x.XSync(self.display, 0)
        errors = tuple(self._x_errors)
        self._x_errors.clear()
        return classify_x_errors(errors, context=context, allow_bad_window=allow_bad_window)

    def windows(self):
        root, parent, children, count = C.c_ulong(), C.c_ulong(), C.POINTER(C.c_ulong)(), C.c_uint()
        self._begin_x_request()
        ok = self.x.XQueryTree(self.display, self.root, C.byref(root), C.byref(parent), C.byref(children), C.byref(count))
        self._finish_x_request("XQueryTree")
        if not ok:
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
            self._begin_x_request()
            fetched = self.x.XFetchName(self.display, window, C.byref(actual))
            stable = self._finish_x_request("XFetchName", allow_bad_window=True)
            if not stable:
                if actual:
                    self.x.XFree(actual)
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
            self._begin_x_request()
            got_attributes = self.x.XGetWindowAttributes(self.display, window, C.byref(attributes))
            stable = self._finish_x_request("XGetWindowAttributes", allow_bad_window=True)
            if not stable:
                continue
            if got_attributes and attributes.map_state == 2:
                if attributes.width >= 200 and attributes.height >= 100:
                    return window
        return None

    def key(self, keysym, down):
        code = self.x.XKeysymToKeycode(self.display, keysym)
        if not code:
            raise RuntimeError(f"X11 keycode unavailable for keysym {keysym:#x}")
        self._begin_x_request()
        emitted = self.xt.XTestFakeKeyEvent(self.display, code, 1 if down else 0, 0)
        self._finish_x_request("XTestFakeKeyEvent")
        if not emitted:
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
        self._begin_x_request()
        self.x.XSetInputFocus(self.display, window, 2, 0)
        self._finish_x_request("XSetInputFocus")

    def accept_path(self, window, path):
        self.focus(window)
        self.chord(0xffe3, ord('a'))
        self.type_ascii(path)
        self.key(0xff0d, True)
        self.key(0xff0d, False)

    def cancel(self, window):
        self.focus(window)
        self.key(0xff1b, True)
        self.key(0xff1b, False)


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--timeout', type=float, default=75.0)
    args = parser.parse_args()
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
