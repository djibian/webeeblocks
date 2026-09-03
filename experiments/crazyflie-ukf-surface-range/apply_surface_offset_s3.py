#!/usr/bin/env python3
"""Reconstruct WebeeBlocks #70 S3 Lab prototype on Crazyflie firmware 2026.08.

This is a fail-closed experimental applicator, not flight-ready firmware.

Target:
  bitcraze/crazyflie-firmware tag 2026.08
  commit 54f31e243a0b28b67efef5ba20dbb6d9890a5478
  src/modules/src/estimator/estimator_ukf.c blob
  57c0e8405c07b63a29538019895ed17d0a379440

Purpose:
- preserve the previously physically proven local down-range path for optical-flow scale;
- add one piecewise-constant surfaceOffset outside the UKF covariance;
- infer candidate terrain-step magnitude from latched local range, never from drifting world Z;
- veto terrain commits using true-vertical-motion evidence (vertical velocity and raw relative barometer);
- require the candidate-corrected ToF innovation to pass the unchanged UKF gate before commit;
- expose direct logs for S3-A terrain and S3-B/S3-C vertical-motion controls.

The experiment is disabled by default.  No PID/controller, Runtime v2, rangeUp,
UKF dimension, ToF gate, or barometer weighting is changed.

Usage from an exact clean crazyflie-firmware 2026.08 checkout:
  python3 /path/to/apply_surface_offset_s3.py --check
  python3 /path/to/apply_surface_offset_s3.py
  git diff --check
  make cf2_defconfig
  # enable CONFIG_ESTIMATOR_UKF_ENABLE=y, then build with the official toolchain

Before any physical S3 trace:
- props removed;
- ukf.qualityGateTof=20 and ukf.baroNoise=6.25 (preserved pre-registered matrix);
- ukf.surfaceOffsetS3=1;
- stationary calibration >=10 s;
- no threshold sweep against S3-A outcome;
- run S3-A terrain, S3-B fast true vertical motion, and S3-C slow true vertical motion.
No motorized flight is authorized by this artifact.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
EXPECTED_BLOB = "57c0e8405c07b63a29538019895ed17d0a379440"
TARGET = Path("src/modules/src/estimator/estimator_ukf.c")


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def require_exact_upstream() -> None:
    if not TARGET.is_file():
        raise SystemExit(f"missing target: {TARGET}")
    head = git("rev-parse", "HEAD")
    if head != EXPECTED_COMMIT:
        raise SystemExit(
            f"wrong upstream commit: expected {EXPECTED_COMMIT}, found {head}; no file written"
        )
    blob = git("hash-object", str(TARGET))
    if blob != EXPECTED_BLOB:
        raise SystemExit(
            f"wrong estimator blob: expected {EXPECTED_BLOB}, found {blob}; no file written"
        )
    status = git("status", "--porcelain", "--", str(TARGET))
    if status:
        raise SystemExit(f"target is not clean ({status}); no file written")


def transform(original: str) -> str:
    text = original

    def replace_once(old: str, new: str, label: str) -> None:
        nonlocal text
        count = text.count(old)
        if count != 1:
            raise SystemExit(
                f"{label}: expected exactly one upstream match, found {count}; no file written"
            )
        text = text.replace(old, new, 1)

    replace_once(
        "static bool isInit = false;\n"
        "static bool flowActive = true;\n"
        "static Axis3f accAccumulator;",
        "static bool isInit = false;\n"
        "static bool flowActive = true;\n"
        "// WebeeBlocks #70 S3 Lab prototype. Disabled by default.\n"
        "// A fresh raw down-range may scale Flow without becoming a world-Z update.\n"
        "static uint8_t surfaceRangeFlow = 0;\n"
        "static float localSurfaceRange = 0.0f;\n"
        "static uint32_t localSurfaceRangeTimeMs = 0;\n"
        "static uint8_t localSurfaceRangeValid = 0;\n"
        "static uint8_t flowLocalActive = 0;\n"
        "static float flowRangeScale = 0.0f;\n"
        "\n"
        "// S3 adds one external piecewise-constant terrain offset; it is not a UKF state.\n"
        "static uint8_t surfaceOffsetS3 = 0;\n"
        "static float surfaceOffset = 0.0f;\n"
        "static float surfaceCandidate = 0.0f;\n"
        "static float surfaceClearance = 0.0f;\n"
        "static float surfaceBaselineClearance = 0.0f;\n"
        "static float latestRelativeBaro = 0.0f;\n"
        "static float surfaceBaroAtSuspect = 0.0f;\n"
        "static float surfaceBaroDelta = 0.0f;\n"
        "static float surfaceCandidateInno = 0.0f;\n"
        "static uint32_t surfaceSuspectStartMs = 0;\n"
        "static uint8_t surfaceDetectorState = 0;\n"
        "static uint8_t surfaceDetectorReason = 0;\n"
        "\n"
        "// Pre-registered Lab constants. Do not tune them against S3-A terrain outcome.\n"
        "#define FLOW_LOCAL_RANGE_MIN_M 0.03f\n"
        "#define FLOW_LOCAL_RANGE_MAX_AGE_MS 100U\n"
        "#define S3_SUSPECT_MIN_MS 2500U\n"
        "#define S3_STEP_MIN_M 0.08f\n"
        "#define S3_STEP_MAX_M 0.35f\n"
        "#define S3_BARO_VERTICAL_VETO_M 0.08f\n"
        "#define S3_VZ_VERTICAL_VETO_MPS 0.08f\n"
        "\n"
        "enum {\n"
        "  S3_STATE_NORMAL = 0,\n"
        "  S3_STATE_SUSPECT = 1,\n"
        "};\n"
        "enum {\n"
        "  S3_REASON_NONE = 0,\n"
        "  S3_REASON_TOF_REJECT = 1,\n"
        "  S3_REASON_WAIT = 2,\n"
        "  S3_REASON_VERTICAL_VETO = 3,\n"
        "  S3_REASON_COMMIT = 4,\n"
        "  S3_REASON_CANDIDATE_REJECT = 5,\n"
        "};\n"
        "static Axis3f accAccumulator;",
        "S3 experiment state",
    )

    reset_body = (
        "  localSurfaceRange = 0.0f;\n"
        "  localSurfaceRangeTimeMs = 0;\n"
        "  localSurfaceRangeValid = 0;\n"
        "  flowLocalActive = 0;\n"
        "  flowRangeScale = 0.0f;\n"
        "  surfaceOffset = 0.0f;\n"
        "  surfaceCandidate = 0.0f;\n"
        "  surfaceClearance = 0.0f;\n"
        "  surfaceBaselineClearance = 0.0f;\n"
        "  latestRelativeBaro = 0.0f;\n"
        "  surfaceBaroAtSuspect = 0.0f;\n"
        "  surfaceBaroDelta = 0.0f;\n"
        "  surfaceCandidateInno = 0.0f;\n"
        "  surfaceSuspectStartMs = 0;\n"
        "  surfaceDetectorState = S3_STATE_NORMAL;\n"
        "  surfaceDetectorReason = S3_REASON_NONE;\n"
    )
    bias_reset = "".join("      " + line if line else line for line in reset_body.splitlines(True))
    replace_once(
        "      flowActive = true;\n\n"
        "      // set initial parameters",
        "      flowActive = true;\n"
        + bias_reset
        + "\n"
        "      // set initial parameters",
        "bias-initialization reset",
    )
    replace_once(
        "  flowActive = true;\n\n"
        "  // set initial parameters",
        "  flowActive = true;\n"
        + reset_body
        + "\n"
        "  // set initial parameters",
        "navigation reset",
    )

    replace_once(
        "        case MeasurementTypeTOF:\n"
        "          //_________________________________________________________________________________\n"
        "          // UKF update - TOF\n"
        "          //_________________________________________________________________________________\n"
        "          if ((fabs(dcm[2][2]) > 0.1) && (dcm[2][2] > 0.0f))\n"
        "          {\n"
        "            // compute mean tdoa observation",
        "        case MeasurementTypeTOF:\n"
        "          //_________________________________________________________________________________\n"
        "          // UKF update - TOF\n"
        "          //_________________________________________________________________________________\n"
        "          if ((fabs(dcm[2][2]) > 0.1) && (dcm[2][2] > 0.0f))\n"
        "          {\n"
        "            // Capture local surface geometry before deciding whether ToF is a world-Z update.\n"
        "            if (m.data.tof.distance >= FLOW_LOCAL_RANGE_MIN_M)\n"
        "            {\n"
        "              localSurfaceRange = m.data.tof.distance;\n"
        "              localSurfaceRangeTimeMs = nowMs;\n"
        "              localSurfaceRangeValid = 1;\n"
        "              surfaceClearance = m.data.tof.distance * dcm[2][2];\n"
        "            }\n"
        "            else\n"
        "            {\n"
        "              localSurfaceRangeValid = 0;\n"
        "            }\n"
        "\n"
        "            // compute mean tdoa observation",
        "ToF local-range capture",
    )

    replace_once(
        "            // if an outlier is detected, flowActive flag prevents fusing optical flow too\n"
        "            if (innoCheck < qualGateTof)\n"
        "            {\n"
        "              ukfUpdate(&Pxy[0], &Pyy, innovation);\n"
        "              flowActive = true;\n"
        "            }\n"
        "            else\n"
        "            {\n"
        "              flowActive = false;\n"
        "            }",
        "            // Stock behavior is preserved unless an explicit Lab mode is enabled.\n"
        "            const bool localFlowMode = (surfaceRangeFlow != 0) || (surfaceOffsetS3 != 0);\n"
        "            if (innoCheck < qualGateTof)\n"
        "            {\n"
        "              ukfUpdate(&Pxy[0], &Pyy, innovation);\n"
        "              flowActive = true;\n"
        "              if (surfaceOffsetS3 && localSurfaceRangeValid)\n"
        "              {\n"
        "                surfaceBaselineClearance = surfaceClearance;\n"
        "                surfaceCandidate = surfaceOffset;\n"
        "                surfaceBaroDelta = 0.0f;\n"
        "                surfaceCandidateInno = innoCheck;\n"
        "                surfaceDetectorState = S3_STATE_NORMAL;\n"
        "                surfaceDetectorReason = S3_REASON_NONE;\n"
        "              }\n"
        "            }\n"
        "            else if (surfaceOffsetS3 && localSurfaceRangeValid)\n"
        "            {\n"
        "              // Infer terrain magnitude only from the latched local-clearance step.\n"
        "              if (surfaceDetectorState == S3_STATE_NORMAL)\n"
        "              {\n"
        "                surfaceDetectorState = S3_STATE_SUSPECT;\n"
        "                surfaceDetectorReason = S3_REASON_TOF_REJECT;\n"
        "                surfaceSuspectStartMs = nowMs;\n"
        "                surfaceBaroAtSuspect = latestRelativeBaro;\n"
        "              }\n"
        "\n"
        "              const float deltaSurface = surfaceBaselineClearance - surfaceClearance;\n"
        "              surfaceCandidate = surfaceOffset + deltaSurface;\n"
        "              surfaceBaroDelta = latestRelativeBaro - surfaceBaroAtSuspect;\n"
        "              const uint32_t suspectAgeMs = nowMs - surfaceSuspectStartMs;\n"
        "              const bool plausibleStep = fabsf(deltaSurface) >= S3_STEP_MIN_M &&\n"
        "                fabsf(deltaSurface) <= S3_STEP_MAX_M;\n"
        "              const bool verticalVeto = fabsf(stateNav[5]) >= S3_VZ_VERTICAL_VETO_MPS ||\n"
        "                fabsf(surfaceBaroDelta) >= S3_BARO_VERTICAL_VETO_M;\n"
        "\n"
        "              // A constant offset shifts the predicted ToF mean but not its covariance.\n"
        "              const float candidateObservation = observation - (deltaSurface / dcm[2][2]);\n"
        "              const float candidateInnovation = m.data.tof.distance - candidateObservation;\n"
        "              surfaceCandidateInno = candidateInnovation * candidateInnovation / Pyy;\n"
        "\n"
        "              if (verticalVeto)\n"
        "              {\n"
        "                surfaceDetectorReason = S3_REASON_VERTICAL_VETO;\n"
        "              }\n"
        "              else if (suspectAgeMs < S3_SUSPECT_MIN_MS)\n"
        "              {\n"
        "                surfaceDetectorReason = S3_REASON_WAIT;\n"
        "              }\n"
        "              else if (plausibleStep && surfaceCandidateInno < qualGateTof)\n"
        "              {\n"
        "                surfaceOffset = surfaceCandidate;\n"
        "                ukfUpdate(&Pxy[0], &Pyy, candidateInnovation);\n"
        "                flowActive = true;\n"
        "                surfaceBaselineClearance = surfaceClearance;\n"
        "                surfaceDetectorState = S3_STATE_NORMAL;\n"
        "                surfaceDetectorReason = S3_REASON_COMMIT;\n"
        "              }\n"
        "              else\n"
        "              {\n"
        "                surfaceDetectorReason = S3_REASON_CANDIDATE_REJECT;\n"
        "              }\n"
        "\n"
        "              // Keep raw local range available for Flow even while ToF-as-Z is rejected.\n"
        "              if (!localFlowMode)\n"
        "              {\n"
        "                flowActive = false;\n"
        "              }\n"
        "            }\n"
        "            else\n"
        "            {\n"
        "              flowActive = false;\n"
        "            }",
        "ToF gate and S3 classifier",
    )

    replace_once(
        "        case MeasurementTypeFlow:\n\n"
        "          if (flowActive)\n"
        "          {",
        "        case MeasurementTypeFlow:\n"
        "        {\n"
        "          const bool localFlowMode = (surfaceRangeFlow != 0) || (surfaceOffsetS3 != 0);\n"
        "          const bool localRangeFresh = localSurfaceRangeValid &&\n"
        "            ((nowMs - localSurfaceRangeTimeMs) <= FLOW_LOCAL_RANGE_MAX_AGE_MS);\n"
        "          flowLocalActive = (localFlowMode && localRangeFresh) ? 1 : 0;\n"
        "          const bool processFlow = localFlowMode ? (flowLocalActive != 0) : flowActive;\n"
        "\n"
        "          if (localFlowMode)\n"
        "          {\n"
        "            flowRangeScale = localRangeFresh ? localSurfaceRange : 0.0f;\n"
        "          }\n"
        "          else if (fabsf(dcm[2][2]) > 0.1f)\n"
        "          {\n"
        "            flowRangeScale = stateNav[2] / dcm[2][2];\n"
        "          }\n"
        "          else\n"
        "          {\n"
        "            flowRangeScale = 0.0f;\n"
        "          }\n"
        "\n"
        "          if (processFlow)\n"
        "          {",
        "Flow gating split",
    )
    replace_once(
        "          }\n"
        "          break;\n"
        "        case MeasurementTypeBarometer:",
        "          }\n"
        "          break;\n"
        "        }\n"
        "        case MeasurementTypeBarometer:",
        "Flow case scope",
    )

    replace_once(
        "        case MeasurementTypeBarometer:\n"
        "          //_________________________________________________________________________________\n"
        "          // UKF update - Baro",
        "        case MeasurementTypeBarometer:\n"
        "          latestRelativeBaro = m.data.barometer.baro.asl - baroAslBias;\n"
        "          //_________________________________________________________________________________\n"
        "          // UKF update - Baro",
        "raw relative barometer capture",
    )

    replace_once(
        "static void computeOutputTof(float *output, float *state)\n"
        "{\n"
        "  output[0] = (stateNav[2] + state[2]) / dcm[2][2];\n"
        "}",
        "static void computeOutputTof(float *output, float *state)\n"
        "{\n"
        "  const float localWorldZ = (stateNav[2] + state[2]) - (surfaceOffsetS3 ? surfaceOffset : 0.0f);\n"
        "  output[0] = localWorldZ / dcm[2][2];\n"
        "}",
        "ToF surface-offset model",
    )

    replace_once(
        "  if (stateNav[2] < 0.1f)\n"
        "  {\n"
        "    h_g = 0.1f;\n"
        "  }\n"
        "  else\n"
        "  {\n"
        "    h_g = stateNav[2] + state[2];\n"
        "  }\n\n"
        "  output[0] = (flow->dt * Npix / thetapix) * ((velocityBody_x / h_g * dcm[2][2]) - omegaFactor * omegaBody->y);",
        "  const bool localFlowMode = (surfaceRangeFlow != 0) || (surfaceOffsetS3 != 0);\n"
        "  if (localFlowMode && flowLocalActive)\n"
        "  {\n"
        "    h_g = fmaxf(localSurfaceRange, 0.1f);\n"
        "  }\n"
        "  else if (stateNav[2] < 0.1f)\n"
        "  {\n"
        "    h_g = 0.1f;\n"
        "  }\n"
        "  else\n"
        "  {\n"
        "    h_g = stateNav[2] + state[2];\n"
        "  }\n\n"
        "  const float translation = (localFlowMode && flowLocalActive)\n"
        "    ? (velocityBody_x / h_g)\n"
        "    : (velocityBody_x / h_g * dcm[2][2]);\n"
        "  output[0] = (flow->dt * Npix / thetapix) * (translation - omegaFactor * omegaBody->y);",
        "Flow X local scale",
    )

    replace_once(
        "  if (stateNav[2] < 0.1f)\n"
        "  {\n"
        "    h_g = 0.1f;\n"
        "  }\n"
        "  else\n"
        "  {\n"
        "    h_g = stateNav[2] + state[2];\n"
        "  }\n\n"
        "  output[0] = (flow->dt * Npix / thetapix) * ((velocityBody_y / h_g * dcm[2][2]) + omegaFactor * omegaBody->x);",
        "  const bool localFlowMode = (surfaceRangeFlow != 0) || (surfaceOffsetS3 != 0);\n"
        "  if (localFlowMode && flowLocalActive)\n"
        "  {\n"
        "    h_g = fmaxf(localSurfaceRange, 0.1f);\n"
        "  }\n"
        "  else if (stateNav[2] < 0.1f)\n"
        "  {\n"
        "    h_g = 0.1f;\n"
        "  }\n"
        "  else\n"
        "  {\n"
        "    h_g = stateNav[2] + state[2];\n"
        "  }\n\n"
        "  const float translation = (localFlowMode && flowLocalActive)\n"
        "    ? (velocityBody_y / h_g)\n"
        "    : (velocityBody_y / h_g * dcm[2][2]);\n"
        "  output[0] = (flow->dt * Npix / thetapix) * (translation + omegaFactor * omegaBody->x);",
        "Flow Y local scale",
    )

    replace_once(
        "LOG_ADD(LOG_FLOAT, innoChTof, &innoCheckTof)\n"
        "LOG_ADD(LOG_FLOAT, distTWR, &distanceTWR)\n"
        "LOG_GROUP_STOP(sensorFilter)",
        "LOG_ADD(LOG_FLOAT, innoChTof, &innoCheckTof)\n"
        "LOG_ADD(LOG_FLOAT, distTWR, &distanceTWR)\n"
        "// WebeeBlocks #70 S3 direct observability.\n"
        "LOG_ADD(LOG_FLOAT, flowRange, &flowRangeScale)\n"
        "LOG_ADD(LOG_UINT8, flowLocal, &flowLocalActive)\n"
        "LOG_ADD(LOG_FLOAT, surfOffset, &surfaceOffset)\n"
        "LOG_ADD(LOG_FLOAT, surfCand, &surfaceCandidate)\n"
        "LOG_ADD(LOG_FLOAT, surfClear, &surfaceClearance)\n"
        "LOG_ADD(LOG_FLOAT, surfBaroD, &surfaceBaroDelta)\n"
        "LOG_ADD(LOG_FLOAT, surfCandInn, &surfaceCandidateInno)\n"
        "LOG_ADD(LOG_UINT8, surfState, &surfaceDetectorState)\n"
        "LOG_ADD(LOG_UINT8, surfReason, &surfaceDetectorReason)\n"
        "LOG_GROUP_STOP(sensorFilter)",
        "S3 logs",
    )

    replace_once(
        "PARAM_ADD(PARAM_FLOAT, baroNoise, &measNoiseBaro)\n"
        "PARAM_ADD(PARAM_FLOAT, qualityGateTof, &qualGateTof)\n"
        "PARAM_ADD(PARAM_FLOAT, qualityGateFlow, &qualGateFlow)",
        "PARAM_ADD(PARAM_FLOAT, baroNoise, &measNoiseBaro)\n"
        "PARAM_ADD(PARAM_FLOAT, qualityGateTof, &qualGateTof)\n"
        "// WebeeBlocks #70 Lab modes. Defaults preserve stock behavior.\n"
        "PARAM_ADD(PARAM_UINT8, surfaceRangeFlow, &surfaceRangeFlow)\n"
        "PARAM_ADD(PARAM_UINT8, surfaceOffsetS3, &surfaceOffsetS3)\n"
        "PARAM_ADD(PARAM_FLOAT, qualityGateFlow, &qualGateFlow)",
        "S3 parameters",
    )

    if text == original:
        raise SystemExit("no changes produced")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate exact upstream and all anchors, but do not write",
    )
    args = parser.parse_args()

    require_exact_upstream()
    original = TARGET.read_text(encoding="utf-8")
    patched = transform(original)

    if args.check:
        print("CHECKED: exact 2026.08 commit/blob and every S3 anchor matched once")
        return

    TARGET.write_text(patched, encoding="utf-8")
    print(f"APPLIED: {TARGET}")
    print("Lab parameters: ukf.surfaceRangeFlow, ukf.surfaceOffsetS3")
    print(
        "Lab logs: sensorFilter.flowRange/flowLocal/surfOffset/surfCand/"
        "surfClear/surfBaroD/surfCandInn/surfState/surfReason"
    )
    print("NO FLIGHT AUTHORITY: validate build, then props-off S3-A/S3-B/S3-C only")


if __name__ == "__main__":
    main()
