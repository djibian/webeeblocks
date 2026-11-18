#!/usr/bin/env python3
"""Static guardrails for the real A7 product status/native Webots witness."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"tools/ci/run_classroom_mini_gp_product_ui.py"
PRODUCT_HTML=ROOT/"plugins/robot_windows/blockly_v2/blockly_v2.html"
PRODUCT_MAIN=ROOT/"plugins/robot_windows/blockly_v2/main.js"
SOURCE=ROOT/"tools/ci/prepare_classroom_mini_gp_pupil.py"

class MiniGpRealStudentStatus(unittest.TestCase):
    def test_exact_product_dom_and_real_native_verdict_are_mandatory(self):
        run=RUNNER.read_text(encoding="utf-8")
        ast.parse(run,filename=str(RUNNER))
        page=PRODUCT_HTML.read_text(encoding="utf-8")
        source=PRODUCT_MAIN.read_text(encoding="utf-8")
        self.assertIn('id="runtimeState"',page)
        self.assertIn('id="runtimeDetail"',page)
        self.assertIn('src="main.js"',page)
        self.assertIn("function setRuntimeStatus(state, detail)",source)
        self.assertIn("setRuntimeStatus(missionOutcome.state, missionOutcome.detail)",source)
        for required in (
            "from probe import Cdp, wait_target",
            'window "blockly_v2"',
            'controller "crazyflie_runtime_v2"',
            "WebeeBlocksActivityContract.preflightWorkspace(profile,workspace)",
            "Blockly.serialization.workspaces.load(data,workspace)",
            "button.click()",
            "status.getAttribute('aria-live')!=='polite'",
            "status.contains(state)",
            "status.contains(detail)",
            'script[src="main.js"]',
            "state.textContent",
            "detail.textContent",
            "document.body.dataset.runtimeState",
            "webeeblocks-runtime-v2",
            "webeeblocks-wwi",
            "STATE not-achieved reason=early-finish",
            "WB_MINI_NATIVE_RESULT variant=L attempt=1 status=not-achieved",
            "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF",
            "WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=0.200000000 stop=1",
            "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1",
            "native_motor_and_oracle_attested",
        ):
            self.assertIn(required,run,required)
        # Do not 'prove' the display by creating or assigning the target.
        for forbidden in ("document.createElement('p')",
                          "document.getElementById('runtimeState').textContent=",
                          "document.getElementById('runtimeDetail').textContent=",
                          "setRuntimeStatus(", "WB_MINI_ACHIEVED",
                          "wb_supervisor_field_set_", "wb_motor_set_"):
            self.assertNotIn(forbidden,run,forbidden)
        self.assertIn('window "mini_gp_pupil_probe"',SOURCE.read_text(encoding="utf-8"))
        self.assertIn("SOURCE.read_text",run)
        self.assertIn("cleanup()",run)

if __name__=="__main__":
    unittest.main()
