#!/usr/bin/env python3
"""No native proof may be relabelled by a failed Activity 6 CI bootstrap."""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_progression_combined_decisions_mission import (
    ACTIVITY6_WEBOTS_LAUNCH, ROOT, setup_failure_message,
)


class Activity6SetupPhaseTests(unittest.TestCase):
    def test_historical_prelaunch_exit_eight_stays_prelaunch_not_webots(self):
        # Actual archived stdout of PR #690, shard 4: no Webots startup evidence.
        historical = "debconf: delaying package configuration, since apt-utils is not installed\n"
        self.assertEqual(
            setup_failure_message(8, historical),
            "Activity 6 CI setup never reached an observed Webots launch (exit=8)",
        )
        self.assertIsNotNone(setup_failure_message(124, historical))

    def test_launch_marker_does_not_mask_real_native_failure(self):
        self.assertIsNone(setup_failure_message(8, ACTIVITY6_WEBOTS_LAUNCH + "\n"))
        self.assertIsNone(setup_failure_message(124, ACTIVITY6_WEBOTS_LAUNCH + "\n"))

    def test_shell_observes_all_setup_boundaries_without_changing_native_timeout(self):
        source = (ROOT / "tools/ci/run_progression_combined_decisions_mission.py").read_text()
        for stage in ("apt-index", "tools-install", "chrome-download", "chrome-install"):
            self.assertIn(f"WEBEEBLOCKS_ACTIVITY6_SETUP stage={stage} status=begin", source)
            self.assertIn(f"WEBEEBLOCKS_ACTIVITY6_SETUP stage={stage} status=ok", source)
        self.assertIn('if wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb; then', source)
        self.assertIn('echo "WEBEEBLOCKS_ACTIVITY6_SETUP stage=chrome-download status=fail rc=$setup_rc"', source)
        self.assertIn('exit "$setup_rc"', source)
        self.assertLess(source.index("stage=chrome-download status=begin"),
                        source.index("echo WEBEEBLOCKS_ACTIVITY6_SETUP stage=webots status=launch"))
        self.assertLess(source.index("echo WEBEEBLOCKS_ACTIVITY6_SETUP stage=webots status=launch"),
                        source.index("timeout -k 5s 540s xvfb-run"))
        self.assertLess(source.index("setup_failure = setup_failure_message("),
                        source.index("if result.returncode == 124:"))
        self.assertIn('"COMBINED_FRONT_ONLY_BBO_NOT_ACHIEVED"', source)
        self.assertIn('"COMBINED_FRONT_LEFT_BBO_NOT_ACHIEVED"', source)

    def test_static_preflight_is_required(self):
        source = (ROOT / "tools/ci/run_progression_combined_decisions_mission.py").read_text()
        self.assertIn('["python3", "tools/ci/test_activity6_setup_phase.py"]', source)


if __name__ == "__main__":
    unittest.main()
