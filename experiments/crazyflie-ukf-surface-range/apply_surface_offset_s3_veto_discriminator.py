#!/usr/bin/env python3
"""Split the #70 S3 vertical-veto reason without changing veto semantics.

This is a Lab-only instrumentation overlay for the already reconstructed
``apply_surface_offset_s3.py`` candidate. Run that applicator first on the exact
Crazyflie firmware 2026.08 checkout, then run this script.

The only behavioral change is observability: the existing boolean

    abs(stateNav[5]) >= 0.08 || abs(surfaceBaroDelta) >= 0.08

still gates commit exactly as before, but ``surfReason`` distinguishes velocity,
barometer, and simultaneous vetoes. No threshold, persistence window, estimator
state, Flow path, ToF/barometer weighting, controller, or motor authority changes.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
TARGET = Path("src/modules/src/estimator/estimator_ukf.c")

ENUM_OLD = """  S3_REASON_NONE = 0,
  S3_REASON_TOF_REJECT = 1,
  S3_REASON_WAIT = 2,
  S3_REASON_VERTICAL_VETO = 3,
  S3_REASON_COMMIT = 4,
  S3_REASON_CANDIDATE_REJECT = 5,
};"""

ENUM_NEW = """  S3_REASON_NONE = 0,
  S3_REASON_TOF_REJECT = 1,
  S3_REASON_WAIT = 2,
  S3_REASON_VERTICAL_VETO = 3, // legacy aggregate; retained but no longer emitted
  S3_REASON_COMMIT = 4,
  S3_REASON_CANDIDATE_REJECT = 5,
  S3_REASON_VZ_VETO = 6,
  S3_REASON_BARO_VETO = 7,
  S3_REASON_BOTH_VETO = 8,
};"""

VETO_OLD = """              const bool verticalVeto = fabsf(stateNav[5]) >= S3_VZ_VERTICAL_VETO_MPS ||
                fabsf(surfaceBaroDelta) >= S3_BARO_VERTICAL_VETO_M;
"""

VETO_NEW = """              const bool vzVerticalVeto = fabsf(stateNav[5]) >= S3_VZ_VERTICAL_VETO_MPS;
              const bool baroVerticalVeto = fabsf(surfaceBaroDelta) >= S3_BARO_VERTICAL_VETO_M;
              const bool verticalVeto = vzVerticalVeto || baroVerticalVeto;
"""

REASON_OLD = """              if (verticalVeto)
              {
                surfaceDetectorReason = S3_REASON_VERTICAL_VETO;
              }
"""

REASON_NEW = """              if (verticalVeto)
              {
                if (vzVerticalVeto && baroVerticalVeto)
                {
                  surfaceDetectorReason = S3_REASON_BOTH_VETO;
                }
                else if (vzVerticalVeto)
                {
                  surfaceDetectorReason = S3_REASON_VZ_VETO;
                }
                else
                {
                  surfaceDetectorReason = S3_REASON_BARO_VETO;
                }
              }
"""


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


def require_exact_context(text: str) -> None:
    if git("rev-parse", "HEAD") != EXPECTED_COMMIT:
        raise SystemExit("wrong upstream commit; no file written")
    if "WebeeBlocks #70 S3 Lab prototype" not in text:
        raise SystemExit("S3 base applicator has not been applied; no file written")
    for label, old, new in (
        ("reason enum", ENUM_OLD, ENUM_NEW),
        ("vertical-veto expression", VETO_OLD, VETO_NEW),
        ("vertical-veto reason", REASON_OLD, REASON_NEW),
    ):
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count == 1 and new_count == 0:
            continue
        if old_count == 0 and new_count == 1:
            continue
        raise SystemExit(
            f"{label}: expected exactly one old or one new marker, "
            f"found old={old_count}, new={new_count}; no file written"
        )


def transform(text: str) -> str:
    require_exact_context(text)
    if text.count(ENUM_NEW) == 1:
        if text.count(VETO_NEW) == 1 and text.count(REASON_NEW) == 1:
            return text
        raise SystemExit("partial discriminator application detected; no file written")
    text = text.replace(ENUM_OLD, ENUM_NEW, 1)
    text = text.replace(VETO_OLD, VETO_NEW, 1)
    text = text.replace(REASON_OLD, REASON_NEW, 1)
    require_exact_context(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that the exact S3 context is transformable/already transformed",
    )
    args = parser.parse_args()

    if not TARGET.is_file():
        raise SystemExit(f"missing target: {TARGET}")
    original = TARGET.read_text(encoding="utf-8")
    transformed = transform(original)
    if args.check:
        state = "already applied" if transformed == original else "applicable"
        print(f"S3 veto discriminator: {state}")
        return
    if transformed == original:
        print("S3 veto discriminator already applied; no file written")
        return
    TARGET.write_text(transformed, encoding="utf-8")
    print("Applied S3 veto discriminator: VZ/BARO/BOTH reason codes only")


if __name__ == "__main__":
    main()
