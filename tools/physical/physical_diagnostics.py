"""Bounded failure evidence. This module grants no physical authority.

Keep the causal exception chain across host/launcher IPC without serializing
traceback locals, capability tokens, sockets or the student's entire program.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from time import monotonic_ns


def record_inflight_range(binding, sample, error, *, returned: bool) -> None:
    """Best-effort raw evidence; neither logging nor these fields grant authority.

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
            return
        print("HOST_INFLIGHT_RANGE " + json.dumps({
            **raw, "profileId": binding.profile_id,
            "astSha256": hashlib.sha256(binding.ast_binding.encode("utf-8")).hexdigest(),
            "hostReportMonotonicNs": monotonic_ns(),
            "backendReadAccepted": returned,
            "executionAuthority": False,
            "boundary": "LOG publication; no producer-age, clearance or continuous-availability proof",
        }, sort_keys=True), file=sys.stderr, flush=True)
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
