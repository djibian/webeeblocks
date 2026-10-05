"""Bounded failure evidence. This module grants no physical authority.

Keep the causal exception chain across host/launcher IPC without serializing
traceback locals, capability tokens, sockets or the student's entire program.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


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
    if binding is not None:
        result.update(
            profileId=binding.profile_id,
            astSha256=hashlib.sha256(binding.ast_binding.encode("utf-8")).hexdigest(),
            connectionEpoch=binding.connection_epoch,
        )
    return result
