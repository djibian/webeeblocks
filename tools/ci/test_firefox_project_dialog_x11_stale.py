#!/usr/bin/env python3
"""Deterministically exercise the scoped X11 stale-window probe boundary."""

from __future__ import annotations

import ctypes as C

from firefox_project_dialog_driver import Attributes, XDriver, XErrorHandler


def main() -> int:
    driver = XDriver()
    pointer, window, integer = C.c_void_p, C.c_ulong, C.c_int
    driver.bind(
        driver.x,
        "XCreateSimpleWindow",
        window,
        pointer,
        window,
        integer,
        integer,
        C.c_uint,
        C.c_uint,
        C.c_uint,
        C.c_ulong,
        C.c_ulong,
    )
    driver.bind(driver.x, "XDestroyWindow", integer, pointer, window)

    created = driver.x.XCreateSimpleWindow(
        driver.display,
        driver.root,
        0,
        0,
        16,
        16,
        0,
        0,
        0,
    )
    if not created:
        raise AssertionError("X11 stale-window fixture creation failed")
    driver.x.XSync(driver.display, 0)
    if created not in driver.windows():
        raise AssertionError("fixture window was not present in the XQueryTree snapshot")

    driver.x.XDestroyWindow(driver.display, created)
    driver.x.XSync(driver.display, 0)

    sentinel_errors: list[tuple[int, int, int, int]] = []

    def capture_sentinel(_display, event):
        value = event.contents
        sentinel_errors.append((
            int(value.error_code),
            int(value.resourceid),
            int(value.request_code),
            int(value.minor_code),
        ))
        return 0

    sentinel = XErrorHandler(capture_sentinel)
    sentinel_pointer = C.cast(sentinel, C.c_void_p)
    previous = driver.x.XSetErrorHandler(sentinel_pointer)
    try:
        attributes = Attributes()
        stale = driver._volatile_window_query(
            created,
            lambda: driver.x.XGetWindowAttributes(
                driver.display, created, C.byref(attributes)
            ),
        )
        if stale is not None:
            raise AssertionError("exact stale XID was not consumed as a vanished snapshot entry")
        if sentinel_errors:
            raise AssertionError(f"scoped probe error escaped to prior handler: {sentinel_errors}")

        # The previous process-global handler must have been restored after the
        # scoped query. Delivering the same real BadWindow outside that scope must
        # therefore reach the sentinel rather than the probe callback.
        driver.x.XGetWindowAttributes(driver.display, created, C.byref(attributes))
        driver.x.XSync(driver.display, 0)
        if len(sentinel_errors) != 1 or sentinel_errors[0][1] != created:
            raise AssertionError(f"prior X11 error handler was not restored: {sentinel_errors}")
        sentinel_errors.clear()

        # A BadWindow for an XID other than the one declared as the volatile probe
        # target must remain a hard failure, even though the same scoped handler
        # and XSync path observe it.
        try:
            driver._volatile_window_query(
                driver.root,
                lambda: driver.x.XGetWindowAttributes(
                    driver.display, created, C.byref(attributes)
                ),
            )
        except RuntimeError as exc:
            if "unexpected X11 error while probing window" not in str(exc):
                raise
        else:
            raise AssertionError("mismatched-XID BadWindow was incorrectly suppressed")

        current = driver.x.XSetErrorHandler(sentinel_pointer)
        if current != sentinel_pointer.value:
            raise AssertionError("prior X11 handler was not restored after fail-closed probe")
    finally:
        driver.x.XSetErrorHandler(previous)

    print(
        "PASS: real X11 stale-window probe consumes only the exact vanished XID, "
        "fails closed on a mismatched XID, and restores the prior handler."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
