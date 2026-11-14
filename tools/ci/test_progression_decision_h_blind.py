#!/usr/bin/env python3
"""A4 blind-path native witness construction and unforgeable failure checks."""
from pathlib import Path
import ast
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
JS=ROOT/'plugins/robot_windows/decision_h_blind_probe/decision_h_blind_probe.js'
HTML=ROOT/'plugins/robot_windows/decision_h_blind_probe/decision_h_blind_probe.html'
RUN=ROOT/'tools/ci/run_classroom_decision_h_blind.py'


class BlindNativeControls(unittest.TestCase):
    def test_no_sensor_or_weak_physical_oracle(self):
        js=JS.read_text(encoding='utf-8')
        node=shutil.which('node')
        self.assertIsNotNone(node,'Node required')
        cmd=subprocess.run([node,'--check',str(JS)],capture_output=True,text=True,timeout=20)
        self.assertEqual(cmd.returncode,0,cmd.stdout+cmd.stderr)
        for name in ('a','b'):
            self.assertIn("for(const variant of ['a','b'])",js)
        for fragment in (
          "await backend.vertical('up',0.10)",
          "await backend.vertical('down',0.35)",
          "await backend.move('forward',0.75)",
          "await backend.readActivityOutcome(",
          "result.status==='not-achieved'",
          "await backend.resetSimulation()",
          "A4_BLIND_NATIVE_REFUSED",
          "A4_BLIND_TEST_COMPLETE",
          "rangeReads:0",
        ):
            self.assertIn(fragment,js)
        for forbidden in (
          "backend.range(", "backend.completeActivityMission(",
          "wb_supervisor_node_", "WB_DH_NOT_ACHIEVED", "WEBEEBLOCKS_DECISION_H_RESULT",
          "WebeeBlocksSemanticAst", "WebeeBlocksProjectFiles",
        ):
            self.assertNotIn(forbidden,js)
        html=HTML.read_text(encoding='utf-8')
        self.assertIn("decision_h_blind_probe.js",html)
        self.assertIn("wwi_backend.js",html)
        self.assertIn("A4_BLIND_HTML_LOADED",html)

    def test_draft_and_canonical_runtime_protect_both_native_witnesses(self):
        for workflow in ('.github/workflows/ci-progression-a4-draft.yml',
                         '.github/workflows/ci-runtime.yml'):
            content=(ROOT/workflow).read_text(encoding='utf-8')
            self.assertIn('python3 tools/ci/run_classroom_decision_h_pupil.py',content)
            self.assertIn('python3 tools/ci/run_classroom_decision_h_blind.py',content)
            self.assertIn('A4_PUPIL_EXIT=$pupil_status A4_BLIND_EXIT=$blind_status',content)
            self.assertIn('test "$pupil_status" -eq 0',content)
            self.assertIn('test "$blind_status" -eq 0',content)
            self.assertIn('ci-artifacts/progression-decision-h-blind/',content)
            self.assertIn('if: always()',content)

    def test_native_runner_requires_two_actual_wrong_scene_refusals(self):
        src=RUN.read_text(encoding='utf-8')
        ast.parse(src,filename=str(RUN))
        for token in (
          "prepare_classroom_decision_h_pupil as pupil",
          "pupil.compose(pupil.ack.SOURCE.read_text(encoding='utf-8'))",
          "run_classroom_altitude_scene_ack as ack",
          'window "decision_h_blind_probe"',
          "WORLD=ROOT/'worlds/ci_classroom_decision_h_blind.wbt'",
          "refusing to overwrite existing blind-native world",
          "refusing to delete changed blind-native world",
          "WEBEEBLOCKS_DECISION_H_VERDICT_SAMPLE attempt=",
          "WEBEEBLOCKS_DECISION_H_RESULT scene=",
          "results==[('A','1','not-achieved','0'),",
          "('B','2','not-achieved','0')]",
          "A4_BLIND_NATIVE_PASS",
          "no_sensor='WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE' not in log",
        ):
            self.assertIn(token,src)
        self.assertIn("s[4]=='0' and s[5]=='0'",src)
        self.assertIn("s[6]=='0' and s[7]=='1'",src)
        self.assertNotIn('wb_motor_set_',src)
        self.assertNotIn('set_sf_vec3f',src)


if __name__=='__main__':
    unittest.main()
