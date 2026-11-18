"""A6 B native motor geometry adapter: bounded source and negative controls.

This is a SOURCE-ONLY and compilation-contract test, never a R2025a flight
PASS. The native C oracle independently attests physical colliders in Webots.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_count_h_motor_flight as motor

class BMotorGeometrySourceTests(unittest.TestCase):
    def test_all_six_private_worlds_are_real_and_otherwise_unchanged(self):
        for family in ("matched","sampling"):
            for n in (1,2,3):
                with self.subTest(family=family,n=n):
                    from tools.ci.test_a6_b_matched_tail_geometry import validate_scene
                    from tools.ci.test_a6_b_sampling_holdout import SECOND,CLASSIFIER_POSTS,GATE_HALF_X
                    file=(ROOT/f"tools/ci/fixtures/a6-b/count-h-{n}-"
                          f"{motor.B_PRIVATE_FAMILIES[family]}-private.wbo")
                    body=file.read_text(encoding="utf-8")
                    if family=="matched":
                        validate_scene(body,n)
                    else:
                        validate_scene(body,n,expected_positions=SECOND[n],
                            checked_checkpoints=CLASSIFIER_POSTS,
                            checkpoint_margin=GATE_HALF_X,terminal_h=.48)
                    combined=motor.compose(variant=n,scene=body)
                    self.assertEqual(combined.count("PRIVATE A6 CHOICE B"),1)
                    self.assertEqual(combined.count(f"WEBEEBLOCKS_COUNT_{n}_SCENE"),1)
                    self.assertEqual(combined.count(" Solid {"),3*n+2)
                    self.assertEqual(combined.count('controller "progression_count_h_school_pilot"'),1)
                    self.assertEqual(combined.count('controller "progression_count_h_flight_observer"'),0)
    def test_holdout_runner_cannot_claim_counter_or_blockly(self):
        source=(ROOT/"tools/ci/run_classroom_count_h_motor_flight.py").read_text()
        self.assertIn('family not in ("matched","sampling") or mode not in ("reference","blockly")',source)
        self.assertIn('world.prepare(variant=variant,family=family)',source)
        self.assertIn('b_native_holdout_geometry_test_only',source)
        self.assertIn('counter_and_blockly=UNPROVEN',source)
        self.assertIn('"WEBEEBLOCKS_A6_MOTOR_REJECT" not in txt',source)
        self.assertIn('up_motor["native_motor_ray_observed"] and',source)
        wf=(ROOT/'.github/workflows/ci-progression-a6-draft.yml').read_text()
        self.assertIn('a6-b-motor-draft-only:',wf)
        self.assertIn('make A6_B_HOLDOUT_TEST_ONLY=1',wf)
        school=(ROOT/"controllers/progression_count_h_school_pilot/classroom_count_h_scene.cpp").read_text()
        school_make=(ROOT/"controllers/progression_count_h_school_pilot/Makefile").read_text()
        self.assertIn("#ifdef WEBEEBLOCKS_A6_B_PRIVATE_MOTOR_TEST_ONLY",school)
        self.assertIn("const double x=-0.850+0.850*(i-1);",school)
        self.assertIn("bPrivateH[bFamily][variant-1][i-1]",school)
        self.assertIn("!box(bar,x,0,.74,.07,.57,.24)",school)
        self.assertIn("make A6_B_HOLDOUT_TEST_ONLY=1",wf)
        self.assertIn("CFLAGS += -DWEBEEBLOCKS_A6_B_PRIVATE_MOTOR_TEST_ONLY",school_make)
        self.assertIn("a6-b-blockly-count-draft-only:",wf)
        self.assertIn("step_cm: [8, 4]",wf)
        self.assertIn("family: [matched, sampling]",wf)
        self.assertIn("count: [1, 2, 3]",wf)
        self.assertIn('sha256sum -c "a6-b-step${step}-ci-only.wbb.sha256"',wf)
        self.assertIn("needs: a6-private-generic-wbb-build-draft-only",wf)
        self.assertIn("run_classroom_count_h_motor_flight.py",wf)
        self.assertIn("--mode blockly --step-cm ${{ matrix.step_cm }}",wf)
        self.assertIn("if: always()",wf)
        self.assertIn("A6_B_BLOCKLY_COUNT_MOTOR_PASS",source)
        self.assertIn('make CFLAGS="-I../progression_count_h_v1 -DWEBEEBLOCKS_A6_B_PRIVATE_MOTOR_TEST_ONLY"',wf)
        self.assertIn('ci-artifacts/progression-count-h-motor/b-${{ matrix.family }}-reference-n${{ matrix.count }}/',wf)

    def test_b_private_artifact_names_are_path_safe(self):
        # Catches Path + str before all 18 actual R2025a motor jobs.
        from unittest.mock import patch
        from types import SimpleNamespace
        import run_classroom_count_h_motor_flight as runner
        # The flight function is deliberately NOT run in a unit test.
        source=(ROOT/"tools/ci/run_classroom_count_h_motor_flight.py").read_text()
        self.assertIn('ARTIFACT=(world.ARTIFACT/(',source)
        self.assertIn('f"-step{step_cm:02}" if step_cm is not None else ""',source)
        for family in ("matched","sampling"):
            for mode in ("reference","blockly"):
                for n in (1,2,3):
                    for step in ((None,) if mode=="reference" else (4,8)):
                        expected=f"b-{family}-{mode}-n{n}"
                        if step is not None:
                            expected+=f"-step{step:02}"
                        actual=motor.ARTIFACT/expected
                        self.assertTrue(actual.is_relative_to(motor.ARTIFACT))
                        self.assertFalse(".." in actual.parts)

    def test_prepare_private_world_from_protected_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            wbt=Path(directory)/"private.wbt"
            wbproj=Path(directory)/"private.wbproj"
            with patch.object(motor,"WORLD",wbt), patch.object(motor,"PROJECT",wbproj):
                motor.prepare(variant=3,family="sampling")
                self.assertTrue(wbt.is_file())
                self.assertTrue(wbproj.is_file())
                self.assertIn("PRIVATE A6 CHOICE B",wbt.read_text())
                self.assertIn("translation -0.160 0 0.74",wbt.read_text())
                self.assertEqual(wbproj.read_text(),motor.PROJECT_BYTES)

    def test_unknown_or_adversarial_source_rejected(self):
        with self.assertRaises(ValueError):
            motor.compose(variant=4)
        base=(ROOT/"tools/ci/fixtures/a6-b/count-h-3-sampling-holdout-private.wbo").read_text()
        with self.assertRaises(ValueError):
            motor.compose(variant=3,scene=base+'Robot { }')
    def test_compile_time_only_oracle_gate_positions_fail_closed(self):
        core=(ROOT/"controllers/progression_count_h_v1/count_core.h").read_text()
        observer=(ROOT/"controllers/progression_count_h_flight_observer/progression_count_h_flight_observer.c").read_text()
        self.assertIn("WEBEEBLOCKS_A6_B_PRIVATE_MOTOR_TEST_ONLY",core)
        self.assertIn("return -0.850 + 0.850 * (double)index;",core)
        self.assertIn("return index < WB_COUNT_MAX_GATES ? wb_count_b_private_gate_x[index] : NAN;",core)
        self.assertIn("if(b_family<0)return fail",observer)
        self.assertIn("WEBEEBLOCKS_A6_B_MOTOR_GEOMETRY_ATTESTED",observer)
        self.assertIn('!box(bar,x,0,.74,.07,.57,.24',observer)
        self.assertIn('if(!box(screen,1.235,0,.76,.07,1.48,.24',observer)

if __name__=="__main__":unittest.main()
