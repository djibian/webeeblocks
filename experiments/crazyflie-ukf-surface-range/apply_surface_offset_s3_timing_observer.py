#!/usr/bin/env python3
"""Add queue/sample timing observability to the #70 S3 discriminator candidate.

Apply the existing S3 base applicator and VZ/BARO/BOTH discriminator first on
the exact Crazyflie firmware 2026.08 source. This overlay does not alter the ToF
quality gate, any S3 threshold/persistence constant, the veto predicate, the
surface-offset commit predicate, estimator state, Flow behavior, Runtime v2, or
motor authority.

It records enough provenance to distinguish ToF producer time from UKF
queue-processing time and to identify which already-dequeued barometer/VZ
snapshot the late classifier is using. Observer state is cleared by both S3
navigation reset paths so provenance cannot leak across estimator resets.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
TARGET = Path("src/modules/src/estimator/estimator_ukf.c")

STATE_OLD = """static uint8_t surfaceDetectorState = 0;
static uint8_t surfaceDetectorReason = 0;
"""

STATE_NEW = """static uint8_t surfaceDetectorState = 0;
static uint8_t surfaceDetectorReason = 0;

// X3 timing observer: provenance only; classifier semantics stay unchanged.
static uint32_t surfaceQueueSequence = 0;
static uint32_t surfaceLatestBaroSequence = 0;
static uint32_t surfaceLatestBaroProcessMs = 0;
static uint32_t surfaceTofAgeMs = 0;
static uint32_t surfaceBaroAgeMs = 0;
static uint32_t surfaceBaroLagEvents = 0;
static uint32_t surfaceTofAgeAtSuspectMs = 0;
static uint32_t surfaceBaroAgeAtSuspectMs = 0;
static uint32_t surfaceBaroLagAtSuspect = 0;
static uint32_t surfaceTofAgeAtDecisionMs = 0;
static uint32_t surfaceBaroAgeAtDecisionMs = 0;
static uint32_t surfaceBaroLagAtDecision = 0;
static uint8_t surfaceBaroSeen = 0;
static uint8_t surfaceBaroSeenAtSuspect = 0;
static uint8_t surfaceBaroSeenAtDecision = 0;
static uint8_t surfaceLateDecisionEligible = 0;
static float surfaceVzAtSuspect = 0.0f;
static float surfaceVzAtDecision = 0.0f;
static float surfaceBaroAtDecision = 0.0f;
static float surfaceBaroDeltaAtDecision = 0.0f;
"""

QUEUE_OLD = """  measurement_t m;
  while (estimatorDequeue(&m))
  {

"""

QUEUE_NEW = """  measurement_t m;
  while (estimatorDequeue(&m))
  {
    surfaceQueueSequence++;

"""

TOF_OLD = """            // Capture local surface geometry before deciding whether ToF is a world-Z update.
            if (m.data.tof.distance >= FLOW_LOCAL_RANGE_MIN_M)
"""

TOF_NEW = """            // Capture producer-vs-processing timing before any late classifier decision.
            surfaceTofAgeMs = nowMs - T2M(m.data.tof.timestamp);
            surfaceLateDecisionEligible = 0;
            if (surfaceBaroSeen)
            {
              surfaceBaroAgeMs = nowMs - surfaceLatestBaroProcessMs;
              surfaceBaroLagEvents = surfaceQueueSequence - surfaceLatestBaroSequence;
            }
            else
            {
              surfaceBaroAgeMs = 0;
              surfaceBaroLagEvents = 0;
            }

            // Capture local surface geometry before deciding whether ToF is a world-Z update.
            if (m.data.tof.distance >= FLOW_LOCAL_RANGE_MIN_M)
"""

BARO_OLD = """        case MeasurementTypeBarometer:
          latestRelativeBaro = m.data.barometer.baro.asl - baroAslBias;
"""

BARO_NEW = """        case MeasurementTypeBarometer:
          latestRelativeBaro = m.data.barometer.baro.asl - baroAslBias;
          surfaceLatestBaroSequence = surfaceQueueSequence;
          surfaceLatestBaroProcessMs = nowMs;
          surfaceBaroSeen = 1;
"""

SUSPECT_ENTRY_OLD = """                surfaceBaroAtSuspect = latestRelativeBaro;
                surfaceOffsetBefore = surfaceOffset;
"""

SUSPECT_ENTRY_NEW = """                surfaceBaroAtSuspect = latestRelativeBaro;
                surfaceTofAgeAtSuspectMs = surfaceTofAgeMs;
                surfaceBaroAgeAtSuspectMs = surfaceBaroAgeMs;
                surfaceBaroLagAtSuspect = surfaceBaroLagEvents;
                surfaceBaroSeenAtSuspect = surfaceBaroSeen;
                surfaceVzAtSuspect = stateNav[5];
                surfaceOffsetBefore = surfaceOffset;
"""

SUSPECT_RESTART_OLD = """                  surfaceSuspectStartMs = nowMs;
                  surfaceBaroAtSuspect = latestRelativeBaro;
                  surfaceSuspectCount = 0;
"""

SUSPECT_RESTART_NEW = """                  surfaceSuspectStartMs = nowMs;
                  surfaceBaroAtSuspect = latestRelativeBaro;
                  surfaceTofAgeAtSuspectMs = surfaceTofAgeMs;
                  surfaceBaroAgeAtSuspectMs = surfaceBaroAgeMs;
                  surfaceBaroLagAtSuspect = surfaceBaroLagEvents;
                  surfaceBaroSeenAtSuspect = surfaceBaroSeen;
                  surfaceVzAtSuspect = stateNav[5];
                  surfaceSuspectCount = 0;
"""

DECISION_OLD = """              surfaceCandidateInno = candidateInnovation * candidateInnovation / Pyy;

              if (verticalVeto)
"""

DECISION_NEW = """              surfaceCandidateInno = candidateInnovation * candidateInnovation / Pyy;
              surfaceLateDecisionEligible = (
                sameSignPersistent && settled && plausibleStep &&
                surfaceCandidateInno < qualGateTof) ? 1U : 0U;
              if (surfaceLateDecisionEligible)
              {
                surfaceTofAgeAtDecisionMs = surfaceTofAgeMs;
                surfaceBaroAgeAtDecisionMs = surfaceBaroAgeMs;
                surfaceBaroLagAtDecision = surfaceBaroLagEvents;
                surfaceBaroSeenAtDecision = surfaceBaroSeen;
                surfaceVzAtDecision = stateNav[5];
                surfaceBaroAtDecision = latestRelativeBaro;
                surfaceBaroDeltaAtDecision = surfaceBaroDelta;
              }

              if (verticalVeto)
"""

LOG_OLD = """LOG_ADD(LOG_UINT8, surfState, &surfaceDetectorState)
LOG_ADD(LOG_UINT8, surfReason, &surfaceDetectorReason)
LOG_GROUP_STOP(sensorFilter)
"""

LOG_NEW = """LOG_ADD(LOG_UINT8, surfState, &surfaceDetectorState)
LOG_ADD(LOG_UINT8, surfReason, &surfaceDetectorReason)
// X3 timing/provenance logs. Ages are ms; baroLag counts dequeued measurements.
LOG_ADD(LOG_UINT32, tofAge, &surfaceTofAgeMs)
LOG_ADD(LOG_UINT32, baroAge, &surfaceBaroAgeMs)
LOG_ADD(LOG_UINT32, baroLag, &surfaceBaroLagEvents)
LOG_ADD(LOG_UINT32, tofAge0, &surfaceTofAgeAtSuspectMs)
LOG_ADD(LOG_UINT32, baroAge0, &surfaceBaroAgeAtSuspectMs)
LOG_ADD(LOG_UINT32, baroLag0, &surfaceBaroLagAtSuspect)
LOG_ADD(LOG_UINT8, baroSeen, &surfaceBaroSeen)
LOG_ADD(LOG_UINT8, baroSeen0, &surfaceBaroSeenAtSuspect)
LOG_ADD(LOG_UINT8, lateElig, &surfaceLateDecisionEligible)
LOG_ADD(LOG_UINT32, tofAgeD, &surfaceTofAgeAtDecisionMs)
LOG_ADD(LOG_UINT32, baroAgeD, &surfaceBaroAgeAtDecisionMs)
LOG_ADD(LOG_UINT32, baroLagD, &surfaceBaroLagAtDecision)
LOG_ADD(LOG_UINT8, baroSeenD, &surfaceBaroSeenAtDecision)
LOG_ADD(LOG_FLOAT, baro0, &surfaceBaroAtSuspect)
LOG_ADD(LOG_FLOAT, vz0, &surfaceVzAtSuspect)
LOG_ADD(LOG_FLOAT, vzDec, &surfaceVzAtDecision)
LOG_ADD(LOG_FLOAT, baroDec, &surfaceBaroAtDecision)
LOG_ADD(LOG_FLOAT, baroDDec, &surfaceBaroDeltaAtDecision)
LOG_GROUP_STOP(sensorFilter)
"""

BIAS_RESET_OLD = """        surfaceDetectorState = S3_STATE_NORMAL;
        surfaceDetectorReason = S3_REASON_NONE;

      // set initial parameters"""

BIAS_RESET_NEW = """        surfaceDetectorState = S3_STATE_NORMAL;
        surfaceDetectorReason = S3_REASON_NONE;
        surfaceQueueSequence = 0;
        surfaceLatestBaroSequence = 0;
        surfaceLatestBaroProcessMs = 0;
        surfaceTofAgeMs = 0;
        surfaceBaroAgeMs = 0;
        surfaceBaroLagEvents = 0;
        surfaceTofAgeAtSuspectMs = 0;
        surfaceBaroAgeAtSuspectMs = 0;
        surfaceBaroLagAtSuspect = 0;
        surfaceTofAgeAtDecisionMs = 0;
        surfaceBaroAgeAtDecisionMs = 0;
        surfaceBaroLagAtDecision = 0;
        surfaceBaroSeen = 0;
        surfaceBaroSeenAtSuspect = 0;
        surfaceBaroSeenAtDecision = 0;
        surfaceLateDecisionEligible = 0;
        surfaceVzAtSuspect = 0.0f;
        surfaceVzAtDecision = 0.0f;
        surfaceBaroAtDecision = 0.0f;
        surfaceBaroDeltaAtDecision = 0.0f;

      // set initial parameters"""

NAV_RESET_OLD = """  surfaceDetectorState = S3_STATE_NORMAL;
  surfaceDetectorReason = S3_REASON_NONE;

  // set initial parameters"""

NAV_RESET_NEW = """  surfaceDetectorState = S3_STATE_NORMAL;
  surfaceDetectorReason = S3_REASON_NONE;
  surfaceQueueSequence = 0;
  surfaceLatestBaroSequence = 0;
  surfaceLatestBaroProcessMs = 0;
  surfaceTofAgeMs = 0;
  surfaceBaroAgeMs = 0;
  surfaceBaroLagEvents = 0;
  surfaceTofAgeAtSuspectMs = 0;
  surfaceBaroAgeAtSuspectMs = 0;
  surfaceBaroLagAtSuspect = 0;
  surfaceTofAgeAtDecisionMs = 0;
  surfaceBaroAgeAtDecisionMs = 0;
  surfaceBaroLagAtDecision = 0;
  surfaceBaroSeen = 0;
  surfaceBaroSeenAtSuspect = 0;
  surfaceBaroSeenAtDecision = 0;
  surfaceLateDecisionEligible = 0;
  surfaceVzAtSuspect = 0.0f;
  surfaceVzAtDecision = 0.0f;
  surfaceBaroAtDecision = 0.0f;
  surfaceBaroDeltaAtDecision = 0.0f;

  // set initial parameters"""

MARKERS = (
    ("timing state", STATE_OLD, STATE_NEW, 1),
    ("bias reset", BIAS_RESET_OLD, BIAS_RESET_NEW, 1),
    ("navigation reset", NAV_RESET_OLD, NAV_RESET_NEW, 1),
    ("queue sequence", QUEUE_OLD, QUEUE_NEW, 1),
    ("ToF timing", TOF_OLD, TOF_NEW, 1),
    ("barometer provenance", BARO_OLD, BARO_NEW, 1),
    ("SUSPECT-entry provenance", SUSPECT_ENTRY_OLD, SUSPECT_ENTRY_NEW, 1),
    ("SUSPECT-restart provenance", SUSPECT_RESTART_OLD, SUSPECT_RESTART_NEW, 1),
    ("late-decision VZ snapshot", DECISION_OLD, DECISION_NEW, 1),
    ("timing logs", LOG_OLD, LOG_NEW, 1),
)


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


def marker_state(text: str) -> str:
    states: list[str] = []
    for label, old, new, count in MARKERS:
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count == count and new_count == 0:
            states.append("old")
        elif old_count == 0 and new_count == count:
            states.append("new")
        else:
            raise SystemExit(
                f"{label}: expected old={count}/new=0 or old=0/new={count}, "
                f"found old={old_count}, new={new_count}; no file written"
            )
    if all(state == "old" for state in states):
        return "applicable"
    if all(state == "new" for state in states):
        return "applied"
    raise SystemExit("partial X3 timing-observer application detected; no file written")


def require_exact_context(text: str) -> str:
    if git("rev-parse", "HEAD") != EXPECTED_COMMIT:
        raise SystemExit("wrong upstream commit; no file written")
    if "WebeeBlocks #70 S3 Lab prototype" not in text:
        raise SystemExit("S3 base applicator has not been applied; no file written")
    if "S3_REASON_BOTH_VETO = 8" not in text or "vzVerticalVeto" not in text:
        raise SystemExit("S3 VZ/BARO/BOTH discriminator has not been applied; no file written")
    return marker_state(text)


def transform(text: str) -> str:
    state = require_exact_context(text)
    if state == "applied":
        return text
    for _label, old, new, count in MARKERS:
        text = text.replace(old, new, count)
    if require_exact_context(text) != "applied":
        raise SystemExit("X3 timing observer failed postcondition; no file written")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify exact S3+discriminator context and timing-observer applicability",
    )
    args = parser.parse_args()

    if not TARGET.is_file():
        raise SystemExit(f"missing target: {TARGET}")
    original = TARGET.read_text(encoding="utf-8")
    state = require_exact_context(original)
    transformed = transform(original)
    if args.check:
        print(f"S3 X3 timing observer: {state}")
        return
    if transformed == original:
        print("S3 X3 timing observer already applied; no file written")
        return
    TARGET.write_text(transformed, encoding="utf-8")
    print(
        "Applied S3 X3 timing observer: ToF age, barometer queue provenance, "
        "and SUSPECT/decision VZ snapshots only"
    )


if __name__ == "__main__":
    main()
