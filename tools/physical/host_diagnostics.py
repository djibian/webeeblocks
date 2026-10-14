"""Bounded, best-effort host diagnostics that cannot stall physical recovery.

One daemon owns writes, including writes to full or closed OS stderr pipes.
Diagnostic records may be lost if stderr is unavailable; the independent caller
response still carries the failure cause when its channel remains open.
No diagnostic writer holds a lock used for radio authority or recovery.
"""
from __future__ import annotations

import json
import os
from queue import Full, Queue
from threading import Event, Lock, Thread


class HostDiagnostics:
    """One bounded diagnostic queue, never a synchronous control-path write."""

    def __init__(self, stream: object) -> None:
        self._stream = stream
        try:
            self._fd: int | None = stream.fileno()
        except (AttributeError, OSError, ValueError):
            self._fd = None
        self._queue: Queue[str | None] = Queue(maxsize=16)
        self._lock = Lock()
        self._drained = Event()
        self._drained.set()
        self._pending = 0
        self.dropped = 0
        self._worker = Thread(target=self._write, daemon=True, name="host-diagnostics")
        self._worker.start()

    def emit(self, label: str, payload: dict[str, object]) -> None:
        try:
            line = label + " " + json.dumps(payload, sort_keys=True) + "\n"
        except (TypeError, ValueError, OSError):
            return  # An unavailable diagnostic must never replace a causal failure.
        with self._lock:
            try:
                self._queue.put_nowait(line)
            except Full:
                self.dropped += 1
            else:
                self._pending += 1
                self._drained.clear()

    def _write(self) -> None:
        while True:
            line = self._queue.get()
            if line is None:
                return
            try:
                if self._fd is None:
                    self._stream.write(line)
                    self._stream.flush()
                else:
                    # Bypass buffered sys.stderr locks: a daemon blocked in a
                    # full pipe must not deadlock interpreter shutdown.
                    data = line.encode("utf-8")
                    offset = 0
                    while offset < len(data):
                        written = os.write(self._fd, data[offset:])
                        if written == 0:
                            raise OSError("zero-byte diagnostic write")
                        offset += written
            except Exception:
                pass  # Only best-effort evidence; never replace the real failure.
            finally:
                with self._lock:
                    self._pending -= 1
                    if not self._pending:
                        self._drained.set()

    def finish(self, *, timeout_seconds: float = 0.1) -> None:
        """Allow normal sinks to drain; never wait indefinitely for stderr."""
        if self._drained.wait(timeout_seconds):
            try:
                self._queue.put_nowait(None)
            except Full:
                pass
