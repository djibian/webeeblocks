#!/usr/bin/env python3
"""Bounded ordinary IPC intake; caller loss can only revoke, never authorize.

One reader keeps observing EOF while the host executes a blocking physical
operation. No physical API, approval or program semantics exist in this helper.
"""
from queue import Empty, Full, Queue
from threading import Event, Thread


class CallerLifetime:
    def __init__(self, reader, *, max_message_bytes: int):
        self._reader = reader
        self._max_bytes = max_message_bytes
        self._closed = Event()
        self._reason = "host stopped"
        self._lines = Queue(maxsize=1)
        self._thread = Thread(target=self._receive, daemon=True)
        self._thread.start()

    def _receive(self):
        try:
            while not self._closed.is_set():
                line = self._reader.readline(self._max_bytes + 1)
                if not line:
                    self._reason = "caller EOF"
                    break
                if not line.endswith("\n") or len(line.encode("utf-8")) > self._max_bytes:
                    self._reason = "incomplete or oversized caller message"
                    break
                try:
                    self._lines.put_nowait(line)
                except Full:
                    self._reason = "overlapping caller requests"
                    break  # ordinary requests must be serialized, never queued for replay
        except Exception as exc:
            self._reason = type(exc).__name__ + ": " + str(exc)[:300]
        finally:
            self._closed.set()

    @property
    def close_reason(self):
        return self._reason if self._closed.is_set() else None

    def assert_open(self):
        if self._closed.is_set():
            raise RuntimeError("ordinary caller channel lost; program execution revoked: " + self._reason)

    def __iter__(self):
        while not self._closed.is_set():
            try:
                yield self._lines.get(timeout=0.05)
            except Empty:
                continue

    def stop(self):
        self._closed.set()
