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

from probe_reference_hardware import ProbeError
from serve_reference_capabilities import (
    CapabilityBridgeError,
    ReadOnlyCapabilityHttpBridge,
    _require_text,
)


class _LockedSessionView:
    """Read-only session facade whose calls stay inside the reset cutover lock."""

    def __init__(self, bridge: "PostResetCapabilityHttpBridge") -> None:
        self._bridge = bridge

    def read_connection_epoch(self):
        return self._bridge._read_current_session("read_connection_epoch")

    def read_capabilities(self):
        return self._bridge._read_current_session("read_capabilities")


class PostResetCapabilityHttpBridge(ReadOnlyCapabilityHttpBridge):
    """One loopback bridge whose read-only session may rotate exactly at #266."""

    def __init__(self, session: object, **kwargs) -> None:
        self._session_lock = RLock()
        self._session: object | None = None
        self._session_view = _LockedSessionView(self)
        self._base_session_assignment_open = True
        self._replacement_previous_epoch: str | None = None
        try:
            super().__init__(session, **kwargs)
        finally:
            self._base_session_assignment_open = False

    def _current_session_locked(self) -> object:
        if self._replacement_previous_epoch is not None:
            raise CapabilityBridgeError(
                "capability bridge session is unavailable during post-reset replacement"
            )
        if self._session is None:
            raise CapabilityBridgeError("capability bridge session is unavailable")
        return self._session

    def _read_current_session(self, method_name: str):
        """Keep direct bridge reads linearized against replacement begin/install."""
        with self._session_lock:
            session = self._current_session_locked()
            method = getattr(session, method_name, None)
            if not callable(method):
                raise CapabilityBridgeError(
                    "capability bridge session does not expose " + method_name
                )
            return method()

    @property
    def session(self) -> object:
        # The base bridge calls ``self.session.read_*``. Return a facade rather
        # than the raw session so the actual read stays inside ``_session_lock``.
        return self._session_view

    @session.setter
    def session(self, value: object) -> None:
        # ReadOnlyCapabilityHttpBridge assigns ``session`` once from its own
        # constructor. No later property assignment is allowed: all post-reset
        # rotation must pass through the explicit two-phase protocol below.
        with self._session_lock:
            if not self._base_session_assignment_open:
                raise CapabilityBridgeError(
                    "capability bridge session replacement requires the explicit post-reset protocol"
                )
            self._session = value
            self._base_session_assignment_open = False

    def _handler_type(self):
        """Linearize successful HTTP capability replies with the reset cutover.

        The base handler obtains ``bridge.session`` and only then invokes the
        session method. A property-level lock therefore ends too early: reset can
        begin while the old read is still running. For the two ordinary read-only
        endpoints, keep ``_session_lock`` through both the physical read and the
        response write. Consequently ``begin_post_reset_replacement()`` cannot
        return while an admitted old-session HTTP view can still be published,
        and any request admitted after that edge sees replacement-pending and
        fails closed. The trusted preflight-responder endpoint remains delegated
        to the base implementation and is fenced separately by
        ``_preflight_condition`` below.
        """
        base_handler = super()._handler_type()
        bridge = self

        class Handler(base_handler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path not in {"/v1/connection-epoch", "/v1/capabilities"}:
                    super().do_GET()
                    return
                if not self._capability_authorized():
                    self._json(401, {"error": "unauthorized"})
                    return
                try:
                    with bridge._session_lock:
                        session = bridge._current_session_locked()
                        if self.path == "/v1/connection-epoch":
                            payload = {
                                "connectionEpoch": session.read_connection_epoch()
                            }
                        else:
                            payload = session.read_capabilities()
                        self._json(200, payload)
                except (ProbeError, CapabilityBridgeError) as exc:
                    self._json(409, {"error": str(exc)})

        return Handler

    @property
    def post_reset_replacement_pending(self) -> bool:
        with self._session_lock:
            return self._replacement_previous_epoch is not None

    def assert_current_program(
        self,
        *,
        profile_id: str,
        ast_binding: str,
        connection_epoch: str,
        timeout_seconds: float = 1.0,
    ):
        """Serialize #249 assertion admission against the #266 replacement edge.

        The base bridge reads the epoch immediately before registering its pending
        challenge. Without this outer condition there is a narrow race where a
        reset replacement can begin after that first read but before the pending
        challenge becomes visible. Holding the same re-entrant condition across
        admission closes that gap. During the base wait the condition is released,
        but the pending challenge is already installed, so replacement still
        rejects rather than crossing an in-flight assertion.
        """
        with self._preflight_condition:
            with self._session_lock:
                if self._replacement_previous_epoch is not None:
                    raise CapabilityBridgeError(
                        "capability bridge session is unavailable during post-reset replacement"
                    )
            return super().assert_current_program(
                profile_id=profile_id,
                ast_binding=ast_binding,
                connection_epoch=connection_epoch,
                timeout_seconds=timeout_seconds,
            )

    def begin_post_reset_replacement(self, expected_connection_epoch: str) -> None:
        """Invalidate the current bridge view immediately before #266 reset.

        This method is intended to be the #266 ``invalidate_prior_evidence``
        collaborator. Once it succeeds there is deliberately no rollback to the
        old session: an ambiguous reset must not make stale pre-reset evidence
        reusable. Acquiring ``_session_lock`` after the assertion fence also
        drains any already-admitted ordinary capability response before this
        cutover returns.
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
                if current is None:
                    raise CapabilityBridgeError(
                        "current capability session is unavailable before replacement"
                    )
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
