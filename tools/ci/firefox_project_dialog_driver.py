#!/usr/bin/env python3
"""Drive the exact Qt project-file dialogs in the private CI Xvfb display."""

from __future__ import annotations

import argparse
import ctypes as C
from pathlib import Path
import time


class Attributes(C.Structure):
    _fields_ = [(name, kind) for name, kind in (
        ("x", C.c_int), ("y", C.c_int), ("width", C.c_int), ("height", C.c_int),
        ("border_width", C.c_int), ("depth", C.c_int), ("visual", C.c_void_p), ("root", C.c_ulong),
        ("window_class", C.c_int), ("bit_gravity", C.c_int), ("win_gravity", C.c_int),
        ("backing_store", C.c_int), ("backing_planes", C.c_ulong), ("backing_pixel", C.c_ulong),
        ("save_under", C.c_int), ("colormap", C.c_ulong), ("map_installed", C.c_int),
        ("map_state", C.c_int), ("all_event_masks", C.c_long), ("your_event_mask", C.c_long),
        ("do_not_propagate_mask", C.c_long), ("override_redirect", C.c_int), ("screen", C.c_void_p))]


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
        self.bind(self.xt, "XTestFakeKeyEvent", integer, pointer, C.c_uint, integer, C.c_ulong)
        self.bind(self.xt, "XTestQueryExtension", integer, pointer, C.POINTER(integer), C.POINTER(integer), C.POINTER(integer), C.POINTER(integer))
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
            if not self.x.XFetchName(self.display, window, C.byref(actual)) or not actual:
                continue
            try:
                matches = actual.value == wanted
            finally:
                self.x.XFree(actual)
            if not matches:
                continue
            attributes = Attributes()
            if self.x.XGetWindowAttributes(self.display, window, C.byref(attributes)) and attributes.map_state == 2:
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--timeout', type=float, default=75.0)
    args = parser.parse_args()
    root = Path(args.root)
    roundtrip = str((root / 'roundtrip.wbb').resolve())
    malformed = str((root / 'malformed.wbb').resolve())
    unsupported = str((root / 'unsupported.wbb').resolve())
    unknown = str((root / 'unknown-activity.wbb').resolve())
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
    print('FIREFOX_DIALOG_PLAN_COMPLETE', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
