#!/usr/bin/env python3
"""Concrete #249 current-program freshness guard for the physical effect path.

Integrated #277 provides the production host-initiated round trip for exact
current profile / backend-neutral AST / connection-epoch evidence. The ordinary
browser capability bearer cannot answer that round trip; only the distinct
closure-private #249 responder can settle a host-created challenge.

This module binds that concrete production bridge to one exact #267 run binding.
It deliberately accepts no assertion-shaped callback. Every assert_current()
call invokes a fresh ReadOnlyCapabilityHttpBridge.assert_current_program(...)
round trip and validates the bridge-private immutable evidence before returning
the binding to the effect transport.

The guard remains non-authority. Current-program evidence does not grant teacher
approval, watchdog liveness, powered-session authority, command acknowledgement
or trajectory completion.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

import serve_reference_capabilities as capability_bridge
from teacher_run_authorization import PhysicalRunBinding


class CurrentProgramPreflightError(RuntimeError):
    """Fail-closed error for unavailable or mismatched current-program evidence."""


_MINT_KEY = object()


@dataclass(frozen=True)
class CurrentProgramPreflightEvidence:
    """One fresh exact-program assertion translated from integrated #277 evidence."""

    binding: PhysicalRunBinding
    challenge_id: str
    execution_authority: bool = False


class LiveCurrentProgramPreflightGuard:
    """Private-minted handle onto the concrete production #249 host bridge."""

    def __init__(
        self,
        binding: PhysicalRunBinding,
        bridge: capability_bridge.ReadOnlyCapabilityHttpBridge,
        *,
        _mint_key: object,
    ) -> None:
        if _mint_key is not _MINT_KEY:
            raise CurrentProgramPreflightError(
                "current-program preflight guard may only be minted by trusted host factory"
            )
        if type(binding) is not PhysicalRunBinding:
            raise CurrentProgramPreflightError(
                "exact PhysicalRunBinding is required for current-program preflight"
            )
        if type(bridge) is not capability_bridge.ReadOnlyCapabilityHttpBridge:
            raise CurrentProgramPreflightError(
                "integrated #277 ReadOnlyCapabilityHttpBridge is required"
            )
        self._binding = binding
        self._bridge = bridge
        self._lock = Lock()

    @property
    def binding(self) -> PhysicalRunBinding:
        return self._binding

    def assert_current(self) -> CurrentProgramPreflightEvidence:
        """Synchronously require one fresh host-initiated #249 round trip."""
        with self._lock:
            try:
                evidence = self._bridge.assert_current_program(
                    profile_id=self._binding.profile_id,
                    ast_binding=self._binding.ast_binding,
                    connection_epoch=self._binding.connection_epoch,
                )
            except Exception as exc:
                raise CurrentProgramPreflightError(
                    "integrated #249 current-program re-assertion failed"
                ) from exc

            if type(evidence) is not capability_bridge.CurrentProgramPreflightEvidence:
                raise CurrentProgramPreflightError(
                    "integrated #277 bridge returned invalid current-program evidence"
                )
            if evidence.execution_authority is not False:
                raise CurrentProgramPreflightError(
                    "current-program evidence crossed the non-authority boundary"
                )
            if (
                evidence.profile_id != self._binding.profile_id
                or evidence.ast_binding != self._binding.ast_binding
                or evidence.connection_epoch != self._binding.connection_epoch
            ):
                raise CurrentProgramPreflightError(
                    "current profile/AST/connection binding differs from authorized run"
                )
            if not isinstance(evidence.challenge_id, str) or not evidence.challenge_id.strip():
                raise CurrentProgramPreflightError(
                    "current-program challenge provenance is unavailable"
                )
            return CurrentProgramPreflightEvidence(
                binding=self._binding,
                challenge_id=evidence.challenge_id,
            )


class TrustedCurrentProgramPreflightFactory:
    """Bind the integrated #277 production bridge to exact run evidence."""

    def __init__(
        self,
        bridge: capability_bridge.ReadOnlyCapabilityHttpBridge,
    ) -> None:
        if type(bridge) is not capability_bridge.ReadOnlyCapabilityHttpBridge:
            raise CurrentProgramPreflightError(
                "integrated #277 ReadOnlyCapabilityHttpBridge is required"
            )
        self._bridge = bridge

    def bind(
        self,
        binding: PhysicalRunBinding,
    ) -> LiveCurrentProgramPreflightGuard:
        if type(binding) is not PhysicalRunBinding:
            raise CurrentProgramPreflightError(
                "exact PhysicalRunBinding is required for current-program preflight"
            )
        return LiveCurrentProgramPreflightGuard(
            binding,
            self._bridge,
            _mint_key=_MINT_KEY,
        )
