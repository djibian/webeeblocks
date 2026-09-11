#!/usr/bin/env python3
"""Negative oracle controls; these fixtures are not a live-dialog qualification."""

from pathlib import Path
import tempfile
import unittest

import qualify


LOG = """Q87 WB_INIT_RETURN
Q87 PROVIDER_CALLED
WEBEEBLOCKS_FILE_BROKER_V1 QT_APP_INITIALIZED
WEBEEBLOCKS_FILE_BROKER_V1 QFILEDIALOG_CONSTRUCTED
Q87 DIALOG_EXEC
Q87 DIALOG_EXPOSED pid=321 wid=987 width=600 height=400
Q87 DIALOG_CANCELLED result=Rejected
Q87 PROVIDER_RETURNED
Q87 LOOP_RETURN steps=8 before=0.000000 after=0.256000
Q87 CAPABILITIES_RETURN operationsReady=false
Q87 PROVIDER_DESTROYED
Q87 CONTROLLER_COMPLETE
"""
WITNESS = {"pid": 321, "window": 987, "map_state": "IsViewable",
           "focus_verified": True, "cancel": "XTEST_ESCAPE"}


class OracleTests(unittest.TestCase):
    def test_complete_synthetic_record_and_refuting_outcomes(self):
        self.assertEqual(qualify.evaluate(LOG, WITNESS, 0, True, True), "PASS")
        self.assertEqual(qualify.evaluate(LOG, WITNESS, 1, True, True), "FAIL")
        self.assertEqual(qualify.evaluate(LOG, WITNESS, 0, False, True), "FAIL")
        self.assertEqual(qualify.evaluate(LOG.replace("0.256000", "0.000000"), WITNESS, 0, True, True), "FAIL")
        self.assertEqual(qualify.evaluate("Q87 WB_INIT_RETURN\nQ87 PROVIDER_CALLED\nQ87 FATAL\n", None, 139, True, False), "FAIL")

    def test_constructed_or_programmatic_cancel_cannot_replace_real_exposure(self):
        for missing in ("Q87 DIALOG_EXPOSED", "Q87 DIALOG_CANCELLED", "Q87 PROVIDER_RETURNED", "Q87 LOOP_RETURN"):
            truncated = "\n".join(line for line in LOG.splitlines() if missing not in line)
            self.assertEqual(qualify.evaluate(truncated, WITNESS, 0, True, True), "UNPROVEN")
        for patch in ({"pid": 322}, {"window": 988}, {"focus_verified": False},
                      {"map_state": "IsUnmapped"}, {"cancel": "direct-reject-call"}):
            witness = {**WITNESS, **patch}
            self.assertEqual(qualify.evaluate(LOG, witness, 0, True, True), "UNPROVEN")
        self.assertEqual(qualify.evaluate(LOG, WITNESS, 0, True, False), "UNPROVEN")

    def test_event_order_and_unknown_launcher_are_not_success(self):
        reverse = "\n".join(reversed(LOG.splitlines()))
        self.assertEqual(qualify.evaluate(reverse, WITNESS, 0, True, True), "UNPROVEN")
        self.assertEqual(qualify.evaluate("", None, 0, True, False), "UNPROVEN")

    def test_preparation_keeps_provider_factory_and_adds_only_dialog_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            evidence = Path(directory) / "evidence"
            controller = project / "controllers/qt_provider_probe"
            controller.mkdir(parents=True)
            (project / "worlds").mkdir()
            evidence.mkdir()
            original = "namespace {\nvoid constructor() {\n    std::fflush(stdout);\n}\n}\n"
            (controller / "file_broker.cpp").write_text(original)
            qualify.prepare(project, evidence)
            actual = (controller / "file_broker.cpp").read_text()
            self.assertEqual((evidence / "provider-original.cpp").read_text(), original)
            self.assertEqual(actual.count("qualify_dialog(*mDialog);"), 1)
            self.assertIn('controller "qt_provider_probe"', (project / "worlds/qualification.wbt").read_text())


if __name__ == "__main__":
    unittest.main()
