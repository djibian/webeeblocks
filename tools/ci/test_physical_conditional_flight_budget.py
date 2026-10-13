#!/usr/bin/env python3
"""Machine-only falsification: no flight authority or physical evidence implied."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))
from conditional_flight_budget import BOUNDS, EvidenceError, evaluate  # noqa: E402

def require(value, message):
    if not value:
        raise AssertionError(message)

def synthetic_sheet():
    # Every digest/value in this test is SYNTHETIC, not a real measurement.
    numbers = {
        "distance_to_hazard_m": 2.0,
        "prior_horizontal_excursion_m": 0.2,
        "rotor_radius_m": 0.1,
        "geometry_uncertainty_m": 0.05,
        "max_hazard_approach_speed_m_s": 0.4,
        "max_abort_to_deceleration_s": 0.3,
        "min_supported_deceleration_m_s2": 0.8,
        "endurance_lower_bound_s": 120.0,
        "max_planned_motor_time_s": 40.0,
        "max_abort_to_motor_off_s": 10.0,
        "energy_time_reserve_s": 20.0,
    }
    return {"source_sha": "a" * 40, "ast_sha256": "b" * 64,
            "bounds": {key: {"value": numbers[key], "evidence_sha256": "c" * 64}
                       for key in BOUNDS}}

def rejected(sheet):
    try:
        evaluate(sheet)
    except EvidenceError:
        return
    raise AssertionError("unsupported or missing evidence was accepted")

def test_conditional_arithmetic_and_no_authority():
    result = evaluate(synthetic_sheet())
    require(result["status"] == "CONDITIONAL_ARITHMETIC_ONLY"
            and result["physical_qualification"] == "UNPROVEN"
            and result["flight_authorized"] is False,
            "pure arithmetic was promoted to physical GO")
    # v L + v^2/(2a) = .12 + .10, never only the software pacing slice.
    require(abs(result["abort_motion_allowance_m"] - .22) < 1e-12, result)
    require(abs(result["conditional_horizontal_margin_m"] - 1.43) < 1e-12, result)
    require(abs(result["conditional_endurance_margin_s"] - 50.0) < 1e-12, result)
    unsafe = synthetic_sheet()
    unsafe["bounds"]["distance_to_hazard_m"]["value"] = 0.3
    unsafe["bounds"]["endurance_lower_bound_s"]["value"] = 60
    verdict = evaluate(unsafe)
    require(verdict["conditional_horizontal_margin_m"] < 0
            and verdict["conditional_endurance_margin_s"] < 0
            and verdict["flight_authorized"] is False,
            "adverse hypothetical margins lost or became a verdict")

def test_missing_or_unattested_bounds_fail_closed():
    baseline = synthetic_sheet()
    for name in BOUNDS:
        modified = copy.deepcopy(baseline)
        del modified["bounds"][name]
        rejected(modified)
        modified = copy.deepcopy(baseline)
        modified["bounds"][name]["evidence_sha256"] = ""
        rejected(modified)
        for value in (None, True, "0.4", float("nan"), float("inf"), -0.1):
            modified = copy.deepcopy(baseline)
            modified["bounds"][name]["value"] = value
            rejected(modified)
    for key in ("source_sha", "ast_sha256"):
        modified = copy.deepcopy(baseline)
        modified[key] = "invalid"
        rejected(modified)
    modified = copy.deepcopy(baseline)
    modified["bounds"]["invented"] = {"value": 0, "evidence_sha256": "c" * 64}
    rejected(modified)
    for key in ("min_supported_deceleration_m_s2", "endurance_lower_bound_s",
                "max_planned_motor_time_s", "max_abort_to_motor_off_s"):
        modified = copy.deepcopy(baseline)
        modified["bounds"][key]["value"] = 0
        rejected(modified)

def test_offline_cli_does_not_claim_authority():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "synthetic.json"
        path.write_text(json.dumps(synthetic_sheet()), encoding="utf-8")
        script = PHYSICAL / "conditional_flight_budget.py"
        proc = subprocess.run([sys.executable, str(script), str(path)], capture_output=True,
                              text=True, timeout=5)
        require(proc.returncode == 0, proc.stderr + proc.stdout)
        output = json.loads(proc.stdout)
        require(output["flight_authorized"] is False
                and output["physical_qualification"] == "UNPROVEN",
                "CLI promoted synthetic numbers to qualification")
        path.write_text('{"source_sha":"bad"}', encoding="utf-8")
        proc = subprocess.run([sys.executable, str(script), str(path)], capture_output=True,
                              text=True, timeout=5)
        require(proc.returncode == 2
                and json.loads(proc.stdout)["status"] == "INCOMPLETE",
                "incomplete evidence yielded a valid candidate")
        path.write_text("not JSON", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(script), str(path)], capture_output=True,
                              text=True, timeout=5)
        require(proc.returncode == 2, "malformed JSON was accepted")

def main():
    test_conditional_arithmetic_and_no_authority()
    test_missing_or_unattested_bounds_fail_closed()
    test_offline_cli_does_not_claim_authority()
    print("PASS #157 synthetic budgets: strict provenance fields, missing/invalid bounds, adverse margins, and no physical authority")

if __name__ == "__main__":
    main()
