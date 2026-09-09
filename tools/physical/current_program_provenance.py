#!/usr/bin/env python3
"""Effect-side client for fresh current-program provenance authority.

The effect process receives only an already-established OS socket capability
from trusted production composition. This module deliberately imports no
Crazyflie capability bridge/session implementation and exposes no responder,
challenge-answer, bridge-binding or evidence-mint surface.

A request names the exact profile / canonical AST binding / connection epoch.
The separate authority process performs the integrated #278/#249 round trip and
returns non-authority evidence. Transport/protocol ambiguity poisons this client;
a clean negative assertion does not.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import secrets
import socket
from threading import Lock


_MAX_MESSAGE_BYTES = 8192


class CurrentProgramProvenanceError(RuntimeError):
    """Fail-closed current-program authority-channel error."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise CurrentProgramProvenanceError(f"{name} must be a non-empty trimmed string")
    return value


def _timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CurrentProgramProvenanceError("authority timeout must be positive")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0.0:
        raise CurrentProgramProvenanceError("authority timeout must be positive")
    return parsed


@dataclass(frozen=True, slots=True)
class CurrentProgramAuthorityEvidence:
    """Exact fresh non-authority result received from the authority process."""

    request_id: str
    challenge_id: str
    profile_id: str
    ast_binding: str
    connection_epoch: str
    execution_authority: bool = False


class CurrentProgramProvenanceClient:
    """One serialized capability onto the separate current-program authority."""

    __slots__ = ("__socket", "__lock", "__poisoned")

    def __init__(self, channel: socket.socket) -> None:
        if type(channel) is not socket.socket:
            raise CurrentProgramProvenanceError(
                "exact connected OS socket capability is required"
            )
        try:
            channel.getpeername()
        except OSError as exc:
            raise CurrentProgramProvenanceError(
                "current-program authority socket is not connected"
            ) from exc
        self.__socket = channel
        self.__lock = Lock()
        self.__poisoned = False

    @property
    def poisoned(self) -> bool:
        with self.__lock:
            return self.__poisoned

    def _poison(self) -> None:
        self.__poisoned = True
        try:
            self.__socket.close()
        except OSError:
            pass

    def _read_line(self) -> bytes:
        data = bytearray()
        while len(data) <= _MAX_MESSAGE_BYTES:
            chunk = self.__socket.recv(1)
            if not chunk:
                raise CurrentProgramProvenanceError(
                    "current-program authority channel closed before reply"
                )
            if chunk == b"\n":
                return bytes(data)
            data.extend(chunk)
        raise CurrentProgramProvenanceError(
            "current-program authority reply exceeds protocol limit"
        )

    def assert_current_program(
        self,
        *,
        profile_id: str,
        ast_binding: str,
        connection_epoch: str,
        timeout_seconds: float = 1.0,
    ) -> CurrentProgramAuthorityEvidence:
        profile = _text(profile_id, "profileId")
        ast = _text(ast_binding, "astBinding")
        epoch = _text(connection_epoch, "connectionEpoch")
        timeout = _timeout(timeout_seconds)
        request_id = secrets.token_urlsafe(24)
        request = {
            "op": "assert-current-program",
            "requestId": request_id,
            "profileId": profile,
            "astBinding": ast,
            "connectionEpoch": epoch,
        }
        encoded = (
            json.dumps(request, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode("utf-8")

        with self.__lock:
            if self.__poisoned:
                raise CurrentProgramProvenanceError(
                    "current-program authority channel is poisoned"
                )
            try:
                self.__socket.settimeout(timeout)
                self.__socket.sendall(encoded)
                raw = self._read_line()
                reply = json.loads(raw.decode("utf-8"))
                if not isinstance(reply, dict):
                    raise CurrentProgramProvenanceError(
                        "current-program authority reply must be a JSON object"
                    )
                if reply.get("requestId") != request_id:
                    raise CurrentProgramProvenanceError(
                        "current-program authority reply correlation failed"
                    )
                if reply.get("executionAuthority") is not False:
                    raise CurrentProgramProvenanceError(
                        "current-program authority crossed the non-authority boundary"
                    )
                if reply.get("ok") is not True:
                    error = reply.get("error")
                    if not isinstance(error, str) or not error.strip():
                        raise CurrentProgramProvenanceError(
                            "current-program authority negative reply is malformed"
                        )
                    raise _NegativeCurrentProgramAssertion(error.strip())

                challenge = _text(reply.get("challengeId"), "challengeId")
                if (
                    reply.get("profileId") != profile
                    or reply.get("astBinding") != ast
                    or reply.get("connectionEpoch") != epoch
                ):
                    raise CurrentProgramProvenanceError(
                        "current-program authority reply binding mismatch"
                    )
                return CurrentProgramAuthorityEvidence(
                    request_id=request_id,
                    challenge_id=challenge,
                    profile_id=profile,
                    ast_binding=ast,
                    connection_epoch=epoch,
                )
            except _NegativeCurrentProgramAssertion as exc:
                raise CurrentProgramProvenanceError(
                    "current-program assertion was not established: " + str(exc)
                ) from exc
            except Exception as exc:
                self._poison()
                if isinstance(exc, CurrentProgramProvenanceError):
                    raise
                raise CurrentProgramProvenanceError(
                    "current-program authority channel failed or is ambiguous"
                ) from exc
            finally:
                if not self.__poisoned:
                    try:
                        self.__socket.settimeout(None)
                    except OSError:
                        self._poison()


class _NegativeCurrentProgramAssertion(RuntimeError):
    pass
