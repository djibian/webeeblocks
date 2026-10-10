"""Bounded failure evidence. This module grants no physical authority.

Keep the causal exception chain across host/launcher IPC without serializing
traceback locals, capability tokens, sockets or the student's entire program.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from queue import Full, Queue
import sys
from threading import Thread
from time import monotonic_ns


class _InflightRangeReporter:
    """Bounded diagnostic writer; no control-path I/O, drain or worker join.

    A stalled sink can occupy only this daemon and at most 64 queued records.
    Lost/full/failed output means incomplete evidence, never a flight retry.
    """

    def __init__(self):
        self.queue = Queue(maxsize=64)
        self.available = False
        try:
            Thread(target=self._run, name="range-evidence", daemon=True).start()
            self.available = True
        except Exception:
            pass

    def submit(self, sink, line):
        if not self.available or len(line.encode("utf-8")) > 4096:
            return
        try:
            self.queue.put_nowait((sink, line))
        except Full:
            pass

    def _run(self):
        while True:
            sink, line = self.queue.get()
            try:
                try:
                    fd = sink.fileno()
                except (AttributeError, OSError, ValueError):
                    # In-memory/test streams have no OS descriptor.
                    sink.write(line)
                    sink.flush()
                else:
                    # One bounded pipe write also avoids acquiring the shared
                    # TextIO lock that other host diagnostics may use.
                    os.write(fd, line.encode("utf-8"))
            except Exception:
                pass
            finally:
                self.queue.task_done()


_INFLIGHT_REPORTER = _InflightRangeReporter()


def record_inflight_range(binding, sample, error, *, returned: bool, raw_observation=None) -> None:
    """Best-effort nonblocking handoff; these fields grant no authority.

    The host time dates this report, not arrival, sensor production or thrust.
    A missing record makes the later scientific comparison incomplete, never
    changes execution/recovery or licenses a retry.
    """
    try:
        from range_observer import RangeObservation
        raw = None
        if type(sample) is RangeObservation:
            raw = {
                "connectionEpoch": sample.connection_epoch,
                "direction": sample.direction, "rawMm": sample.raw_mm,
                "logTimestampMs": sample.firmware_timestamp_ms,
            }
        elif error is not None:
            raw = getattr(error, "range_observation", None)
        if not isinstance(raw, dict):
            raw = raw_observation
        if not isinstance(raw, dict):
            return
        line = "HOST_INFLIGHT_RANGE " + json.dumps({
            **raw, "profileId": binding.profile_id,
            "astSha256": hashlib.sha256(binding.ast_binding.encode("utf-8")).hexdigest(),
            "hostReportMonotonicNs": monotonic_ns(),
            "backendReadAccepted": returned,
            "executionAuthority": False,
            "boundary": "LOG publication; no producer-age, clearance or continuous-availability proof",
        }, sort_keys=True) + "\n"
        _INFLIGHT_REPORTER.submit(sys.stderr, line)
    except Exception:
        # Evidence output must not replace a primary exception, prevent recovery
        # or turn a failed observation into a successful interpreter value.
        pass


def failure_evidence(error: BaseException, *, binding=None, phase=None) -> dict:
    causes = []
    seen = set()
    current = error
    while current is not None and id(current) not in seen and len(causes) < 12:
        seen.add(id(current))
        item = {
            "type": type(current).__name__,
            "message": str(current)[:400],
        }
        if len(str(current)) > 400:
            item["messageTruncated"] = True
        worker = getattr(current, "physical_worker", None)
        if isinstance(worker, dict):
            item["worker"] = worker
        trace = current.__traceback__
        if trace is not None:
            while trace.tb_next is not None:
                trace = trace.tb_next
            item["source"] = (
                Path(trace.tb_frame.f_code.co_filename).name
                + ":" + str(trace.tb_lineno)
                + ":" + trace.tb_frame.f_code.co_name
            )
        site = getattr(current, "physical_call", None)
        if isinstance(site, dict):
            item["call"] = site
        causes.append(item)
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
    result = {"causes": causes, "phase": phase}
    if current is not None:
        result["causeChainTruncated"] = True
    if binding is not None:
        result.update(
            profileId=binding.profile_id,
            astSha256=hashlib.sha256(binding.ast_binding.encode("utf-8")).hexdigest(),
            connectionEpoch=binding.connection_epoch,
        )
    return result
