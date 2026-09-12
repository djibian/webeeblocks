#!/usr/bin/env python3
"""Host-owned runtime nominal-altitude state for dynamic physical programs.

The conservative dynamic preflight proves that every reachable vertical path of
one exact teacher-bound AST remains inside the established physical altitude
envelope. This module tracks which of those already-proven vertical effects
actually completed at runtime.

It is deliberately non-authority state. It emits no packet, chooses no branch,
accepts no browser/IPC input and cannot make a physical effect eligible. The
trusted shared-interpreter backend may advance it only after a selected vertical
effect has definitively completed. A rejected, failed or ambiguous effect leaves
the state unchanged.

Terminal landing uses an opaque evidence object minted from this state so its
descent can follow the branch that really executed instead of the conservative
union of all reachable branches.
"""
from __future__ import annotations

from math import isfinite
from threading import Lock

import high_level_semantics
import physical_program_sequence
from physical_dynamic_preflight import ReachablePhysicalEnvelope

_EPSILON = 1e-9
_MINT_KEY = object()


class RuntimeNominalAltitudeError(RuntimeError):
    """Fail-closed error for branch-selected physical altitude state."""


class RuntimeLandingAltitudeEvidence:
    """Opaque non-authority evidence for one host-owned runtime altitude."""

    __slots__ = ("_ast_binding", "_altitude_m", "_terminal_low", "_terminal_high")

    def __init__(
        self,
        ast_binding: str,
        altitude_m: float,
        terminal_low: float,
        terminal_high: float,
        *,
        _mint_key: object,
    ) -> None:
        if _mint_key is not _MINT_KEY:
            raise RuntimeNominalAltitudeError(
                "runtime landing altitude evidence may only be minted by trusted host state"
            )
        self._ast_binding = ast_binding
        self._altitude_m = altitude_m
        self._terminal_low = terminal_low
        self._terminal_high = terminal_high

    @property
    def ast_binding(self) -> str:
        return self._ast_binding

    @property
    def altitude_m(self) -> float:
        return self._altitude_m

    @property
    def terminal_low_m(self) -> float:
        return self._terminal_low

    @property
    def terminal_high_m(self) -> float:
        return self._terminal_high


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeNominalAltitudeError(label + " must be finite")
    parsed = float(value)
    if not isfinite(parsed):
        raise RuntimeNominalAltitudeError(label + " must be finite")
    return parsed


def _inside(value: float, low: float, high: float) -> bool:
    return low - _EPSILON <= value <= high + _EPSILON


class RuntimeNominalAltitude:
    """Exact host-local altitude after definitively completed selected effects."""

    def __init__(self, safety: ReachablePhysicalEnvelope) -> None:
        if type(safety) is not ReachablePhysicalEnvelope:
            raise RuntimeNominalAltitudeError(
                "exact dynamic physical safety evidence is required"
            )
        if (
            not isinstance(safety.ast_binding, str)
            or not safety.ast_binding.strip()
            or safety.ast_binding != safety.ast_binding.strip()
        ):
            raise RuntimeNominalAltitudeError(
                "dynamic physical safety binding is invalid"
            )

        initial = _finite(safety.initial_altitude_m, "initial nominal altitude")
        low = _finite(safety.min_altitude_m, "reachable minimum altitude")
        high = _finite(safety.max_altitude_m, "reachable maximum altitude")
        terminal_low = _finite(
            safety.terminal_min_altitude_m, "terminal minimum altitude"
        )
        terminal_high = _finite(
            safety.terminal_max_altitude_m, "terminal maximum altitude"
        )
        if (
            low > high
            or terminal_low > terminal_high
            or not _inside(initial, low, high)
            or low < physical_program_sequence.MIN_NOMINAL_ALTITUDE_M
            or high > physical_program_sequence.MAX_NOMINAL_ALTITUDE_M
            or not _inside(terminal_low, low, high)
            or not _inside(terminal_high, low, high)
        ):
            raise RuntimeNominalAltitudeError(
                "dynamic physical safety altitude envelope is inconsistent"
            )

        self._safety = safety
        self._altitude_m = initial
        self._lock = Lock()

    @property
    def ast_binding(self) -> str:
        return self._safety.ast_binding

    @property
    def altitude_m(self) -> float:
        with self._lock:
            return self._altitude_m

    def record_vertical_completion(
        self,
        direction: object,
        distance_m: object,
    ) -> float:
        """Advance only after the trusted consumer proved one selected vertical effect."""
        if not isinstance(direction, str):
            raise RuntimeNominalAltitudeError(
                "completed vertical direction is malformed"
            )
        try:
            target = high_level_semantics.vertical_move(direction, distance_m)
        except (
            TypeError,
            ValueError,
            high_level_semantics.HighLevelSemanticError,
        ) as exc:
            raise RuntimeNominalAltitudeError(
                "completed vertical effect violates integrated semantics"
            ) from exc

        delta = _finite(target.z_m, "completed vertical altitude delta")
        with self._lock:
            candidate = self._altitude_m + delta
            if (
                not _inside(
                    candidate,
                    self._safety.min_altitude_m,
                    self._safety.max_altitude_m,
                )
                or candidate
                < physical_program_sequence.MIN_NOMINAL_ALTITUDE_M - _EPSILON
                or candidate
                > physical_program_sequence.MAX_NOMINAL_ALTITUDE_M + _EPSILON
            ):
                raise RuntimeNominalAltitudeError(
                    "completed vertical effect escaped pre-takeoff safety envelope"
                )
            self._altitude_m = candidate
            return candidate

    def landing_evidence(self) -> RuntimeLandingAltitudeEvidence:
        """Mint non-authority altitude data for the interpreter-selected terminal land."""
        with self._lock:
            altitude = self._altitude_m
            if not _inside(
                altitude,
                self._safety.terminal_min_altitude_m,
                self._safety.terminal_max_altitude_m,
            ):
                raise RuntimeNominalAltitudeError(
                    "runtime altitude is outside the proven terminal envelope"
                )
            return RuntimeLandingAltitudeEvidence(
                self._safety.ast_binding,
                altitude,
                self._safety.terminal_min_altitude_m,
                self._safety.terminal_max_altitude_m,
                _mint_key=_MINT_KEY,
            )
