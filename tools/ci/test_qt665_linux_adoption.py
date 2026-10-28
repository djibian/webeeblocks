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


HISTORICAL_REFERENCE_JOBS = (
    ("encoders-historical", "gyro-gps-historical"),
    ("light-sensor-historical", "sensor-probing-historical"),
    ("sensor-probing-historical", "robot-window-roundtrip"),
)


def actual_webots_consumers_without_historical_witnesses(source):
    """Exclude only #749's *verified official* reference jobs from Qt adoption.

    An unverified legacy image, an extra job, changed native timing,
    online execution or removed pinned provisioning must still be rejected.
    """
    for name, following in HISTORICAL_REFERENCE_JOBS:
        start, end = "\n  " + name + ":\n", "\n  " + following + ":\n"
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("historical Webots witness boundary absent: " + name)
        section = source.split(start, 1)[1].split(end, 1)[0]
        if (section.count("bash tools/ci/pull_pinned_historical_webots.sh") != 1
                or section.count(OFFICIAL[0]) != 1
                or IMAGE in section
                or section.count("bash tools/ci/build_historical_blockly_sidecar.sh --with-supervisor --pinned-reference") != 1
                or "timeout-minutes: 12" not in section
                or "timeout -k 5s 30s xvfb-run" not in section
                or "--network none" not in section
                or "Validate " not in section
                or 'if [ "$code" -eq 124 ] || [ "$code" -eq 137 ]' not in section
                or 'exit "$code"' not in section
                or "continue-on-error:" in section
                or "run: docker pull cyberbotics/webots:R2025a-ubuntu22.04" in section):
            raise ValueError("unqualified historical Webots witness: " + name)
        # Do not exempt any neighboring job or unverified reference.
        source = source.replace(start + section, "", 1)
    return source


def actual_support_selectors_without_historical_contract_literals(source):
    """Tests about official witnesses are not image execution selectors."""
    start = "    def test_historical_cold_provisioning_preserves_native_trial(self) -> None:"
    end = "    def test_gyro_gps_historical_runtime_is_offline(self) -> None:"
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("missing independent historical image contract")
    a = source.index(start)
    b = source.index(end, a)
    historical_contract = source[a:b]
    for anchor in ("def test_historical_image_digest_provisioning_is_fail_closed",
                   "bash tools/ci/pull_pinned_historical_webots.sh",
                   "timeout -k 5s 30s xvfb-run",
                   'self.assertNotIn("ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:'):
        if anchor not in historical_contract:
            raise ValueError("historical image contract incomplete: " + anchor)
    return source[:a] + source[b:]


def actual_sidecar_consumer_with_verified_reference_mode(source):
    """The default sidecar is corrected Qt; only a digest-checked flag may use official."""
    expected = 'IMAGE="' + IMAGE + '"'
    official = 'IMAGE="' + OFFICIAL[0] + '"'
    digest = 'source_id="$(docker image inspect --format \'{{.Id}}\' "' + OFFICIAL[1] + '")"'
    required = (
        'PINNED_REFERENCE=0',
        '--pinned-reference)',
        'if [ "$PINNED_REFERENCE" = 1 ]; then',
        'tag_id="$(docker image inspect --format \'{{.Id}}\' "$IMAGE")"',
        '[[ ! "$source_id" =~ ^sha256:[[:xdigit:]]{64}$ || "$tag_id" != "$source_id" ]]',
        'docker run --rm --network none',
    )
    if source.count(expected) != 1 or source.count(official) != 1 or source.count(digest) != 1:
        raise ValueError("unqualified native sidecar image selector")
    if any(token not in source for token in required):
        raise ValueError("native sidecar official reference guard missing")
    if "docker pull " in source:
        raise ValueError("native sidecar must not fetch any unpinned image")
    return source.replace(official, "", 1).replace(digest, "", 1)



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
                source = (ROOT / relative).read_text(encoding="utf-8")
                if relative == ".github/workflows/ci-webots.yml":
                    source = actual_webots_consumers_without_historical_witnesses(source)
                elif relative == "tools/ci/test_workflow_contract.py":
                    source = actual_support_selectors_without_historical_contract_literals(source)
                elif relative == "tools/ci/build_historical_blockly_sidecar.sh":
                    source = actual_sidecar_consumer_with_verified_reference_mode(source)
                enforce_selector(source)

    def test_reject_old_image_missing_digest_and_mixed_sources(self):
        for text in ("", "cyberbotics/webots:R2025a-ubuntu22.04",
                     IMAGE.split("@")[0] + ":elf-e45a90b580a00f50",
                     IMAGE + "\ncyberbotics/webots:R2025a-ubuntu22.04",
                     IMAGE + "\n" + OFFICIAL[1]):
            with self.subTest(bad=text[:62]):
                with self.assertRaises(ValueError):
                    enforce_selector(text)
        enforce_selector("IMAGE = '" + IMAGE + "'")


    def test_historical_witness_exemption_fails_closed_on_adversarial_mutations(self):
        """A legacy image is never legal merely because its job sounds historical."""
        suite = (ROOT / ".github/workflows/ci-webots.yml").read_text(encoding="utf-8")
        contract = (ROOT / "tools/ci/test_workflow_contract.py").read_text(encoding="utf-8")
        enforce_selector(actual_webots_consumers_without_historical_witnesses(suite))
        enforce_selector(actual_support_selectors_without_historical_contract_literals(contract))
        def mutate_encoder(source, from_text, to_text):
            start, end = "\n  encoders-historical:\n", "\n  gyro-gps-historical:\n"
            section = source.split(start, 1)[1].split(end, 1)[0]
            self.assertEqual(section.count(from_text), 1)
            return source.replace(start + section,
                                  start + section.replace(from_text, to_text, 1), 1)

        for label, damaged in (
            ("unverified pull", mutate_encoder(
                suite, "bash tools/ci/pull_pinned_historical_webots.sh", "true")),
            ("corrected image replacing an official witness", mutate_encoder(
                suite, OFFICIAL[0], IMAGE)),
            ("historical native deadline dropped", mutate_encoder(
                suite, "timeout -k 5s 30s xvfb-run", "xvfb-run")),
            ("historical network reopened", mutate_encoder(
                suite, "--network none", "--network host")),
            ("historical builder fallback to candidate", mutate_encoder(
                suite, "--with-supervisor --pinned-reference", "--with-supervisor")),
            ("unqualified runtime added to other job", suite.replace(
                IMAGE, IMAGE + "\n" + OFFICIAL[0], 1)),
        ):
            with self.subTest(mutant=label), self.assertRaises(ValueError):
                enforce_selector(actual_webots_consumers_without_historical_witnesses(damaged))
        with self.assertRaises(ValueError):
            actual_support_selectors_without_historical_contract_literals(
                contract.replace("def test_historical_image_digest_provisioning_is_fail_closed",
                                 "def renamed_historical_digest_test", 1))
        with self.assertRaises(ValueError):
            enforce_selector(actual_support_selectors_without_historical_contract_literals(
                contract + "\n# Unqualified nonhistorical " + OFFICIAL[0] + "\n"))


    def test_sidecar_reference_image_cannot_be_unpinned_or_impersonated(self):
        sidecar = (ROOT / "tools/ci/build_historical_blockly_sidecar.sh").read_text(encoding="utf-8")
        enforce_selector(actual_sidecar_consumer_with_verified_reference_mode(sidecar))
        for label, damaged in (
            ("source digest changed", sidecar.replace(OFFICIAL[1], OFFICIAL[1][:-1] + "0", 1)),
            ("reference changed", sidecar.replace('IMAGE="' + OFFICIAL[0] + '"',
                                                  'IMAGE="cyberbotics/webots:latest"', 1)),
            ("tag/source check removed", sidecar.replace(
                '"$tag_id" != "$source_id"', '"$tag_id" = "$source_id"', 1)),
            ("network reopened", sidecar.replace("--network none", "--network host", 1)),
            ("implicit unpinned pull", sidecar + "\ndocker pull cyberbotics/webots:latest\n"),
        ):
            with self.subTest(mutant=label), self.assertRaises(ValueError):
                enforce_selector(actual_sidecar_consumer_with_verified_reference_mode(damaged))

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
