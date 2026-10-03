#!/usr/bin/env python3
"""One-shot Crazyflie link teardown without Commander traffic.

Pinned cflib's Crazyflie.close_link() emits a zero Commander setpoint before
closing the transport. X3 props-off preparation and acquisition explicitly
forbid Commander effects, so these one-shot helpers close the underlying link
and stop the incoming thread directly instead of calling close_link().
"""

from __future__ import annotations


class X3LinkCloseError(RuntimeError):
    pass


def close_link_without_commander(cf: object) -> None:
    """Close one X3 Crazyflie connection without calling Commander APIs.

    The Crazyflie object is intentionally one-shot after this function. The
    sequence mirrors the non-Commander portions of pinned cflib close_link():
    close the transport, stop the incoming handler, drop pending answer state,
    publish the disconnected callback, and mark the object disconnected.
    """

    link_uri = getattr(cf, "link_uri", "")
    link = getattr(cf, "link", None)
    if link is not None:
        link.close()
        cf.link = None

    incoming = getattr(cf, "incoming", None)
    if incoming is not None and incoming.is_alive():
        incoming.stop()
        incoming.join(timeout=1.0)
        if incoming.is_alive():
            raise X3LinkCloseError("Crazyflie incoming handler did not stop")

    answer_patterns = getattr(cf, "_answer_patterns", None)
    if isinstance(answer_patterns, dict):
        for timer in tuple(answer_patterns.values()):
            cancel = getattr(timer, "cancel", None)
            if callable(cancel):
                cancel()
        cf._answer_patterns = {}

    disconnected = getattr(cf, "disconnected", None)
    if disconnected is not None:
        disconnected.call(link_uri)

    # State.DISCONNECTED == 0 in the exact pinned cflib source. Avoid importing
    # cflib here so this teardown primitive remains independently self-testable.
    cf.state = 0


def self_test() -> None:
    events: list[str] = []

    class Link:
        def close(self) -> None:
            events.append("link-close")

    class Incoming:
        def __init__(self) -> None:
            self.alive = True

        def is_alive(self) -> bool:
            return self.alive

        def stop(self) -> None:
            events.append("incoming-stop")
            self.alive = False

        def join(self, timeout: float) -> None:
            if timeout != 1.0:
                raise AssertionError("unexpected join timeout")
            events.append("incoming-join")

    class Disconnected:
        def call(self, uri: str) -> None:
            events.append("disconnected:" + uri)

    class Commander:
        def send_setpoint(self, *_args: object) -> None:
            raise AssertionError("Commander emission attempted during X3 teardown")

    class Timer:
        def cancel(self) -> None:
            events.append("timer-cancel")

    class FakeCf:
        def __init__(self) -> None:
            self.link_uri = "radio://0/80/2M"
            self.link = Link()
            self.incoming = Incoming()
            self.disconnected = Disconnected()
            self.commander = Commander()
            self._answer_patterns = {"pending": Timer()}
            self.state = 3

    cf = FakeCf()
    close_link_without_commander(cf)
    if cf.link is not None or cf.state != 0:
        raise AssertionError("X3 no-Commander teardown did not close the link")
    if cf._answer_patterns:
        raise AssertionError("X3 no-Commander teardown retained answer state")
    if events != [
        "link-close",
        "incoming-stop",
        "incoming-join",
        "timer-cancel",
        "disconnected:radio://0/80/2M",
    ]:
        raise AssertionError(f"unexpected X3 teardown trace: {events!r}")
    print("PASS: X3 one-shot link teardown emits no Commander/setpoint call")


if __name__ == "__main__":
    self_test()
