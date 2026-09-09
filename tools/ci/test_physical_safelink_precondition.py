#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "safelink_precondition.py"
sys.path.insert(0, str(MODULE_PATH.parent))
import safelink_precondition as safelink  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except safelink.SafeLinkPreconditionError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(
        f"expected SafeLinkPreconditionError containing {pattern!r}"
    )


class Epoch:
    def __init__(self, values) -> None:
        if isinstance(values, str):
            values = [values]
        self.values = list(values)
        self.index = 0

    def __call__(self) -> str:
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value


class Link:
    def __init__(self, needs_resending) -> None:
        self.needs_resending = needs_resending


class Crazyflie:
    def __init__(
        self,
        *,
        link=None,
        link_uri: str = "radio://0/80/2M/E7E7E7E7E7",
        connected=True,
    ) -> None:
        self.link = link if link is not None else Link(False)
        self.link_uri = link_uri
        self.connected = connected

    def is_connected(self):
        return self.connected


def test_exact_live_radio_safelink_passes() -> None:
    cf = Crazyflie(link=Link(False))
    epoch = Epoch("epoch-ok")
    guard = safelink.LiveSafeLinkPrecondition(cf, epoch)
    evidence = guard.assert_ready()
    require(guard.bound_crazyflie is cf, "guard must retain exact Crazyflie identity")
    require(
        guard.bound_connection_epoch == "epoch-ok",
        "guard must bind exact connection epoch",
    )
    require(
        evidence
        == safelink.SafeLinkEvidence(
            connection_epoch="epoch-ok",
            link_uri="radio://0/80/2M/E7E7E7E7E7",
        ),
        "evidence is exact same-epoch radio SafeLink observation",
    )


def test_resending_or_unknown_safelink_fails_closed() -> None:
    for value in (True, None, 0, "", object()):
        cf = Crazyflie(link=Link(value))
        guard = safelink.LiveSafeLinkPrecondition(
            cf,
            Epoch("epoch-unsafe-" + type(value).__name__),
        )
        expect_error(guard.assert_ready, "not positively established")

    class MissingState:
        pass

    guard = safelink.LiveSafeLinkPrecondition(
        Crazyflie(link=MissingState()),
        Epoch("epoch-missing"),
    )
    expect_error(guard.assert_ready, "SafeLink state is unavailable")


def test_connection_and_radio_identity_are_required() -> None:
    disconnected = safelink.LiveSafeLinkPrecondition(
        Crazyflie(connected=False),
        Epoch("epoch-disconnected"),
    )
    expect_error(disconnected.assert_ready, "not positively connected")

    for uri in ("", "usb://0", "radio://0/80/2M/E7E7E7E7E7 ", None):
        guard = safelink.LiveSafeLinkPrecondition(
            Crazyflie(link_uri=uri),
            Epoch("epoch-uri-" + repr(uri)),
        )
        expect_error(guard.assert_ready, "explicit radio:// link")

    missing_link = safelink.LiveSafeLinkPrecondition(
        Crazyflie(link=Link(False)),
        Epoch("epoch-link"),
    )
    missing_link.bound_crazyflie.link = None
    expect_error(missing_link.assert_ready, "radio link is unavailable")


def test_epoch_rotation_fails_closed() -> None:
    cf = Crazyflie()
    guard = safelink.LiveSafeLinkPrecondition(
        cf,
        Epoch(["epoch-a", "epoch-a", "epoch-b"]),
    )
    expect_error(guard.assert_ready, "connection epoch changed")


def test_link_replacement_during_observation_fails_closed() -> None:
    first = Link(False)
    second = Link(False)

    class ReplacingCrazyflie:
        link_uri = "radio://0/80/2M/E7E7E7E7E7"

        def __init__(self) -> None:
            self.reads = 0

        @property
        def link(self):
            self.reads += 1
            return first if self.reads == 1 else second

        def is_connected(self):
            return True

    cf = ReplacingCrazyflie()
    guard = safelink.LiveSafeLinkPrecondition(cf, Epoch("epoch-replace"))
    expect_error(guard.assert_ready, "radio link changed")


def test_no_physical_effect_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "import cflib",
        "CRTPPacket",
        "HighLevelCommander(",
        ".send_packet(",
        "add_port_callback(",
        "expected_" + "reply",
        "send_arming_request",
        "send_emergency_stop",
    ):
        require(
            forbidden not in source,
            "SafeLink precondition contains physical effect surface: " + forbidden,
        )


def main() -> int:
    test_exact_live_radio_safelink_passes()
    test_resending_or_unknown_safelink_fails_closed()
    test_connection_and_radio_identity_are_required()
    test_epoch_rotation_fails_closed()
    test_link_replacement_during_observation_fails_closed()
    test_no_physical_effect_surface()
    print(
        "PASS live radio SafeLink duplicate suppression is required on one exact "
        "Crazyflie/connection epoch without physical effect authority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
