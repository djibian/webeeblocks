#!/usr/bin/env python3
"""Fail-closed post-reset rebinding for the trusted read-only capability bridge.

#266 replaces the live Crazyflie connection and therefore its opaque connection
epoch, while the production browser responder already holds the one-time loopback
bridge URL and bearer tokens. Recreating an unrelated HTTP bridge would strand
that trusted responder. This module preserves the existing bridge identity and
makes the session handoff explicit: once replacement begins, capability reads and
#249 assertions fail closed until a genuinely new live epoch is installed.

This is non-authority plumbing. It emits no CRTP command, exposes no raw
Crazyflie object and cannot mint execution authority.
"""

from __future__ import annotations

from threading import RLock

from serve_reference_capabilities import (
    CapabilityBridgeError,
    ReadOnlyCapabilityHttpBridge,
    _require_text,
)


class PostResetCapabilityHttpBridge(ReadOnlyCapabilityHttpBridge):
    """One loopback bridge whose read-only session may rotate exactly at #266."""

    def __init__(self, session: object, **kwargs) -> None:
        self._session_lock = RLock()
        self._session = session
        self._replacement_previous_epoch: str | None = None
        super().__init__(session, **kwargs)

    @property
    def session(self) -> object:
        with self._session_lock:
            if self._replacement_previous_epoch is not None:
                raise CapabilityBridgeError(
                    "capability bridge session is unavailable during post-reset replacement"
                )
            return self._session

    @session.setter
    def session(self, value: object) -> None:
        # Base construction assigns ``session`` once. Later rotation is permitted
        # only through the explicit two-phase methods below.
        with self._session_lock:
            self._session = value

    @property
    def post_reset_replacement_pending(self) -> bool:
        with self._session_lock:
            return self._replacement_previous_epoch is not None

    def begin_post_reset_replacement(self, expected_connection_epoch: str) -> None:
        """Invalidate the current bridge view immediately before #266 reset.

        This method is intended to be the #266 ``invalidate_prior_evidence``
        collaborator. Once it succeeds there is deliberately no rollback to the
        old session: an ambiguous reset must not make stale pre-reset evidence
        reusable.
        """
        expected = _require_text(expected_connection_epoch, "connectionEpoch")
        with self._preflight_condition:
            if self._preflight_closed:
                raise CapabilityBridgeError("capability bridge is shut down")
            if self._preflight_pending is not None:
                raise CapabilityBridgeError(
                    "cannot replace capability session during current-program assertion"
                )
            with self._session_lock:
                if self._replacement_previous_epoch is not None:
                    raise CapabilityBridgeError(
                        "post-reset capability session replacement is already pending"
                    )
                current = self._session
                try:
                    observed = current.read_connection_epoch()
                except Exception as exc:
                    raise CapabilityBridgeError(
                        "current capability session epoch is unavailable before replacement"
                    ) from exc
                if observed != expected:
                    raise CapabilityBridgeError(
                        "current capability session does not match replacement epoch"
                    )
                self._replacement_previous_epoch = expected
            self._preflight_condition.notify_all()

    def install_post_reset_session(self, session: object) -> str:
        """Install a live read-only view only when its epoch is genuinely new."""
        if session is None:
            raise CapabilityBridgeError("post-reset capability session is required")
        try:
            new_epoch = _require_text(
                session.read_connection_epoch(),
                "post-reset connectionEpoch",
            )
        except CapabilityBridgeError:
            raise
        except Exception as exc:
            raise CapabilityBridgeError(
                "post-reset capability session epoch is unavailable"
            ) from exc

        with self._preflight_condition:
            if self._preflight_closed:
                raise CapabilityBridgeError("capability bridge is shut down")
            if self._preflight_pending is not None:
                raise CapabilityBridgeError(
                    "cannot install capability session during current-program assertion"
                )
            with self._session_lock:
                previous = self._replacement_previous_epoch
                if previous is None:
                    raise CapabilityBridgeError(
                        "post-reset capability session replacement was not started"
                    )
                if new_epoch == previous:
                    raise CapabilityBridgeError(
                        "post-reset capability session reused the previous connection epoch"
                    )
                self._session = session
                self._replacement_previous_epoch = None
            self._preflight_condition.notify_all()
        return new_epoch
