#!/usr/bin/env python3
"""One-way current-program provenance channel for the trusted physical host.

This module is deliberately not an effect-side authority factory.  It defines
only the small request/response protocol and the authority-side broker used by
the trusted top-level physical-host composition selected in #280.

Production composition creates two unidirectional OS pipe capabilities before
the effect worker starts:

    effect worker: request-send + response-receive
    authority host: request-receive + response-send

Only the authority host owns the integrated #278 ReadOnlyCapabilityHttpBridge,
its live ReadOnlyCapabilitySession, pending host-created challenge and browser
responder credential.  The effect worker may import/construct arbitrary local
bridge/session objects, but none of those objects has a route to the trusted
response-receive capability already inherited from production composition.

Responses remain non-authority evidence.  They do not grant teacher approval,
watchdog/powered-session authority or a physical command.  A later #276 worker
must consume this channel inside the same trusted process composition and still
apply every independent effect/safety gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from multiprocessing.connection import Connection
from threading import Lock

import serve_reference_capabilities as capability_bridge

PROTOCOL_VERSION = 1
MAX_TEXT_LENGTH = 4096


class CurrentProgramAuthorityChannelError(RuntimeError):
    """Fail-closed current-program authority-channel error."""


def _text(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > MAX_TEXT_LENGTH
    ):
        raise CurrentProgramAuthorityChannelError(
            f"{name} must be a non-empty trimmed bounded string"
        )
    return value


def _timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CurrentProgramAuthorityChannelError("channel timeout must be positive")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0.0:
        raise CurrentProgramAuthorityChannelError("channel timeout must be positive")
    return parsed


@dataclass(frozen=True)
class CurrentProgramAuthorityEvidence:
    """Validated non-authority response read from the trusted response pipe."""

    profile_id: str
    ast_binding: str
    connection_epoch: str
    challenge_id: str
    request_id: str
    execution_authority: bool = False


def request_payload(
    *,
    request_id: str,
    profile_id: str,
    ast_binding: str,
    connection_epoch: str,
) -> dict[str, object]:
    """Build the exact request shape sent over the request-only capability."""
    return {
        "version": PROTOCOL_VERSION,
        "requestId": _text(request_id, "requestId"),
        "profileId": _text(profile_id, "profileId"),
        "astBinding": _text(ast_binding, "astBinding"),
        "connectionEpoch": _text(connection_epoch, "connectionEpoch"),
    }


def _parse_request(payload: object) -> tuple[str, str, str, str]:
    if not isinstance(payload, dict):
        raise CurrentProgramAuthorityChannelError(
            "current-program authority request must be a mapping"
        )
    expected = {
        "version",
        "requestId",
        "profileId",
        "astBinding",
        "connectionEpoch",
    }
    if set(payload) != expected or payload.get("version") != PROTOCOL_VERSION:
        raise CurrentProgramAuthorityChannelError(
            "current-program authority request shape is invalid"
        )
    return (
        _text(payload.get("requestId"), "requestId"),
        _text(payload.get("profileId"), "profileId"),
        _text(payload.get("astBinding"), "astBinding"),
        _text(payload.get("connectionEpoch"), "connectionEpoch"),
    )


def _success_payload(
    request_id: str,
    evidence: capability_bridge.CurrentProgramPreflightEvidence,
) -> dict[str, object]:
    if type(evidence) is not capability_bridge.CurrentProgramPreflightEvidence:
        raise CurrentProgramAuthorityChannelError(
            "authority broker requires exact integrated #278 evidence"
        )
    if evidence.execution_authority is not False:
        raise CurrentProgramAuthorityChannelError(
            "current-program evidence unexpectedly carries execution authority"
        )
    return {
        "version": PROTOCOL_VERSION,
        "requestId": request_id,
        "ok": True,
        "executionAuthority": False,
        "profileId": evidence.profile_id,
        "astBinding": evidence.ast_binding,
        "connectionEpoch": evidence.connection_epoch,
        "challengeId": evidence.challenge_id,
    }


def _failure_payload(request_id: str | None) -> dict[str, object]:
    return {
        "version": PROTOCOL_VERSION,
        "requestId": request_id,
        "ok": False,
        "executionAuthority": False,
        "error": "current-program assertion unavailable",
    }


def validate_response(
    payload: object,
    *,
    expected_request_id: str,
    expected_profile_id: str,
    expected_ast_binding: str,
    expected_connection_epoch: str,
) -> CurrentProgramAuthorityEvidence:
    """Validate one payload already read from the trusted response capability.

    This function validates correlation/binding only.  Constructing an identical
    Python mapping is not provenance: production #276 must obtain the payload by
    reading the response-receive endpoint inherited from trusted composition.
    """
    request_id = _text(expected_request_id, "expected requestId")
    profile_id = _text(expected_profile_id, "expected profileId")
    ast_binding = _text(expected_ast_binding, "expected astBinding")
    connection_epoch = _text(
        expected_connection_epoch,
        "expected connectionEpoch",
    )
    if not isinstance(payload, dict):
        raise CurrentProgramAuthorityChannelError(
            "current-program authority response must be a mapping"
        )
    if payload.get("version") != PROTOCOL_VERSION:
        raise CurrentProgramAuthorityChannelError(
            "current-program authority response version mismatch"
        )
    if payload.get("requestId") != request_id:
        raise CurrentProgramAuthorityChannelError(
            "current-program authority response correlation mismatch"
        )
    if payload.get("executionAuthority") is not False:
        raise CurrentProgramAuthorityChannelError(
            "current-program authority response crossed authority boundary"
        )
    if payload.get("ok") is not True:
        raise CurrentProgramAuthorityChannelError(
            "current-program authority did not establish fresh evidence"
        )
    expected_keys = {
        "version",
        "requestId",
        "ok",
        "executionAuthority",
        "profileId",
        "astBinding",
        "connectionEpoch",
        "challengeId",
    }
    if set(payload) != expected_keys:
        raise CurrentProgramAuthorityChannelError(
            "current-program authority success response shape is invalid"
        )
    if (
        payload.get("profileId") != profile_id
        or payload.get("astBinding") != ast_binding
        or payload.get("connectionEpoch") != connection_epoch
    ):
        raise CurrentProgramAuthorityChannelError(
            "current-program authority response binding mismatch"
        )
    challenge_id = _text(payload.get("challengeId"), "challengeId")
    return CurrentProgramAuthorityEvidence(
        profile_id=profile_id,
        ast_binding=ast_binding,
        connection_epoch=connection_epoch,
        challenge_id=challenge_id,
        request_id=request_id,
    )


class CurrentProgramAuthorityBroker:
    """Authority-side owner of the #278 bridge and one-way pipe endpoints.

    This object is never an effect-eligible requester.  It can only receive
    requests and write responses on endpoints retained by trusted production
    composition.
    """

    def __init__(
        self,
        bridge: capability_bridge.ReadOnlyCapabilityHttpBridge,
        request_receiver: Connection,
        response_sender: Connection,
    ) -> None:
        if type(bridge) is not capability_bridge.ReadOnlyCapabilityHttpBridge:
            raise CurrentProgramAuthorityChannelError(
                "authority broker requires exact integrated #278 bridge"
            )
        if not isinstance(request_receiver, Connection):
            raise CurrentProgramAuthorityChannelError(
                "authority request-receive capability is required"
            )
        if not isinstance(response_sender, Connection):
            raise CurrentProgramAuthorityChannelError(
                "authority response-send capability is required"
            )
        self._bridge = bridge
        self._requests = request_receiver
        self._responses = response_sender
        self._lock = Lock()

    def serve_one(self, *, timeout_seconds: float = 1.0) -> None:
        """Serve exactly one request; any ambiguity returns fail-closed evidence."""
        timeout = _timeout(timeout_seconds)
        with self._lock:
            try:
                if not self._requests.poll(timeout):
                    raise CurrentProgramAuthorityChannelError(
                        "current-program authority request timed out"
                    )
                raw = self._requests.recv()
            except (EOFError, OSError) as exc:
                raise CurrentProgramAuthorityChannelError(
                    "current-program authority request channel is unavailable"
                ) from exc

            request_id: str | None = None
            try:
                request_id, profile_id, ast_binding, connection_epoch = _parse_request(
                    raw
                )
                evidence = self._bridge.assert_current_program(
                    profile_id=profile_id,
                    ast_binding=ast_binding,
                    connection_epoch=connection_epoch,
                    timeout_seconds=timeout,
                )
                response = _success_payload(request_id, evidence)
            except Exception:
                if isinstance(raw, dict) and isinstance(raw.get("requestId"), str):
                    request_id = raw.get("requestId")
                response = _failure_payload(request_id)

            try:
                self._responses.send(response)
            except (BrokenPipeError, EOFError, OSError) as exc:
                raise CurrentProgramAuthorityChannelError(
                    "current-program authority response channel is unavailable"
                ) from exc


def assert_no_effect_surface() -> None:
    """Static self-check: this prerequisite owns no physical command operation."""
    forbidden = (
        "send_packet",
        "HighLevelCommander",
        "send_arming_request",
        "send_emergency_stop",
        "takeoff",
        "land",
        "setpoint",
    )
    source = __loader__.get_source(__name__) if __loader__ is not None else ""
    if any(token in source for token in forbidden):
        raise CurrentProgramAuthorityChannelError(
            "current-program authority channel contains physical effect surface"
        )
