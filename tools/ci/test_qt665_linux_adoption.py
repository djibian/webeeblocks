#!/usr/bin/env python3
"""#665: fail-closed static inventory of Linux *consumer* runtime selectors.

The legacy physical qualification image is intentionally a separately hashed,
locked input; this probe must NEVER silently rewrite that evidence.
Runtime process identity and native oracles remain separate dynamic obligations.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca"
OFFICIAL = (
    "cyberbotics/webots:R2025a-ubuntu22.04",
    "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099",
)
CONSUMERS = (
    ".github/workflows/ci-runtime.yml",
    ".github/workflows/ci-webots.yml",
    "tools/ci/build_historical_blockly_sidecar.sh",
    "tools/ci/run_crazyflie_ab_matrix.py",
    "tools/ci/run_crazyflie_first_obstacle.py",
    "tools/ci/run_crazyflie_b_edge_matrix.py",
    "tools/ci/run_crazyflie_primitive_matrix.py",
    "tools/ci/run_runtime_v2_firefox_project_files.py",
    "tools/ci/run_grand_prix_prototype.py",
    "tools/ci/run_grand_prix_u_geometry.py",
    "tools/ci/run_progression_autonomous_mission.py",
    "tools/ci/run_progression_combined_decisions_mission.py",
    "tools/ci/run_progression_memory_mission.py",
    "tools/ci/run_progression_memory_overwrite.py",
    "tools/ci/run_progression_reactive_mission.py",
    "tools/ci/run_progression_repeat_mission.py",
    "tools/ci/run_progression_sequence_mission.py",
    "tools/ci/run_progression_simple_decision_mission.py",
    "tools/ci/run_runtime_v2_outcome_freshness.py",
)
SUPPORT = (
    "tools/ci/test_workflow_contract.py",
    "tools/ci/ci_optimization_report.py",
    "tools/ci/test_historical_boost_support.py",
)


def enforce_selector(source):
    if IMAGE not in source:
        raise ValueError("qualified immutable OCI digest missing")
    for rejected in OFFICIAL:
        if rejected in source:
            raise ValueError("unqualified legacy image still selected")


class LinuxConsumerImageTests(unittest.TestCase):
    def test_every_actual_linux_consumer_is_qualified(self):
        for relative in CONSUMERS + SUPPORT:
            with self.subTest(path=relative):
                enforce_selector((ROOT / relative).read_text(encoding="utf-8"))

    def test_reject_old_image_missing_digest_and_mixed_sources(self):
        for text in ("", "cyberbotics/webots:R2025a-ubuntu22.04",
                     IMAGE.split("@")[0] + ":elf-e45a90b580a00f50",
                     IMAGE + "\ncyberbotics/webots:R2025a-ubuntu22.04",
                     IMAGE + "\n" + OFFICIAL[1]):
            with self.subTest(bad=text[:62]):
                with self.assertRaises(ValueError):
                    enforce_selector(text)
        enforce_selector("IMAGE = '" + IMAGE + "'")

    def test_separate_physical_qualification_lock_is_not_rewritten(self):
        # These certified generated inputs are distinct from CI's execution
        # consumers, and must not be silently mutated as a side effect.
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        physical = (ROOT / "tools/physical/qualification_generated_lock.json").read_text(encoding="utf-8")
        self.assertIn("WEBOTS_IMAGE='" + OFFICIAL[1] + "'", ci)
        self.assertIn('"image": "' + OFFICIAL[1] + '"', physical)
        self.assertNotIn(IMAGE, physical)


if __name__ == "__main__":
    unittest.main()
