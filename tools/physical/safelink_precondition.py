#!/usr/bin/env python3
"""Live SafeLink eligibility precondition for future Crazyflie physical effects.

Pinned cflib exposes radio-level duplicate-suppression certainty through the exact
live Crazyflie link: RadioDriver starts with ``needs_resending = True`` and flips
it to ``False`` only when the radio thread has positively established SafeLink.

This module emits no CRTP packet and grants no command authority. It provides a
small same-connection-epoch observation that a later trusted SETPOINT_HL effect
consumer must call immediately before entering its acknowledged effect
transaction. A successful observation proves only that the exact live radio link
currently reports the duplicate-suppression precondition; it does not prove
teacher authorization, watchdog liveness, command acknowledgement/completion or
the outcome of any earlier ambiguous physical effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class SafeLinkPreconditionError(RuntimeError):
    """Fail-closed error for unavailable live SafeLink evidence."""


def _read_epoch(reader: Callable[[], str]) -> str:
    try:
        value = reader()
    except Exception as exc:
        raise SafeLinkPreconditionError(
            "connection epoch is unavailable for SafeLink precondition"
        ) from exc
    if not isinstance(value, str) or not value.strip():
        raise SafeLinkPreconditionError(
            "connection epoch is invalid for SafeLink precondition"
        )
    return value.strip()


@dataclass(frozen=True)
class SafeLinkEvidence:
    """One non-authority observation of live radio duplicate suppression."""

    connection_epoch: str
    link_uri: str


class LiveSafeLinkPrecondition:
    """Observe SafeLink on one exact Crazyflie and connection epoch."""

    def __init__(
        self,
        crazyflie: object,
        connection_epoch_reader: Callable[[], str],
    ) -> None:
        if crazyflie is None:
            raise SafeLinkPreconditionError(
                "exact live Crazyflie object is required for SafeLink precondition"
            )
        if not callable(connection_epoch_reader):
            raise SafeLinkPreconditionError(
                "connection epoch reader is required for SafeLink precondition"
            )
        self._cf = crazyflie
        self._connection_epoch_reader = connection_epoch_reader
        self._bound_connection_epoch = _read_epoch(connection_epoch_reader)

    @property
    def bound_crazyflie(self) -> object:
        return self._cf

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    def _verify_epoch(self) -> None:
        current = _read_epoch(self._connection_epoch_reader)
        if current != self._bound_connection_epoch:
            raise SafeLinkPreconditionError(
                "connection epoch changed during SafeLink precondition"
            )

    def _require_connected(self) -> None:
        method = getattr(self._cf, "is_connected", None)
        if not callable(method):
            raise SafeLinkPreconditionError(
                "Crazyflie live connection state is unavailable for SafeLink precondition"
            )
        try:
            connected = method()
        except Exception as exc:
            raise SafeLinkPreconditionError(
                "Crazyflie live connection state is unavailable for SafeLink precondition"
            ) from exc
        if connected is not True:
            raise SafeLinkPreconditionError(
                "Crazyflie is not positively connected for SafeLink precondition"
            )

    def assert_ready(self) -> SafeLinkEvidence:
        """Require exact live radio SafeLink evidence without emitting an effect."""
        self._verify_epoch()
        self._require_connected()

        link_uri = getattr(self._cf, "link_uri", None)
        if (
            not isinstance(link_uri, str)
            or not link_uri.strip()
            or link_uri != link_uri.strip()
            or not link_uri.startswith("radio://")
        ):
            raise SafeLinkPreconditionError(
                "SafeLink physical effect precondition requires an explicit radio:// link"
            )

        link = getattr(self._cf, "link", None)
        if link is None:
            raise SafeLinkPreconditionError(
                "live Crazyflie radio link is unavailable for SafeLink precondition"
            )

        try:
            needs_resending = getattr(link, "needs_resending")
        except Exception as exc:
            raise SafeLinkPreconditionError(
                "live radio SafeLink state is unavailable"
            ) from exc
        if needs_resending is not False:
            raise SafeLinkPreconditionError(
                "live radio SafeLink duplicate suppression is not positively established"
            )

        if getattr(self._cf, "link", None) is not link:
            raise SafeLinkPreconditionError(
                "Crazyflie live radio link changed during SafeLink precondition"
            )
        try:
            if getattr(link, "needs_resending") is not False:
                raise SafeLinkPreconditionError(
                    "live radio SafeLink duplicate suppression changed during observation"
                )
        except SafeLinkPreconditionError:
            raise
        except Exception as exc:
            raise SafeLinkPreconditionError(
                "live radio SafeLink state became unavailable"
            ) from exc
        self._require_connected()
        self._verify_epoch()

        return SafeLinkEvidence(
            connection_epoch=self._bound_connection_epoch,
            link_uri=link_uri,
        )
