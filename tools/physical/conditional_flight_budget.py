#!/usr/bin/env python3
"""Pure, non-authorizing conditional physical margin arithmetic for #157.

All inputs are externally established *bounds*, not estimates inferred from this
program. A structurally complete sheet is not a qualified physical domain.
No cflib import, IO to a Crazyflie, control command or teacher authority exists.
"""
from __future__ import annotations

import json
from math import isfinite
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

def _bound(source: dict, key: str, strictly_positive: bool) -> float:
    item = source[key]
    if type(item) is not dict or set(item) != {"value", "evidence_sha256"}:
        raise EvidenceError(key + " needs exactly value and evidence_sha256")
    value = item["value"]
    if type(value) not in (int, float) or not isfinite(value):
        raise EvidenceError(key + " must be a finite numeric bound, not bool/string/null")
    if value < 0 or (strictly_positive and value == 0):
        raise EvidenceError(key + " has an impossible or missing bound")
    _digest(item["evidence_sha256"], 64, key + " evidence_sha256")
    return float(value)

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
    # Only under a proven lower deceleration bound over the ENTIRE relevant
    # recovery domain; missing control/epoch certainty cannot supply that bound.
    travel = speed * latency + speed * speed / (2.0 * decel)
    occupied = (values["prior_horizontal_excursion_m"]
                + values["rotor_radius_m"]
                + values["geometry_uncertainty_m"] + travel)
    duration = (values["max_planned_motor_time_s"]
                + values["max_abort_to_motor_off_s"]
                + values["energy_time_reserve_s"])
    return {
        "status": "CONDITIONAL_ARITHMETIC_ONLY",
        "source_sha": source,
        "ast_sha256": ast,
        "abort_motion_allowance_m": travel,
        "conditional_horizontal_margin_m": values["distance_to_hazard_m"] - occupied,
        "conditional_endurance_margin_s": values["endurance_lower_bound_s"] - duration,
        "flight_authorized": False,
        "physical_qualification": "UNPROVEN",
        "warning": "Inputs are not physically attested; cannot infer safe flight, landing, or battery endurance.",
    }

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: conditional_flight_budget.py <offline-sheet.json>", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"),
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
