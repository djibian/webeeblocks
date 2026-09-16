#!/usr/bin/env python3
"""Fail closed unless the physical-qualification Webots shell is self-contained."""

from __future__ import annotations

import argparse
from pathlib import Path


class QualificationWorldError(RuntimeError):
    """The qualification-only Webots shell is incomplete or externally coupled."""


def verify_world(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise QualificationWorldError(f"qualification world is unavailable: {path}") from exc

    if not text.startswith("#VRML_SIM R2025a utf8\n"):
        raise QualificationWorldError("qualification world must target exact Webots R2025a")

    for forbidden in ("EXTERNPROTO", "http://", "https://", "webots://"):
        if forbidden in text:
            raise QualificationWorldError(
                f"qualification world retains external Webots dependency: {forbidden}"
            )

    exact_markers = (
        'controller "crazyflie_runtime_v2"',
        'window "blockly_v2"',
        'name "m1_motor"',
        'name "m2_motor"',
        'name "m3_motor"',
        'name "m4_motor"',
        'name "range_front"',
        'name "range_back"',
        'name "range_left"',
        'name "range_right"',
        'name "range_up"',
        'name "inertial_unit"',
        'name "color_led"',
    )
    for marker in exact_markers:
        if text.count(marker) != 1:
            raise QualificationWorldError(
                f"qualification world must contain exactly one required binding: {marker}"
            )

    for required in (
        "Robot {",
        "supervisor TRUE",
        "synchronization TRUE",
        "GPS {",
        "Gyro {",
        "InertialUnit {",
        "LED {",
    ):
        if required not in text:
            raise QualificationWorldError(
                f"qualification world missing Runtime v2 bootstrap requirement: {required}"
            )

    if text.count("Propeller {") != 4 or text.count("device RotationalMotor {") != 4:
        raise QualificationWorldError(
            "qualification world must expose exactly four Runtime v2 motor devices"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the self-contained Webots shell used by physical qualification"
    )
    parser.add_argument("world", type=Path)
    args = parser.parse_args()
    verify_world(args.world.resolve())
    print("PASS: self-contained R2025a physical qualification world verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationWorldError as exc:
        print("FAIL: " + str(exc))
        raise SystemExit(1)
