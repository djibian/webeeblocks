#!/usr/bin/env python3
"""Pure, non-authorizing conditional physical margin arithmetic for #157.

All inputs are externally established *bounds*, not estimates inferred from this
program. A structurally complete sheet is not a qualified physical domain.
No cflib import, IO to a Crazyflie, control command or teacher authority exists.
"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
import json
from math import inf, isfinite, nextafter
from pathlib import Path
import re
import sys

class EvidenceError(ValueError):
    """A bound, provenance identifier or witness reference is incomplete."""

# This deliberately does not accept a 210-second simulation rule as endurance.
# Each value must have a digest of independent supporting evidence. This checks
# syntactic provenance only: the supplied digest is NOT attested by this tool.
BOUNDS = {
    "distance_to_hazard_m": True,
    "prior_horizontal_excursion_m": False,
    "rotor_radius_m": True,
    "geometry_uncertainty_m": False,
    "max_hazard_approach_speed_m_s": False,
    "max_abort_to_deceleration_s": False,
    "min_supported_deceleration_m_s2": True,
    "endurance_lower_bound_s": True,
    "max_planned_motor_time_s": True,
    "max_abort_to_motor_off_s": True,
    "energy_time_reserve_s": False,
}

def _digest(value: object, length: int, name: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is None:
        raise EvidenceError(name + " must be a lowercase " + str(length) + "-hex identifier")
    return value

def _bound(source: dict, key: str, strictly_positive: bool) -> Fraction:
    item = source[key]
    if type(item) is not dict or set(item) != {"value", "evidence_sha256"}:
        raise EvidenceError(key + " needs exactly value and evidence_sha256")
    value = item["value"]
    if type(value) not in (int, float, Decimal):
        raise EvidenceError(key + " must be a finite numeric bound, not bool/string/null")
    # JSON decimal spellings stay exact. Direct Python float callers must keep
    # their EXACT binary value: Decimal(str(float)) can erase a negative margin
    # near zero and thereby overstate a conditional bound. Neither route attests
    # physical measurement accuracy, units or evidence provenance.
    number = Decimal.from_float(value) if type(value) is float else Decimal(value)
    if not number.is_finite():
        raise EvidenceError(key + " must be a finite numeric bound, not bool/string/null")
    if number < 0 or (strictly_positive and number == 0):
        raise EvidenceError(key + " has an impossible or missing bound")
    try:
        encoded = float(number)
    except (ValueError, OverflowError):
        raise EvidenceError(key + " cannot be represented by finite output arithmetic") from None
    if not isfinite(encoded) or (number != 0 and encoded == 0):
        raise EvidenceError(key + " cannot be represented by finite output arithmetic")
    _digest(item["evidence_sha256"], 64, key + " evidence_sha256")
    return Fraction(number)

def _outward(value: Fraction, *, lower: bool) -> float:
    """Return a finite float bounding the exact rational in the safe direction."""
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise EvidenceError("derived conditional budget overflowed; no finite bound") from None
    if not isfinite(result):
        raise EvidenceError("derived conditional budget overflowed; no finite bound")
    exact_output = Fraction.from_float(result)
    if (lower and exact_output > value) or (not lower and exact_output < value):
        result = nextafter(result, -inf if lower else inf)
    if not isfinite(result):
        raise EvidenceError("derived conditional budget overflowed; no finite bound")
    return result

def evaluate(sheet: object) -> dict[str, object]:
    if type(sheet) is not dict or set(sheet) != {"source_sha", "ast_sha256", "bounds"}:
        raise EvidenceError("sheet needs exactly source_sha, ast_sha256 and bounds")
    source = _digest(sheet["source_sha"], 40, "source_sha")
    ast = _digest(sheet["ast_sha256"], 64, "ast_sha256")
    bound_map = sheet["bounds"]
    if type(bound_map) is not dict or set(bound_map) != set(BOUNDS):
        missing = sorted(set(BOUNDS) - set(bound_map)) if type(bound_map) is dict else list(BOUNDS)
        extra = sorted(set(bound_map) - set(BOUNDS)) if type(bound_map) is dict else []
        raise EvidenceError("bound keys differ; missing=" + repr(missing) + ", extra=" + repr(extra))
    values = {name: _bound(bound_map, name, positive) for name, positive in BOUNDS.items()}
    speed = values["max_hazard_approach_speed_m_s"]
    latency = values["max_abort_to_deceleration_s"]
    decel = values["min_supported_deceleration_m_s2"]
    # Rational arithmetic preserves the exact sign of the supplied decimal
    # envelope, without an optimistic rounding error near either zero margin.
    # A finite positive deceleration is still NOT physically attested here.
    travel = speed * latency + speed * speed / (2 * decel)
    occupied = (values["prior_horizontal_excursion_m"]
                + values["rotor_radius_m"]
                + values["geometry_uncertainty_m"] + travel)
    duration = (values["max_planned_motor_time_s"]
                + values["max_abort_to_motor_off_s"]
                + values["energy_time_reserve_s"])
    horizontal_margin = values["distance_to_hazard_m"] - occupied
    endurance_margin = values["endurance_lower_bound_s"] - duration
    return {
        "status": "CONDITIONAL_ARITHMETIC_ONLY",
        "source_sha": source,
        "ast_sha256": ast,
        "abort_motion_allowance_m": _outward(travel, lower=False),
        "conditional_horizontal_margin_m": _outward(horizontal_margin, lower=True),
        "conditional_endurance_margin_s": _outward(endurance_margin, lower=True),
        "flight_authorized": False,
        "physical_qualification": "UNPROVEN",
        "warning": "Inputs are not physically attested; cannot infer safe flight, landing, or battery endurance.",
    }

def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("duplicate JSON key: " + repr(key))
        result[key] = value
    return result

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: conditional_flight_budget.py <offline-sheet.json>", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"),
                          parse_float=Decimal, object_pairs_hook=_unique_object,
                          parse_constant=lambda s: (_ for _ in ()).throw(EvidenceError("nonfinite JSON: " + s)))
        result = evaluate(data)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "INCOMPLETE", "flight_authorized": False,
                          "physical_qualification": "UNPROVEN",
                          "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
