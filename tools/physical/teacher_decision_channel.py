#!/usr/bin/env python3
"""One-shot trusted teacher decision channel for physical-run authorization.

The channel is installed by the trusted launcher as a distinct connected socket.
It is not reachable through the ordinary caller or browser-responder paths.  A
teacher-side request names one exact profile/AST/connection-epoch binding; the
host then creates a fresh correlation challenge and accepts exactly one matching
positive/negative decision.  Any malformed, mismatched, duplicated, late or
transport-ambiguous exchange makes the channel terminal.

A positive decision is converted into the existing #267
``TeacherRunAuthorization`` by a process-local ``TrustedTeacherAuthorizer``.
This module exposes no physical-effect operation and serializes no authorization
receipt.
"""

from __future__ import annotations

import json
import math
import secrets
import socket
from threading import Lock
from typing import Callable

from teacher_run_authorization import (
    PhysicalRunBinding,
    TeacherRunAuthorization,
    TeacherRunAuthorizationError,
    TrustedTeacherAuthorizer,
)

_MAX_MESSAGE_BYTES = 8192
_DEFAULT_DECISION_TIMEOUT_SECONDS = 5.0


class TeacherDecisionChannelError(RuntimeError):
    """Fail-closed teacher-decision transport or correlation error."""


def _require_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TeacherDecisionChannelError("teacher decision timeout must be positive")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise TeacherDecisionChannelError("teacher decision timeout must be positive")
    return timeout


def _read_epoch(reader: Callable[[], str]) -> str:
    try:
        epoch = reader()
    except Exception as exc:
        raise TeacherDecisionChannelError(
            "connection epoch is unavailable for teacher decision"
        ) from exc
    if not isinstance(epoch, str) or not epoch.strip() or epoch != epoch.strip():
        raise TeacherDecisionChannelError(
            "connection epoch is invalid for teacher decision"
        )
    return epoch


def _nonempty_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise TeacherDecisionChannelError(f"{name} must be non-empty trimmed text")
    return value


class TrustedTeacherDecisionChannel:
    """One launcher-installed duplex socket consumed by one teacher decision."""

    def __init__(
        self,
        channel_socket: socket.socket,
        connection_epoch_reader: Callable[[], str],
        *,
        challenge_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if type(channel_socket) is not socket.socket:
            raise TeacherDecisionChannelError(
                "trusted teacher decision requires an exact socket capability"
            )
        if not callable(connection_epoch_reader):
            raise TeacherDecisionChannelError(
                "connection epoch reader is required for teacher decision"
            )
        self._socket = channel_socket
        self._epoch_reader = connection_epoch_reader
        self._challenge_id_factory = challenge_id_factory or (
            lambda: secrets.token_urlsafe(24)
        )
        if not callable(self._challenge_id_factory):
            raise TeacherDecisionChannelError(
                "teacher decision challenge-id factory must be callable"
            )
        self._lock = Lock()
        self._started = False
        self._terminal = False
        self._terminal_reason: str | None = None

    @property
    def terminal(self) -> bool:
        with self._lock:
            return self._terminal

    @property
    def terminal_reason(self) -> str | None:
        with self._lock:
            return self._terminal_reason

    def _finish(self, reason: object) -> None:
        message = str(reason).strip() or "teacher decision channel is terminal"
        with self._lock:
            self._terminal = True
            self._terminal_reason = message

    def _challenge_id(self) -> str:
        try:
            value = self._challenge_id_factory()
        except Exception as exc:
            raise TeacherDecisionChannelError(
                "teacher decision challenge id is unavailable"
            ) from exc
        return _nonempty_text(value, "teacher decision challenge id")

    def _send_json_line(self, payload: dict[str, object], timeout: float) -> None:
        encoded = (
            json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode("utf-8")
        if len(encoded) > _MAX_MESSAGE_BYTES:
            raise TeacherDecisionChannelError("teacher decision message is too large")
        try:
            self._socket.settimeout(timeout)
            self._socket.sendall(encoded)
        except socket.timeout as exc:
            raise TeacherDecisionChannelError("teacher decision timed out") from exc
        except OSError as exc:
            raise TeacherDecisionChannelError(
                "teacher decision transport failed"
            ) from exc

    def _recv_json_line(self, timeout: float | None) -> dict[str, object]:
        data = bytearray()
        try:
            self._socket.settimeout(timeout)
            while len(data) <= _MAX_MESSAGE_BYTES:
                chunk = self._socket.recv(1)
                if not chunk:
                    raise TeacherDecisionChannelError(
                        "teacher decision channel closed before a complete message"
                    )
                data.extend(chunk)
                if chunk == b"\n":
                    break
            else:
                raise TeacherDecisionChannelError(
                    "teacher decision message exceeds size limit"
                )
        except socket.timeout as exc:
            raise TeacherDecisionChannelError("teacher decision timed out") from exc
        except OSError as exc:
            raise TeacherDecisionChannelError(
                "teacher decision transport failed"
            ) from exc

        if not data.endswith(b"\n"):
            raise TeacherDecisionChannelError(
                "teacher decision message is not line terminated"
            )
        try:
            payload = json.loads(bytes(data[:-1]).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise TeacherDecisionChannelError(
                "teacher decision message is malformed JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise TeacherDecisionChannelError(
                "teacher decision message must be a JSON object"
            )
        return payload

    def _require_peer_write_closed(self, timeout: float) -> None:
        """Require end-of-stream before minting so late/duplicate decisions cannot follow."""
        try:
            self._socket.settimeout(timeout)
            extra = self._socket.recv(1)
        except socket.timeout as exc:
            raise TeacherDecisionChannelError(
                "teacher decision channel did not finish the one-shot exchange"
            ) from exc
        except OSError as exc:
            raise TeacherDecisionChannelError(
                "teacher decision transport failed while sealing the exchange"
            ) from exc
        if extra != b"":
            raise TeacherDecisionChannelError(
                "duplicate or late teacher decision data followed the reply"
            )

    def receive_authorization(
        self,
        authorizer: TrustedTeacherAuthorizer,
        *,
        decision_timeout_seconds: float = _DEFAULT_DECISION_TIMEOUT_SECONDS,
    ) -> TeacherRunAuthorization:
        """Receive one trusted request/decision exchange and mint its exact #267 receipt.

        Waiting for the initial teacher request has no application timeout: the
        launcher-installed channel may remain idle until a teacher chooses to act.
        Once a request is received, the correlated decision must complete within
        ``decision_timeout_seconds``.  Any attempted exchange consumes the channel.
        """
        if type(authorizer) is not TrustedTeacherAuthorizer:
            raise TeacherDecisionChannelError(
                "exact trusted teacher authorizer is required"
            )
        timeout = _require_timeout(decision_timeout_seconds)

        with self._lock:
            if self._terminal:
                raise TeacherDecisionChannelError(
                    "teacher decision channel is terminal: "
                    + (self._terminal_reason or "prior decision consumed")
                )
            if self._started:
                raise TeacherDecisionChannelError(
                    "teacher decision channel already has an active exchange"
                )
            self._started = True

        receipt: TeacherRunAuthorization | None = None
        try:
            request = self._recv_json_line(None)
            if set(request) != {
                "op",
                "requestId",
                "profileId",
                "astBinding",
                "connectionEpoch",
                "executionAuthority",
            }:
                raise TeacherDecisionChannelError(
                    "teacher authorization request has unsupported fields"
                )
            if request.get("op") != "teacher-run-authorization-request":
                raise TeacherDecisionChannelError(
                    "teacher authorization request has the wrong operation"
                )
            if request.get("executionAuthority") is not False:
                raise TeacherDecisionChannelError(
                    "teacher decision transport must remain non-authority data"
                )
            request_id = _nonempty_text(
                request.get("requestId"),
                "teacher authorization request id",
            )
            binding = PhysicalRunBinding(
                profile_id=_nonempty_text(
                    request.get("profileId"),
                    "teacher authorization profile id",
                ),
                ast_binding=_nonempty_text(
                    request.get("astBinding"),
                    "teacher authorization AST binding",
                ),
                connection_epoch=_nonempty_text(
                    request.get("connectionEpoch"),
                    "teacher authorization connection epoch",
                ),
            )

            before_epoch = _read_epoch(self._epoch_reader)
            if binding.connection_epoch != before_epoch:
                raise TeacherDecisionChannelError(
                    "teacher authorization request does not match the live connection epoch"
                )

            challenge_id = self._challenge_id()
            challenge = {
                "op": "teacher-run-decision-challenge",
                "requestId": request_id,
                "challengeId": challenge_id,
                "profileId": binding.profile_id,
                "astBinding": binding.ast_binding,
                "connectionEpoch": binding.connection_epoch,
                "executionAuthority": False,
            }
            self._send_json_line(challenge, timeout)
            response = self._recv_json_line(timeout)

            if set(response) != {
                "op",
                "requestId",
                "challengeId",
                "profileId",
                "astBinding",
                "connectionEpoch",
                "approved",
                "executionAuthority",
            }:
                raise TeacherDecisionChannelError(
                    "teacher decision reply has unsupported fields"
                )
            if response.get("op") != "teacher-run-decision-result":
                raise TeacherDecisionChannelError(
                    "teacher decision reply has the wrong operation"
                )
            if response.get("requestId") != request_id:
                raise TeacherDecisionChannelError(
                    "teacher decision reply has the wrong request correlation"
                )
            if response.get("challengeId") != challenge_id:
                raise TeacherDecisionChannelError(
                    "teacher decision reply has the wrong challenge correlation"
                )
            if response.get("executionAuthority") is not False:
                raise TeacherDecisionChannelError(
                    "teacher decision transport must remain non-authority data"
                )
            if (
                response.get("profileId") != binding.profile_id
                or response.get("astBinding") != binding.ast_binding
                or response.get("connectionEpoch") != binding.connection_epoch
            ):
                raise TeacherDecisionChannelError(
                    "teacher decision reply does not match the exact run binding"
                )
            approved = response.get("approved")
            if not isinstance(approved, bool):
                raise TeacherDecisionChannelError(
                    "teacher decision reply must contain a boolean approved value"
                )

            after_decision_epoch = _read_epoch(self._epoch_reader)
            if after_decision_epoch != before_epoch:
                raise TeacherDecisionChannelError(
                    "connection epoch changed during teacher decision"
                )
            if approved is not True:
                raise TeacherDecisionChannelError(
                    "teacher explicitly denied this physical run"
                )

            # Positive authority is minted only after the teacher write side is
            # definitively closed. This makes duplicate/late frames impossible
            # after authority publication rather than merely ignored.
            self._require_peer_write_closed(timeout)
            if _read_epoch(self._epoch_reader) != before_epoch:
                raise TeacherDecisionChannelError(
                    "connection epoch changed while sealing teacher decision"
                )

            try:
                receipt = authorizer.authorize_run(
                    binding,
                    lambda exact_binding: exact_binding == binding,
                )
            except TeacherRunAuthorizationError as exc:
                raise TeacherDecisionChannelError(
                    "teacher authorization receipt could not be minted"
                ) from exc

            after_mint_epoch = _read_epoch(self._epoch_reader)
            if after_mint_epoch != before_epoch:
                try:
                    authorizer.close_run(
                        receipt,
                        "connection epoch changed while minting teacher authorization",
                    )
                except TeacherRunAuthorizationError:
                    receipt.invalidate(
                        "connection epoch changed while minting teacher authorization"
                    )
                raise TeacherDecisionChannelError(
                    "connection epoch changed while minting teacher authorization"
                )
            if (
                type(receipt) is not TeacherRunAuthorization
                or receipt.binding != binding
                or receipt.active is not True
            ):
                if type(receipt) is TeacherRunAuthorization:
                    try:
                        authorizer.close_run(
                            receipt,
                            "invalid teacher authorization receipt",
                        )
                    except TeacherRunAuthorizationError:
                        receipt.invalidate("invalid teacher authorization receipt")
                raise TeacherDecisionChannelError(
                    "teacher authorization receipt does not match the approved run"
                )

            self._finish("teacher decision consumed")
            return receipt
        except Exception as exc:
            if receipt is not None and receipt.active:
                try:
                    authorizer.close_run(receipt, "teacher decision failed closed")
                except TeacherRunAuthorizationError:
                    receipt.invalidate("teacher decision failed closed")
            with self._lock:
                already_terminal = self._terminal
            if not already_terminal:
                self._finish(exc)
            if isinstance(exc, TeacherDecisionChannelError):
                raise
            if isinstance(exc, TeacherRunAuthorizationError):
                raise TeacherDecisionChannelError(str(exc)) from exc
            raise TeacherDecisionChannelError(
                "teacher decision failed closed"
            ) from exc

    def close(self) -> None:
        with self._lock:
            if not self._terminal:
                self._terminal = True
                self._terminal_reason = "teacher decision channel closed"
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._socket.close()
        except OSError:
            pass
