#!/usr/bin/env python3
"""One-shot trusted teacher decision channel for physical-run authorization.

This module transports only one exact teacher decision into the trusted physical
host.  It does not grant execution authority by itself and exposes no Crazyflie
command surface.  The trusted launcher chooses the connected socket; ordinary
caller/browser channels must never be substituted for it.

The host sends one exact profile/AST/connection-epoch challenge and accepts only
one correlated reply.  Any denial, malformed/ambiguous transport, wrong binding,
or connection-epoch change makes the channel terminal.  A positive decision is
turned into the existing #267 TeacherRunAuthorization by a host-local
TrustedTeacherAuthorizer; the receipt never needs to cross this channel.
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
_DEFAULT_TIMEOUT_SECONDS = 5.0


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


class TrustedTeacherDecisionChannel:
    """One launcher-installed duplex channel for one exact teacher decision."""

    def __init__(
        self,
        channel_socket: socket.socket,
        connection_epoch_reader: Callable[[], str],
        *,
        request_id_factory: Callable[[], str] | None = None,
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
        self._request_id_factory = request_id_factory or (
            lambda: secrets.token_urlsafe(24)
        )
        if not callable(self._request_id_factory):
            raise TeacherDecisionChannelError(
                "teacher decision request-id factory must be callable"
            )
        self._lock = Lock()
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

    def _finish(self, reason: str) -> None:
        message = str(reason).strip() or "teacher decision channel is terminal"
        self._terminal = True
        self._terminal_reason = message

    def _request_id(self) -> str:
        try:
            value = self._request_id_factory()
        except Exception as exc:
            raise TeacherDecisionChannelError(
                "teacher decision request id is unavailable"
            ) from exc
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise TeacherDecisionChannelError(
                "teacher decision request id must be non-empty trimmed text"
            )
        return value

    def _send_json_line(self, payload: dict[str, object], timeout: float) -> None:
        encoded = (
            json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode("utf-8")
        if len(encoded) > _MAX_MESSAGE_BYTES:
            raise TeacherDecisionChannelError("teacher decision request is too large")
        try:
            self._socket.settimeout(timeout)
            self._socket.sendall(encoded)
        except OSError as exc:
            raise TeacherDecisionChannelError(
                "teacher decision request transport failed"
            ) from exc

    def _recv_json_line(self, timeout: float) -> dict[str, object]:
        data = bytearray()
        try:
            self._socket.settimeout(timeout)
            while len(data) <= _MAX_MESSAGE_BYTES:
                chunk = self._socket.recv(1)
                if not chunk:
                    raise TeacherDecisionChannelError(
                        "teacher decision channel closed before a reply"
                    )
                data.extend(chunk)
                if chunk == b"\n":
                    break
            else:
                raise TeacherDecisionChannelError(
                    "teacher decision reply exceeds size limit"
                )
        except socket.timeout as exc:
            raise TeacherDecisionChannelError("teacher decision timed out") from exc
        except OSError as exc:
            raise TeacherDecisionChannelError(
                "teacher decision reply transport failed"
            ) from exc

        if not data.endswith(b"\n"):
            raise TeacherDecisionChannelError(
                "teacher decision reply is not line terminated"
            )
        try:
            payload = json.loads(bytes(data[:-1]).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise TeacherDecisionChannelError(
                "teacher decision reply is malformed JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise TeacherDecisionChannelError(
                "teacher decision reply must be a JSON object"
            )
        return payload

    def authorize_run(
        self,
        binding: PhysicalRunBinding,
        authorizer: TrustedTeacherAuthorizer,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> TeacherRunAuthorization:
        """Request exactly one teacher decision and mint the matching #267 receipt."""
        if type(binding) is not PhysicalRunBinding:
            raise TeacherDecisionChannelError(
                "exact physical run binding is required for teacher decision"
            )
        if type(authorizer) is not TrustedTeacherAuthorizer:
            raise TeacherDecisionChannelError(
                "exact trusted teacher authorizer is required"
            )
        timeout = _require_timeout(timeout_seconds)

        with self._lock:
            if self._terminal:
                raise TeacherDecisionChannelError(
                    "teacher decision channel is terminal: "
                    + (self._terminal_reason or "prior decision consumed")
                )
            try:
                before_epoch = _read_epoch(self._epoch_reader)
                if before_epoch != binding.connection_epoch:
                    raise TeacherDecisionChannelError(
                        "teacher decision binding does not match the live connection epoch"
                    )

                request_id = self._request_id()
                self._send_json_line(
                    {
                        "op": "teacher-run-decision",
                        "requestId": request_id,
                        "profileId": binding.profile_id,
                        "astBinding": binding.ast_binding,
                        "connectionEpoch": binding.connection_epoch,
                        "executionAuthority": False,
                    },
                    timeout,
                )
                response = self._recv_json_line(timeout)

                if response.get("op") != "teacher-run-decision-result":
                    raise TeacherDecisionChannelError(
                        "teacher decision reply has the wrong operation"
                    )
                if response.get("requestId") != request_id:
                    raise TeacherDecisionChannelError(
                        "teacher decision reply has the wrong correlation id"
                    )
                if response.get("executionAuthority") is not False:
                    raise TeacherDecisionChannelError(
                        "teacher decision transport must remain non-authority"
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

                after_epoch = _read_epoch(self._epoch_reader)
                if after_epoch != before_epoch:
                    raise TeacherDecisionChannelError(
                        "connection epoch changed during teacher decision"
                    )

                if approved is not True:
                    raise TeacherDecisionChannelError(
                        "teacher explicitly denied this physical run"
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
                if (
                    type(receipt) is not TeacherRunAuthorization
                    or receipt.binding != binding
                    or receipt.active is not True
                ):
                    try:
                        if type(receipt) is TeacherRunAuthorization:
                            authorizer.close_run(
                                receipt,
                                "invalid teacher authorization receipt",
                            )
                    except TeacherRunAuthorizationError:
                        pass
                    raise TeacherDecisionChannelError(
                        "teacher authorization receipt does not match the approved run"
                    )
                self._finish("teacher decision consumed")
                return receipt
            except Exception as exc:
                if not self._terminal:
                    self._finish(str(exc))
                if isinstance(exc, TeacherDecisionChannelError):
                    raise
                raise TeacherDecisionChannelError(
                    "teacher decision failed closed"
                ) from exc

    def close(self) -> None:
        with self._lock:
            if not self._terminal:
                self._finish("teacher decision channel closed")
            try:
                self._socket.close()
            except OSError:
                pass
