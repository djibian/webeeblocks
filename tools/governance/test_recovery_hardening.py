#!/usr/bin/env python3
import unittest

from recovery_contract import evaluate_recovery
from test_recovery_contract import base_state, incident_state


class RecoveryHardeningTests(unittest.TestCase):
    NOW = "2026-08-27T16:00:00Z"

    def test_executor_unavailable_requires_platform_classification(self):
        state = incident_state("TRANSIENT")
        state["recovery"]["executor_status"] = "UNAVAILABLE"
        with self.assertRaisesRegex(ValueError, "EXECUTOR_UNAVAILABLE_REQUIRES_PLATFORM"):
            evaluate_recovery(state, self.NOW)

        healthy = base_state()
        healthy["recovery"]["executor_status"] = "UNAVAILABLE"
        with self.assertRaisesRegex(ValueError, "EXECUTOR_UNAVAILABLE_REQUIRES_PLATFORM"):
            evaluate_recovery(healthy, self.NOW)

    def test_cause_established_cannot_be_stale_outside_product(self):
        state = incident_state("HARNESS_ORACLE")
        state["recovery"]["cause_established"] = True
        with self.assertRaisesRegex(ValueError, "CAUSE_ESTABLISHED_ONLY_VALID_FOR_PRODUCT"):
            evaluate_recovery(state, self.NOW)

    def test_non_retryable_failure_cannot_keep_retry_window(self):
        state = incident_state(
            "AUTHORITY",
            retry_target=None,
            window_started_at="2026-08-27T12:00:00Z",
        )
        with self.assertRaisesRegex(ValueError, "RETRY_WINDOW_ON_NON_RETRYABLE_FAILURE"):
            evaluate_recovery(state, self.NOW)

    def test_non_retryable_failure_cannot_keep_retry_count(self):
        for failure_class in ("PRODUCT", "HUMAN_GATE", "AUTHORITY", "PLATFORM"):
            state = incident_state(
                failure_class,
                retry_count=1,
                retry_target=None,
                window_started_at=None,
            )
            with self.subTest(failure_class=failure_class), self.assertRaisesRegex(
                ValueError, "RETRY_COUNT_ON_NON_RETRYABLE_FAILURE"
            ):
                evaluate_recovery(state, self.NOW)

    def test_role_retry_target_must_match_expected_role(self):
        state = incident_state("HARNESS_ORACLE", retry_target="ROLE:Verification")
        state["expected_role"] = "Engineering"
        with self.assertRaisesRegex(ValueError, "ROLE_RETRY_TARGET_MISMATCH"):
            evaluate_recovery(state, self.NOW)

    def test_role_retry_requires_valid_expected_role(self):
        state = incident_state("HARNESS_ORACLE", retry_target="ROLE:Engineering")
        state["expected_role"] = "Unknown"
        with self.assertRaisesRegex(ValueError, "INVALID_RETRY_EXPECTED_ROLE"):
            evaluate_recovery(state, self.NOW)


if __name__ == "__main__":
    unittest.main(verbosity=2)
