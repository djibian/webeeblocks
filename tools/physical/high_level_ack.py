#!/usr/bin/env python3
"""Pure freshness/serialization domain for HighLevel SETPOINT_HL acknowledgements.

The pinned Crazyflie firmware acknowledges high-level commander requests with a
four-byte reply containing only request bytes 0..2 plus one result byte. There
is no transaction nonce. A timeout, malformed reply, disconnect or epoch change
can therefore leave an old reply in flight, exactly where blind command retry
would be unsafe.

This module deliberately emits no CRTP packet and imports no cflib command
surface. It supplies the process-wide connection-epoch freshness discipline that
a later trusted host transport must wrap around its single physical send.

A new connection epoch clears only reply-matching ambiguity. It does not prove
the outcome of a previously emitted physical effect and must never be treated as
flight-inactive or reset evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable

_REPLY_SIZE = 4
_REPLY_PREFIX_SIZE = 3
_MAX_CRTP_DATA_SIZE = 30

_EPOCH_STATE_LOCK = Lock()
_POISONED_EPOCHS: dict[str, str] = {}
_EPOCH_TRANSACTION_LOCKS: dict[str, Lock] = {}


class HighLevelAckError(RuntimeError):
    """Fail-closed error for unavailable HighLevel acknowledgement freshness."""


def _read_nonempty_epoch(reader: Callable[[], str]) -> str:
    try:
        value = reader()
    except Exception as exc:
        raise HighLevelAckError(
            "connection epoch is unavailable for HighLevel acknowledgement"
        ) from exc
    if not isinstance(value, str) or not value.strip():
        raise HighLevelAckError(
            "connection epoch is invalid for HighLevel acknowledgement"
        )
    return value.strip()


def _poison_epoch(epoch: str, reason: str) -> None:
    message = str(reason).strip() or "ambiguous HighLevel acknowledgement outcome"
    with _EPOCH_STATE_LOCK:
        _POISONED_EPOCHS.setdefault(epoch, message)


def _poison_reason(epoch: str) -> str | None:
    with _EPOCH_STATE_LOCK:
        return _POISONED_EPOCHS.get(epoch)


def _transaction_lock(epoch: str) -> Lock:
    with _EPOCH_STATE_LOCK:
        lock = _EPOCH_TRANSACTION_LOCKS.get(epoch)
        if lock is None:
            lock = Lock()
            _EPOCH_TRANSACTION_LOCKS[epoch] = lock
        return lock


def _request_bytes(value: object) -> bytes:
    if isinstance(value, bytearray):
        data = bytes(value)
    elif isinstance(value, bytes):
        data = value
    else:
        raise HighLevelAckError("HighLevel request must be bytes")
    if len(data) < _REPLY_PREFIX_SIZE:
        raise HighLevelAckError(
            "HighLevel request is too short for firmware acknowledgement correlation"
        )
    if len(data) > _MAX_CRTP_DATA_SIZE:
        raise HighLevelAckError("HighLevel request exceeds CRTP data capacity")
    return data


def _reply_bytes(value: object) -> bytes:
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    raise HighLevelAckError("HighLevel acknowledgement must be bytes")


@dataclass(frozen=True)
class HighLevelAckResult:
    """Definitive application-level reply for one exactly serialized request."""

    connection_epoch: str
    request_prefix: bytes
    status: int

    @property
    def accepted(self) -> bool:
        return self.status == 0


class HighLevelAckDomain:
    """Process-wide epoch-bound acknowledgement freshness/serialization domain."""

    def __init__(self, connection_epoch_reader: Callable[[], str]) -> None:
        if not callable(connection_epoch_reader):
            raise HighLevelAckError(
                "connection epoch reader is required for HighLevel acknowledgement"
            )
        self._connection_epoch_reader = connection_epoch_reader
        self._bound_connection_epoch = _read_nonempty_epoch(
            self._connection_epoch_reader
        )
        self._lock = _transaction_lock(self._bound_connection_epoch)
        self._raise_if_poisoned()

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    @property
    def poisoned(self) -> bool:
        return _poison_reason(self._bound_connection_epoch) is not None

    def _raise_if_poisoned(self) -> None:
        reason = _poison_reason(self._bound_connection_epoch)
        if reason is not None:
            raise HighLevelAckError(
                "HighLevel acknowledgement freshness is poisoned for this "
                "connection epoch: " + reason
            )

    def _verify_epoch(self, *, poison_on_change: bool) -> None:
        self._raise_if_poisoned()
        current = _read_nonempty_epoch(self._connection_epoch_reader)
        if current != self._bound_connection_epoch:
            reason = "connection epoch changed during HighLevel acknowledgement"
            if poison_on_change:
                _poison_epoch(self._bound_connection_epoch, reason)
            raise HighLevelAckError(reason)

    def transaction(self, request: object) -> "HighLevelAckTransaction":
        """Reserve one epoch for one request; this method emits no physical effect."""
        self._verify_epoch(poison_on_change=False)
        data = _request_bytes(request)
        if not self._lock.acquire(blocking=False):
            raise HighLevelAckError(
                "another HighLevel acknowledgement transaction is already active"
            )
        try:
            self._verify_epoch(poison_on_change=False)
            return HighLevelAckTransaction(self, data, self._lock)
        except Exception:
            self._lock.release()
            raise


class HighLevelAckTransaction:
    """One prepared request around which a later transport performs one send."""

    _PREPARED = "prepared"
    _EMITTED = "emitted"
    _RESOLVED = "resolved"
    _AMBIGUOUS = "ambiguous"
    _CLOSED = "closed"

    def __init__(self, domain: HighLevelAckDomain, request: bytes, lock: Lock) -> None:
        self._domain = domain
        self._request = request
        self._prefix = request[:_REPLY_PREFIX_SIZE]
        self._lock = lock
        self._state = self._PREPARED
        self._released = False

    @property
    def request(self) -> bytes:
        return self._request

    @property
    def request_prefix(self) -> bytes:
        return self._prefix

    @property
    def emitted(self) -> bool:
        return self._state in (self._EMITTED, self._RESOLVED, self._AMBIGUOUS)

    def __enter__(self) -> "HighLevelAckTransaction":
        return self

    def mark_emitted(self) -> None:
        """Cross the effect boundary immediately before the caller's one send.

        The later physical transport must call this before invoking its send
        primitive. Any send exception then exits an emitted transaction and
        poisons acknowledgement freshness rather than being mistaken for a
        pre-effect local failure.
        """
        if self._state != self._PREPARED:
            raise HighLevelAckError(
                "HighLevel acknowledgement transaction is not prepared for emission"
            )
        try:
            self._domain._verify_epoch(poison_on_change=True)
        except Exception:
            self._state = self._AMBIGUOUS
            raise
        self._state = self._EMITTED

    def resolve_reply(self, reply: object) -> HighLevelAckResult:
        """Resolve one firmware reply; exact transport certainty is definitive."""
        if self._state != self._EMITTED:
            raise HighLevelAckError(
                "HighLevel acknowledgement reply requires an emitted request"
            )
        try:
            self._domain._verify_epoch(poison_on_change=True)
            data = _reply_bytes(reply)
            if len(data) != _REPLY_SIZE:
                raise HighLevelAckError("malformed HighLevel acknowledgement size")
            if data[:_REPLY_PREFIX_SIZE] != self._prefix:
                raise HighLevelAckError(
                    "HighLevel acknowledgement prefix does not match current request"
                )
        except Exception as exc:
            _poison_epoch(
                self._domain.bound_connection_epoch,
                str(exc) or "malformed HighLevel acknowledgement",
            )
            self._state = self._AMBIGUOUS
            raise
        self._state = self._RESOLVED
        return HighLevelAckResult(
            connection_epoch=self._domain.bound_connection_epoch,
            request_prefix=self._prefix,
            status=data[3],
        )

    def fail_ambiguous(self, reason: object) -> None:
        """Poison this epoch after timeout/disconnect/unknown post-send outcome."""
        if self._state != self._EMITTED:
            raise HighLevelAckError(
                "only an emitted HighLevel request can become transport-ambiguous"
            )
        message = str(reason).strip() or "ambiguous HighLevel acknowledgement outcome"
        _poison_epoch(self._domain.bound_connection_epoch, message)
        self._state = self._AMBIGUOUS
        raise HighLevelAckError(message)

    def _release(self) -> None:
        if not self._released:
            self._released = True
            self._lock.release()

    def close(self) -> None:
        """Release the transaction; unresolved post-send state poisons the epoch."""
        if self._state == self._EMITTED:
            _poison_epoch(
                self._domain.bound_connection_epoch,
                "emitted HighLevel request closed without definitive acknowledgement",
            )
            self._state = self._AMBIGUOUS
        elif self._state in (self._PREPARED, self._RESOLVED, self._AMBIGUOUS):
            self._state = self._CLOSED
        self._release()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False
