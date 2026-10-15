#!/usr/bin/env python3
"""Machine-only falsification: no flight authority or physical evidence implied."""
from __future__ import annotations

import copy
from decimal import Decimal
from fractions import Fraction
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
    extreme = copy.deepcopy(baseline)
    extreme["bounds"]["max_hazard_approach_speed_m_s"]["value"] = 1e308
    rejected(extreme)  # Derived v^2 overflows; no positive result.
    extreme = copy.deepcopy(baseline)
    extreme["bounds"]["distance_to_hazard_m"]["value"] = 10 ** 1000
    rejected(extreme)  # Huge integers cannot be finite measured bounds.
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



def test_cli_publishes_conservative_exact_decimal_tokens():
    # Three independent serialization NO_GO witnesses from reviewer of dd96dac.
    # All source IDs, values and evidence digests below are SYNTHETIC.
    reviewer = {
        "distance_to_hazard_m": "0.499999999999999992",
        "prior_horizontal_excursion_m": "0",
        "rotor_radius_m": "0.1",
        "geometry_uncertainty_m": "0",
        "max_hazard_approach_speed_m_s": "0.2",
        "max_abort_to_deceleration_s": "0.10000000000000001",
        "min_supported_deceleration_m_s2": "0.25",
        "endurance_lower_bound_s": "70.29999999999999999",
        "max_planned_motor_time_s": "40",
        "max_abort_to_motor_off_s": "10",
        "energy_time_reserve_s": "20",
    }
    def exact_result(numbers):
        # Independent rational oracle from the original decimal input tokens.
        v = {key: Fraction(Decimal(spelling)) for key, spelling in numbers.items()}
        travel = (v["max_hazard_approach_speed_m_s"] * v["max_abort_to_deceleration_s"]
                  + v["max_hazard_approach_speed_m_s"] ** 2
                  / (2 * v["min_supported_deceleration_m_s2"]))
        return {
            "abort_motion_allowance_m": travel,
            "conditional_horizontal_margin_m": (
                v["distance_to_hazard_m"] - v["prior_horizontal_excursion_m"]
                - v["rotor_radius_m"] - v["geometry_uncertainty_m"] - travel),
            "conditional_endurance_margin_s": (
                v["endurance_lower_bound_s"] - v["max_planned_motor_time_s"]
                - v["max_abort_to_motor_off_s"] - v["energy_time_reserve_s"]),
        }

    def numeric_json(numbers):
        # Keep every input spelling as a literal JSON NUMBER (not quoted,
        # not converted to Python float, and not rounded by json.dumps).
        return ('{"source_sha":"' + "a" * 40 + '","ast_sha256":"' + "b" * 64
                + '","bounds":{' + ",".join(
                    json.dumps(name) + ':{"value":' + spelling
                    + ',"evidence_sha256":"' + "c" * 64 + '"}'
                    for name, spelling in numbers.items()) + '}}')

    expected_reviewer = exact_result(reviewer)
    require(expected_reviewer == {
        "abort_motion_allowance_m": Fraction(Decimal("0.100000000000000002")),
        "conditional_horizontal_margin_m": Fraction(Decimal("0.29999999999999999")),
        "conditional_endurance_margin_s": Fraction(Decimal("0.29999999999999999")),
    }, "reviewer decimal counterexample incorrectly reconstructed")
    raw = numeric_json(reviewer)
    # Explicitly reproduce the defect without restoring the buggy production
    # serializer: binary outward floats are safe, shortest JSON decimals are not.
    baseline = evaluate(json.loads(raw, parse_float=Decimal))
    legacy = json.loads(json.dumps(baseline), parse_float=Decimal, parse_int=Decimal)
    require(Fraction(legacy["abort_motion_allowance_m"])
            < expected_reviewer["abort_motion_allowance_m"],
            "old CLI travel underestimation witness not reproduced")
    for field in ("conditional_horizontal_margin_m", "conditional_endurance_margin_s"):
        require(Fraction(legacy[field]) > expected_reviewer[field],
                "old CLI margin overestimation witness not reproduced: " + field)

    cases = [reviewer]
    # Also exercise the exact zero crossing from both sides in the emitted CLI,
    # not only in evaluate()'s existing direct-float tests.
    for delta in ("-0.00000000000000001", "0", "0.00000000000000001"):
        numbers = dict(reviewer)
        numbers.update({
            "distance_to_hazard_m": str(Decimal("0.1") + Decimal(delta)),
            "max_hazard_approach_speed_m_s": "0",
            "prior_horizontal_excursion_m": "0",
            "rotor_radius_m": "0.1",
            "geometry_uncertainty_m": "0",
            "endurance_lower_bound_s": str(Decimal("70") + Decimal(delta)),
        })
        cases.append(numbers)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "exact-decimal-bounds.json"
        for numbers in cases:
            raw = numeric_json(numbers)
            path.write_text(raw, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(PHYSICAL / "conditional_flight_budget.py"), str(path)],
                capture_output=True, text=True, timeout=5)
            require(proc.returncode == 0, proc.stderr + proc.stdout)
            emitted = json.loads(proc.stdout, parse_float=Decimal, parse_int=Decimal)
            evaluated = evaluate(json.loads(raw, parse_float=Decimal))
            exact = exact_result(numbers)
            require(emitted["flight_authorized"] is False
                    and emitted["physical_qualification"] == "UNPROVEN"
                    and emitted["status"] == "CONDITIONAL_ARITHMETIC_ONLY",
                    "published decimal margins conferred authority")
            for field, rational in exact.items():
                published = emitted[field]
                require(type(published) is Decimal,
                        "directed field must be a numeric JSON token: " + field)
                require((Fraction(published) >= rational
                         if field == "abort_motion_allowance_m"
                         else Fraction(published) <= rational),
                        "optimistic DECIMAL JSON field: " + field + ", " + str(published))
                require(Fraction(published) == Fraction.from_float(evaluated[field]),
                        "JSON lost the exact outward-rounded binary value: " + field)


def test_reviewer_refutations_and_exact_signs():
    # Original NO_GO reproducer: naive floats returned +5.55e-17 metres
    # even though the written decimal bounds imply a NEGATIVE margin.
    sheet = synthetic_sheet()
    boundary = {
        "distance_to_hazard_m": "0.46367642549844795",
        "prior_horizontal_excursion_m": "0.2856287821675341",
        "rotor_radius_m": "0.06425789127078527",
        "geometry_uncertainty_m": "0.04178785698518531",
        "max_hazard_approach_speed_m_s": "0.20120745675755597",
        "max_abort_to_deceleration_s": "0.22940304678469947",
        "min_supported_deceleration_m_s2": "0.7832375810947076",
    }
    for name, spelling in boundary.items():
        sheet["bounds"][name]["value"] = Decimal(spelling)
    result = evaluate(sheet)
    require(result["conditional_horizontal_margin_m"] < 0
            and result["flight_authorized"] is False, result)
    # Second independent signed boundary: binary addition used to erase
    # the strictly negative 1e-17 second endurance margin.
    for name, spelling in (
        ("endurance_lower_bound_s", "1"),
        ("max_planned_motor_time_s", "0.9"),
        ("max_abort_to_motor_off_s", "0.1"),
        ("energy_time_reserve_s", "0.00000000000000001"),
    ):
        sheet["bounds"][name]["value"] = Decimal(spelling)
    require(evaluate(sheet)["conditional_endurance_margin_s"] < 0,
            "near-zero energy deficit disappeared")
    for name, spelling in boundary.items():
        sheet["bounds"][name]["value"] = float(spelling)
    require(evaluate(sheet)["conditional_horizontal_margin_m"] < 0,
            "direct Python float caller inverted the given decimal sign")

    # Exact negative/zero/positive margins. Outward conversion must never
    # overstate either margin or turn zero/negative into positive.
    sheet = synthetic_sheet()
    for name, spelling in (
        ("max_hazard_approach_speed_m_s", "0"),
        ("prior_horizontal_excursion_m", "0.1"),
        ("rotor_radius_m", "0.1"),
        ("geometry_uncertainty_m", "0"),
        ("max_planned_motor_time_s", "40"),
        ("max_abort_to_motor_off_s", "10"),
        ("energy_time_reserve_s", "20"),
    ):
        sheet["bounds"][name]["value"] = Decimal(spelling)
    for delta in ("-0.00000000000000001", "0", "+0.00000000000000001"):
        exact = Fraction(Decimal(delta))
        sheet["bounds"]["distance_to_hazard_m"]["value"] = Decimal("0.2") + Decimal(delta)
        sheet["bounds"]["endurance_lower_bound_s"]["value"] = Decimal("70") + Decimal(delta)
        result = evaluate(sheet)
        for field in ("conditional_horizontal_margin_m", "conditional_endurance_margin_s"):
            reported = Fraction.from_float(result[field])
            require(reported <= exact and (result[field] < 0) == (exact < 0)
                    and not (result[field] > 0 and exact <= 0), (field, delta, result))
    sheet = synthetic_sheet()
    sheet["bounds"]["max_hazard_approach_speed_m_s"]["value"] = Decimal("1")
    sheet["bounds"]["max_abort_to_deceleration_s"]["value"] = Decimal("0")
    sheet["bounds"]["min_supported_deceleration_m_s2"]["value"] = Decimal("3")
    require(Fraction.from_float(evaluate(sheet)["abort_motion_allowance_m"]) >= Fraction(1, 6),
            "abort allowance may not round BELOW exact travel")
    for name, value in (
        ("min_supported_deceleration_m_s2", Decimal("1e-320")),
        ("max_hazard_approach_speed_m_s", Decimal("1e308")),
        ("endurance_lower_bound_s", Decimal("1e1000")),
        ("geometry_uncertainty_m", Decimal("1e-1000")),
    ):
        adverse = synthetic_sheet()
        adverse["bounds"][name]["value"] = value
        rejected(adverse)
    adverse = synthetic_sheet()
    adverse["bounds"]["endurance_lower_bound_s"]["value"] = Decimal("1e-323")
    require(evaluate(adverse)["conditional_endurance_margin_s"] < 0,
            "tiny finite lower endurance hides a motor-time deficit")

def test_direct_float_inputs_keep_their_binary_bounds():
    # Decimal(str(x)) silently erases BOTH strictly negative binary-float
    # margins here (0.3 - 0.1 - 0.2), unlike Decimal.from_float(x).
    sheet = synthetic_sheet()
    for name, value in (
        ("distance_to_hazard_m", 0.3),
        ("prior_horizontal_excursion_m", 0.1),
        ("rotor_radius_m", 0.2),
        ("geometry_uncertainty_m", 0.0),
        ("max_hazard_approach_speed_m_s", 0.0),
        ("max_abort_to_deceleration_s", 0.0),
        ("endurance_lower_bound_s", 0.3),
        ("max_planned_motor_time_s", 0.1),
        ("max_abort_to_motor_off_s", 0.2),
        ("energy_time_reserve_s", 0.0),
    ):
        sheet["bounds"][name]["value"] = value
    exact = Fraction(0.3) - Fraction(0.1) - Fraction(0.2)
    require(exact < 0, "synthetic float counterexample changed")
    output = evaluate(sheet)
    for field in ("conditional_horizontal_margin_m", "conditional_endurance_margin_s"):
        actual = output[field]
        require(actual < 0 and Fraction.from_float(actual) <= exact,
                "optimistic binary-float reinterpretation: " + field)
    require(output["physical_qualification"] == "UNPROVEN"
            and output["flight_authorized"] is False, "float inputs conferred authority")
    wrong_unit = synthetic_sheet()
    wrong_unit["bounds"]["distance_to_hazard_m"]["unit"] = "cm"
    rejected(wrong_unit)  # Units are a strict external contract, not auto-converted.
    wrong_unit = synthetic_sheet()
    wrong_unit["bounds"]["distance_to_hazard_m"]["value"] = "200 cm"
    rejected(wrong_unit)
    fake_origin = synthetic_sheet()
    fake_origin["source_sha"] = "f" * 40
    fake_origin["ast_sha256"] = "e" * 64
    fake_origin["bounds"]["distance_to_hazard_m"]["evidence_sha256"] = "d" * 64
    conditional = evaluate(fake_origin)
    require(conditional["status"] == "CONDITIONAL_ARITHMETIC_ONLY"
            and conditional["physical_qualification"] == "UNPROVEN"
            and conditional["flight_authorized"] is False,
            "syntactically valid invented digests were treated as authentic evidence")


def test_duplicate_json_keys_fail_closed_at_every_depth():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "adversarial.json"
        original = json.dumps(synthetic_sheet())
        cases = (
            original.replace('"source_sha":', '"source_sha": "' + "d" * 40 + '", "source_sha":', 1),
            original.replace('"ast_sha256":', '"ast_sha256": "' + "d" * 64 + '", "ast_sha256":', 1),
            original.replace('"bounds":', '"bounds": {}, "bounds":', 1),
            original.replace('"endurance_lower_bound_s": {',
                             '"endurance_lower_bound_s": {}, "endurance_lower_bound_s": {', 1),
            original.replace('"endurance_lower_bound_s": {"value": 120.0',
                             '"endurance_lower_bound_s": {"value": 1, "value": 120.0', 1),
            original.replace('"endurance_lower_bound_s": {"value": 120.0',
                             '"endurance_lower_bound_s": {"\\u0076alue": 1, "value": 120.0', 1),
            original.replace('"endurance_lower_bound_s": {"value": 120.0',
                             '"endurance_lower_bound_s": {"value": 120.0, "value": 120.0', 1),
        )
        for raw in cases:
            path.write_text(raw, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(PHYSICAL / "conditional_flight_budget.py"),
                                   str(path)], capture_output=True, text=True, timeout=5)
            output = json.loads(proc.stdout)
            require(proc.returncode == 2 and output["status"] == "INCOMPLETE"
                    and output["flight_authorized"] is False
                    and output["physical_qualification"] == "UNPROVEN"
                    and "duplicate JSON key" in output["error"],
                    "duplicate JSON key silently accepted: " + raw)
        raw = original.replace("120.0", "70.00000000000000001")
        path.write_text(raw, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(PHYSICAL / "conditional_flight_budget.py"),
                               str(path)], capture_output=True, text=True, timeout=5)
        output = json.loads(proc.stdout)
        require(proc.returncode == 0 and output["conditional_endurance_margin_s"] > 0,
                "JSON parse rounded away a narrow positive decimal margin")
        path.write_text(original.replace("120.0", "1e1000"), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(PHYSICAL / "conditional_flight_budget.py"),
                               str(path)], capture_output=True, text=True, timeout=5)
        require(proc.returncode == 2
                and json.loads(proc.stdout)["status"] == "INCOMPLETE",
                "unrepresentable decimal exponent yielded a complete budget")

def main():
    test_conditional_arithmetic_and_no_authority()
    test_missing_or_unattested_bounds_fail_closed()
    test_offline_cli_does_not_claim_authority()
    test_cli_publishes_conservative_exact_decimal_tokens()
    test_reviewer_refutations_and_exact_signs()
    test_direct_float_inputs_keep_their_binary_bounds()
    test_duplicate_json_keys_fail_closed_at_every_depth()
    print("PASS #157 synthetic budgets: exact conservative boundaries, duplicate-key rejection, provenance form, extremes, and no physical authority")

if __name__ == "__main__":
    main()
