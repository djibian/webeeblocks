"""Publisher composition on native API fakes, never a Webots/flight PASS."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.ci.test_grand_prix_route_evaluator_data_v2 import FakeSupervisor, Node, Field
from tools.grand_prix.evaluator_publisher_v2 import NativeRouteEvaluator, ORACLE
from tools.grand_prix.oracle_attempt_v2 import PureResult
from tools.grand_prix.route_courses_v2 import reference_course


class LiveField(Field):
    def __init__(self, fields, name):
        self.fields, self.name = fields, name

    @property
    def value(self):
        return self.fields[self.name]

    def setSFString(self, value):
        self.fields[self.name] = value

    def getSFFloat(self):
        return self.value

    def getSFNode(self):
        return self.value


class LiveNode(Node):
    def getField(self, key):
        return LiveField(self.fields, key) if key in self.fields else None


class NativePublisherTests(unittest.TestCase):
    def setUp(self):
        self.course = reference_course(5)
        self.native = FakeSupervisor(self.course.identifier)
        for node in (self.native.vehicle, self.native.evaluator):
            node.__class__ = LiveNode
            node.fields['supervisor'] = 1  # actual pinned Python SFBool readback
        self.pose = [0., 0., .015]
        self.velocity = [0.] * 6
        self.orientation = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
        self.native.vehicle.getPosition = lambda: self.pose
        self.native.vehicle.getVelocity = lambda: self.velocity
        self.native.vehicle.getOrientation = lambda: self.orientation
        self.native.vehicle.fields['customData'] = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1'
        self.bounds = LiveNode(10, '', 'Cylinder', {'height': .03, 'radius': .05})
        self.physics = LiveNode(11, '', 'Physics', {})
        self.base = {'boundingObject': self.bounds, 'physics': self.physics}
        self.native.vehicle.getBaseNodeField = lambda name: LiveField(self.base, name)
        # Keep the production tick's data readers, wire, RESET window and pure
        # attempt code. The scene check has its own full readback tests.
        self.scene = patch('tools.grand_prix.evaluator_publisher_v2.read_native_evaluator_scene',
                           return_value=self.native.vehicle)
        self.checked = self.scene.start()
        self.addCleanup(self.scene.stop)
        self.evaluator = NativeRouteEvaluator(self.native, self.course.identifier)
        self.ms = 2112
        self.attempt = 1
        self.epoch = 'ab' * 16
        self.start = None
        self.ground = True

    def tick(self, *, advance=8, sample=True, raw=None):
        self.ms += advance
        self.native.now = self.ms / 1000
        prefix = f'attempt={self.attempt} config={self.course.identifier} epoch={self.epoch}'
        if raw is None:
            raw = ('GP_ROUTE_CHALLENGE_V1 ' + prefix if self.start is None else
                   'GP_ROUTE_START_V1 ' + prefix + f' start_ms={self.start} state=admitted')
        self.native.evaluator.fields['customData'] = raw
        if sample:
            stamp = self.ms - self.ms % 32
            self.native.evaluator.fields['model'] = (
                'GP_ROUTE_SAMPLE_V1 ' + prefix + f' time_ms={stamp} period_ms=32 '
                + f'ground={int(self.ground)} ranges_um=2000000,2000000,2000000,2000000,2000000')
        self.evaluator.tick()
        return self.native.evaluator.fields['description']

    def ready(self):
        for _ in range(65):
            self.tick()
        self.assertEqual(self.evaluator.phase, 'ready', self.evaluator.last_error)
        self.assertIn('GP_ROUTE_READY_V1 ', self.native.evaluator.fields['description'])

    def admitted(self):
        self.ready()
        while (self.ms + 8) % 32:
            self.tick()
        self.start = self.ms + 8
        self.assertEqual(self.tick(), '')
        self.assertIn('GP_ROUTE_ALIVE_V1 ', self.tick())
        self.assertEqual(self.evaluator.phase, 'active', self.evaluator.last_error)

    def test_real_readers_require_continuous_ground_and_bound_context(self):
        self.assertEqual(self.native.evaluator.fields['description'], '')
        for _ in range(63):
            self.assertEqual(self.tick(), '')
        self.assertTrue(self.tick().startswith('GP_ROUTE_READY_V1 '))
        self.assertEqual(self.native.vehicle.fields['customData'], 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1')
        self.assertIsNone(self.evaluator._active)

    def test_missing_bootstrap_packet_waits_but_never_grants_or_repairs_data(self):
        self.native.evaluator.fields['model'] = ''
        for _ in range(5):
            self.assertEqual(self.tick(sample=False), '')
        self.assertEqual(self.evaluator.phase, 'observing-reset')
        self.assertEqual(self.tick(sample=False), '')
        self.assertEqual(self.evaluator.phase, 'failed')
        for _ in range(70):
            self.assertEqual(self.tick(), '')

    def test_ground_flag_alone_is_not_a_native_reset_proof(self):
        for mutation in ('position', 'altitude', 'motion', 'attitude', 'contact', 'ground'):
            with self.subTest(mutation=mutation):
                # Reset the API fake, then construct a fresh evaluator. No
                # failed sampler/window is reused between counterexamples.
                self.pose[:] = [0., 0., .015]
                self.velocity[:] = [0.] * 6
                self.orientation[:] = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
                self.native.vehicle.contact_points = ()
                self.ground = True
                self.evaluator = NativeRouteEvaluator(self.native, self.course.identifier)
                if mutation == 'position': self.pose[0] = .04
                elif mutation == 'altitude': self.pose[2] = .65
                elif mutation == 'motion': self.velocity[3] = .11
                elif mutation == 'attitude':
                    a = .04
                    import math
                    self.orientation[:] = [math.cos(a), -math.sin(a), 0.,
                                           math.sin(a), math.cos(a), 0., 0., 0., 1.]
                elif mutation == 'contact':
                    self.native.vehicle.contact_points = (SimpleNamespace(point=[0., 0., .1], node_id=8),)
                else: self.ground = False
                for _ in range(70):
                    self.assertEqual(self.tick(), '')

    def test_admission_and_liveness_need_fresh_ready_on_this_process(self):
        self.start = self.ms + 8
        self.assertEqual(self.tick(), '')
        self.assertIn('without-fresh-reset', self.evaluator.last_error)
        self.start = None
        for _ in range(70):
            self.assertEqual(self.tick(), '')

    def test_gap_revokes_and_new_reset_rebuilds_without_old_packet_or_outcome(self):
        self.admitted()
        self.assertEqual(self.tick(advance=16), '')
        self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])
        for _ in range(4): self.assertEqual(self.tick(), '')
        self.attempt = 2
        self.epoch = 'cd' * 16
        self.start = None
        self.native.vehicle.fields['customData'] = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2'
        self.native.evaluator.fields['model'] = ''
        self.assertEqual(self.tick(sample=False), '')
        self.ready()
        self.assertIn('attempt=2 ', self.native.evaluator.fields['description'])
        self.assertIsNone(self.evaluator._active)
        self.assertEqual(self.native.vehicle.fields['customData'], 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2')

    def test_reset_marker_survives_old_evaluator_and_next_attempt_is_admitted(self):
        for already_closed, advance in ((False, 8), (False, 16), (True, 8)):
            with self.subTest(already_closed=already_closed, advance=advance):
                self.evaluator = NativeRouteEvaluator(self.native, self.course.identifier)
                self.attempt, self.epoch, self.start = 1, 'ab' * 16, None
                self.native.vehicle.fields['customData'] = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1'
                self.admitted()
                if already_closed:
                    self.assertEqual(self.tick(advance=16), '')
                    self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])

                # The broker can publish the successful RESET marker before
                # the evaluator sees the new challenge. Keep its old process.
                reset_marker = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2'
                self.native.vehicle.fields['customData'] = reset_marker
                self.native.evaluator.fields['model'] = ''
                self.assertEqual(self.tick(advance=advance, sample=False, raw=''), '')
                self.assertEqual(self.tick(sample=False, raw=''), '')
                self.assertEqual(self.native.vehicle.fields['customData'], reset_marker)

                self.attempt, self.epoch, self.start = 2, 'cd' * 16, None
                self.admitted()
                self.assertIn('GP_ROUTE_ALIVE_V1 attempt=2 ',
                              self.native.evaluator.fields['description'])
                self.assertEqual(self.native.vehicle.fields['customData'], reset_marker)

    def test_invalid_sample_is_fail_stop_for_this_attempt(self):
        self.admitted()
        self.native.evaluator.fields['model'] = self.native.evaluator.fields['model'].replace(
            'epoch=' + self.epoch, 'epoch=' + 'ef' * 16)
        with self.assertLogs('tools.grand_prix.evaluator_publisher_v2') as log:
            self.assertEqual(self.tick(sample=False), '')
            failed_ms = self.ms
            for _ in range(70): self.assertEqual(self.tick(), '')
        self.assertEqual(len(log.records), 1)
        self.assertIn(f'attempt=1 time_ms={failed_ms} reason=invalid-native-observation',
                      log.records[0].getMessage())
        self.assertIn('detail=', log.records[0].getMessage())
        self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])

    def test_first_cause_survives_both_orders_of_native_safety_land(self):
        # Controlled channel interleavings, not a Webots flight witness.
        # Native C++ pilot preservation is tested by the admission probe.
        self.admitted()
        generic = f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle={ORACLE} status=not-achieved'
        causal = generic + ' reason=altitude'

        # Order A: evaluator writes before independent safety LAND.
        self.evaluator._close(self.ms + 8, 'altitude')
        self.assertEqual(self.native.vehicle.fields['customData'], causal)
        self.assertEqual(self.native.evaluator.fields['description'], '')
        self.assertEqual(self.evaluator._active.result.reason, 'altitude')
        self.assertFalse(self.tick())

        # Order B: pilot writes its generic failure synchronously while
        # evaluator revokes ALIVE, just before the evaluator's cause write.
        self.attempt, self.epoch, self.start = 2, 'cd' * 16, None
        self.native.vehicle.fields['customData'] = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2'
        self.admitted()
        generic2 = generic.replace('attempt=1 ', 'attempt=2 ')
        causal2 = causal.replace('attempt=1 ', 'attempt=2 ')
        original_set = self.evaluator._reply.setSFString
        def pilot_on_revoke(value):
            original_set(value)
            if value == '':
                self.native.vehicle.fields['customData'] = generic2
        self.evaluator._reply.setSFString = pilot_on_revoke
        self.evaluator._close(self.ms + 8, 'altitude')
        self.assertEqual(self.native.vehicle.fields['customData'], causal2)
        self.assertEqual(self.evaluator._active.result.reason, 'altitude')
        self.assertEqual(self.evaluator._closed_attempt, 2)

    def test_cause_enrichment_preserves_prior_cause_timeout_and_other_identity(self):
        self.admitted()
        for case in ('first-cause', 'native-deadline', 'stale-attempt',
                     'other-oracle', 'interrupted'):
            generic = (f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt={self.attempt} '
                       f'oracle={ORACLE} status=not-achieved')
            current = {
                'first-cause': generic + ' reason=envelope-contact',
                'native-deadline': generic + ' reason=time-limit',
                'stale-attempt': generic.replace(
                    f'attempt={self.attempt} ', f'attempt={self.attempt + 1} '),
                'other-oracle': generic.replace(
                    f'oracle={ORACLE}', 'oracle=other-oracle'),
                'interrupted': generic.replace('status=not-achieved', 'status=interrupted'),
            }[case]
            with self.subTest(case=case, current=current):
                self.native.vehicle.fields['customData'] = current
                self.evaluator._close(self.ms + 8, 'low-outside-zone')
                self.assertEqual(self.native.vehicle.fields['customData'], current)
                self.attempt += 1
                self.epoch = format(self.attempt, '032x')
                self.start = None
                self.native.vehicle.fields['customData'] = (
                    f'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 {self.attempt}')
                self.admitted()

    def test_ambiguous_cause_never_enriches_generic_pilot_result(self):
        self.admitted()
        generic = f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle={ORACLE} status=not-achieved'
        self.native.vehicle.fields['customData'] = generic
        self.evaluator._close(self.ms + 8, 'invalid-native-observation')
        self.assertEqual(self.native.vehicle.fields['customData'], generic)
        self.assertEqual(self.evaluator._active.result.reason, 'invalid-native-observation')

    def test_reset_marker_precedes_late_evaluator_close_and_remains_fresh(self):
        self.admitted()
        self.native.vehicle.fields['customData'] = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2'
        self.evaluator._close(self.ms + 8, 'altitude')
        self.assertEqual(self.native.vehicle.fields['customData'],
                         'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2')
        self.attempt, self.epoch, self.start = 2, 'ef' * 16, None
        self.admitted()
        self.assertEqual(self.evaluator.phase, 'active')
        self.assertEqual(self.native.vehicle.fields['customData'],
                         'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2')

    def test_unused_bootstrap_epoch_change_discards_the_partial_window(self):
        for _ in range(40): self.assertFalse(self.tick())
        self.epoch = 'cd' * 16
        for _ in range(63): self.assertFalse(self.tick())
        self.assertIn('GP_ROUTE_READY_V1 ', self.tick())
        self.assertIn('epoch=' + self.epoch, self.native.evaluator.fields['description'])
        self.ground = False
        self.assertFalse(self.tick())
        self.epoch = 'ef' * 16
        self.ground = True
        for _ in range(70): self.assertFalse(self.tick())

    def test_scene_change_and_restore_cannot_resurrect_old_readiness(self):
        self.ready()
        self.checked.side_effect = RuntimeError('moved L collider')
        self.assertEqual(self.tick(), '')
        self.checked.side_effect = None
        for _ in range(70): self.assertEqual(self.tick(), '')

    def test_fake_positive_marker_and_completion_at_start_never_win(self):
        self.admitted()
        self.native.vehicle.fields['customData'] = (
            f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle={ORACLE} status=achieved')
        self.assertEqual(self.tick(), '')
        self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])

    def test_incomplete_program_completes_as_failed_not_as_an_expert_solution(self):
        self.admitted()
        self.native.vehicle.fields['customData'] = (
            f'WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=1 oracle={ORACLE}')
        with self.assertLogs('tools.grand_prix.evaluator_publisher_v2') as log:
            for _ in range(190): self.tick()
        self.assertEqual(len(log.records), 1)
        self.assertIn('reason=wrong-landing', log.records[0].getMessage())
        self.assertEqual(self.native.evaluator.fields['description'], '')
        self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])

    def test_positive_publication_keeps_alive_and_never_overwrites_pilot_failure(self):
        self.admitted()
        self.terminal_fixture()
        result = PureResult('achieved', self.course.identifier, 1, 1000, None, self.course.count)
        # Isolate the authority handoff race from the independently tested
        # route oracle. This injected terminal is NOT a native success witness.
        with patch('tools.grand_prix.evaluator_publisher_v2.observe_pure_attempt',
                   side_effect=lambda state, *a, **k: replace(state, result=result)):
            self.assertIn('GP_ROUTE_ALIVE_V1 ', self.tick())
        self.assertIn('status=achieved', self.native.vehicle.fields['customData'])
        self.assertIn('GP_ROUTE_ALIVE_V1 ', self.tick())
        self.native.vehicle.fields['customData'] = (
            f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle={ORACLE} status=not-achieved')
        self.assertEqual(self.tick(), '')
        self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])
        self.assertFalse(self.tick())

    def terminal_fixture(self):
        # Synthetic terminal history for handoff tests only. The real pure
        # oracle's full route/crossing/dwell proofs are tested independently.
        target = self.course.route.landing_target(self.course.count)
        self.pose[:] = [*target, .015]
        before = self.evaluator.observation
        self.evaluator.observation = replace(before, kinematics=replace(
            before.kinematics, position=tuple(self.pose)))

    def test_positive_handoff_still_requires_current_native_landing_evidence(self):
        self.admitted()
        self.terminal_fixture()
        result = PureResult('achieved', self.course.identifier, 1, 1000, None, self.course.count)
        with patch('tools.grand_prix.evaluator_publisher_v2.observe_pure_attempt',
                   side_effect=lambda state, *a, **k: replace(state, result=result)):
            self.assertIn('GP_ROUTE_ALIVE_V1 ', self.tick())
        self.ground = False
        self.assertFalse(self.tick())
        # Preserve a result possibly already consumed by the pilot; ALIVE is
        # revoked so a pilot that has not latched it must independently fail.
        self.assertIn('status=achieved', self.native.vehicle.fields['customData'])
        for _ in range(5): self.assertFalse(self.tick())

    def test_invalid_or_restarted_native_pose_never_recalibrates_ground(self):
        self.pose[:] = [2., -1., .8]
        restarted = NativeRouteEvaluator(self.native, self.course.identifier)
        self.assertEqual(restarted._origin_z, .015)
        self.evaluator = restarted
        for _ in range(70): self.assertFalse(self.tick())
        self.bounds.fields['height'] = .031
        with self.assertRaisesRegex(RuntimeError, 'bounds changed'):
            NativeRouteEvaluator(self.native, self.course.identifier)
        self.assertEqual(self.native.evaluator.fields['description'], '')

    def test_healthy_alive_tick_has_no_transient_empty_publication(self):
        self.admitted()
        from unittest.mock import Mock
        original = self.evaluator._reply.setSFString
        writer = Mock(side_effect=original)
        self.evaluator._reply.setSFString = writer
        self.assertIn('GP_ROUTE_ALIVE_V1 ', self.tick())
        self.assertEqual(writer.call_count, 1)
        self.assertNotEqual(writer.call_args.args[0], '')

    def test_invalid_clock_revokes_before_raising_and_cannot_be_recovered_in_place(self):
        self.admitted()
        self.native.now = float('nan')
        with self.assertRaises(RuntimeError): self.evaluator.tick()
        self.assertEqual(self.native.evaluator.fields['description'], '')
        self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])
        self.native.now = (self.ms + 8) / 1000
        with self.assertRaisesRegex(RuntimeError, 'terminal native clock'):
            self.evaluator.tick()

    def test_publisher_deadline_precedes_any_first_late_success(self):
        self.admitted()
        self.ground = False
        # Scalar host pose observations, no student program or motor command.
        # Keep the unchanged pure oracle active at ordinary altitude at start.
        while self.pose[2] < .65:
            self.pose[2] = min(.65, self.pose[2] + .02)
            self.tick()
        while self.ms - self.start < 209992:
            self.tick()
        self.assertEqual(self.evaluator.phase, 'active', self.evaluator.last_error)
        with patch('tools.grand_prix.evaluator_publisher_v2.observe_pure_attempt') as oracle:
            self.assertEqual(self.tick(), '')
            oracle.assert_not_called()
        self.assertEqual(self.ms - self.start, 210000)
        self.assertIn('status=not-achieved', self.native.vehicle.fields['customData'])
        self.assertFalse(self.tick())


class NativePublisherEvidenceTests(unittest.TestCase):
    def test_compiled_protocol_wrapper_never_injects_land_and_waits_for_real_acks(self):
        # Compile the actual wrapper against API-shaped callbacks. This proves
        # stimulus/ACK ordering only, not native Webots or a flight outcome.
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import os
        import subprocess
        root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            api = folder / 'webots'
            api.mkdir()
            (api / 'robot.h').write_text('extern "C" double wb_robot_get_time();\n')
            (api / 'supervisor.h').write_text('''
typedef void *WbNodeRef; typedef void *WbFieldRef;
extern "C" WbNodeRef wb_supervisor_node_get_from_def(const char *);
extern "C" WbFieldRef wb_supervisor_node_get_field(WbNodeRef,const char *);
extern "C" const char *wb_supervisor_field_get_sf_string(WbFieldRef);
''')
            driver = folder / 'driver.cpp'
            driver.write_text('''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
static double now=0; static int forwarded=0;
extern "C" double wb_robot_get_time(){return now;}
extern "C" const char *__real_wb_robot_wwi_receive_text(){return nullptr;}
extern "C" void __real_gp_u_send(const char*,int){++forwarded;}
extern "C" const char *__wrap_wb_robot_wwi_receive_text();
extern "C" void __wrap_gp_u_send(const char*,int);
static void ack(const char *s){__wrap_gp_u_send(s,std::strlen(s)+1);}
int main(){
  assert(!__wrap_wb_robot_wwi_receive_text());
  const char *path=std::getenv("GP_ROUTE_PILOT_NATIVE_READY_OUT");
  assert(path);
  // Fake cues cannot trigger the one test TAKEOFF: no marker, wrong
  // course, missing timestamp, malformed/extra fields.
  { FILE *f=std::fopen(path,"wb"); assert(f);
    assert(std::fputs("NOT_READY\\n",f)>=0); assert(std::fclose(f)==0); }
  assert(!__wrap_wb_robot_wwi_receive_text());
  { FILE *f=std::fopen(path,"wb"); assert(f);
    assert(std::fputs("GP_ROUTE_PROBE_READY_V1 attempt=1 course=wrong time_ms=3072\\n",f)>=0);
    assert(std::fclose(f)==0); }
  assert(!__wrap_wb_robot_wwi_receive_text());
  { FILE *f=std::fopen(path,"wb"); assert(f);
    assert(std::fputs("GP_ROUTE_PROBE_READY_V1 attempt=1 course=gp-route-v2-L2000-2500-3000-TGD-s105-H2 time_ms=3073\\n",f)>=0);
    assert(std::fclose(f)==0); }
  assert(!__wrap_wb_robot_wwi_receive_text());
  { FILE *f=std::fopen(path,"wb"); assert(f);
    assert(std::fputs("GP_ROUTE_PROBE_READY_V1 attempt=1 course=gp-route-v2-L2000-2500-3000-TGD-s105-H2 time_ms=3072 extra\\n",f)>=0);
    assert(std::fclose(f)==0); }
  assert(!__wrap_wb_robot_wwi_receive_text());
  { FILE *f=std::fopen(path,"wb"); assert(f);
    assert(std::fputs("GP_ROUTE_PROBE_READY_V1 attempt=1 course=gp-route-v2-L2000-2500-3000-TGD-s105-H2 time_ms=3072\\n",f)>=0);
    assert(std::fclose(f)==0); }
  const char *takeoff=__wrap_wb_robot_wwi_receive_text();
  assert(takeoff && !std::strcmp(takeoff,"WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 TAKEOFF 0.4"));
  assert(!__wrap_wb_robot_wwi_receive_text());
  now=1.024;ack("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK");
  assert(!__wrap_wb_robot_wwi_receive_text());
  now=2.048;ack("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 OK");
  const char *reset=__wrap_wb_robot_wwi_receive_text();
  assert(reset && !std::strcmp(reset,"WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 RESET"));
  assert(!__wrap_wb_robot_wwi_receive_text());
  now=2.560;ack("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK");
  assert(!__wrap_wb_robot_wwi_receive_text());
  const auto second_path=std::string(path)+".second";
  const auto cue=[&](const char *line){
    FILE *f=std::fopen(second_path.c_str(),"wb"); assert(f);
    assert(std::fputs(line,f)>=0); assert(std::fclose(f)==0);
  };
  cue("GP_ROUTE_PROBE_READY_V1 attempt=1 course=gp-route-v2-L2000-2500-3000-TGD-s105-H2 time_ms=3072\\n");
  assert(!__wrap_wb_robot_wwi_receive_text());
  cue("GP_ROUTE_PROBE_READY_V1 attempt=2 course=gp-route-v2-L2000-2500-3000-TGD-s105-H2 time_ms=3000\\n");
  assert(!__wrap_wb_robot_wwi_receive_text());
  cue("GP_ROUTE_PROBE_READY_V1 attempt=2 course=gp-route-v2-L2000-2500-3000-TGD-s105-H2 time_ms=3072\\n");
  const char *second=__wrap_wb_robot_wwi_receive_text();
  assert(second && !std::strcmp(second,"WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 TAKEOFF 0.4"));
  assert(!__wrap_wb_robot_wwi_receive_text());
  now=4.096;ack("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK");
  assert(!__wrap_wb_robot_wwi_receive_text());assert(forwarded==4);
}
''')
            binary = folder / 'probe'
            subprocess.run(['g++', '-std=c++17', '-I', str(folder), str(driver),
                str(root / 'controllers/grand_prix_route_publisher_probe/grand_prix_route_publisher_probe.cpp'),
                '-o', str(binary)], check=True, capture_output=True, text=True)
            output = folder / 'acks.json'
            subprocess.run([str(binary)], check=True, capture_output=True,
                           env=dict(os.environ, GP_ROUTE_PILOT_ACK_OUT=str(output),
                                    GP_ROUTE_PILOT_NATIVE_READY_OUT=str(folder / 'ready.txt'),
                                    GP_ROUTE_PILOT_COURSE_ID=reference_course(5).identifier))
            import json
            self.assertEqual(json.loads(output.read_text()), dict(takeoff_ack_ms=1024,
                             land_ack_ms=2048, reset_ack_ms=2560, second_takeoff_ack_ms=4096))
            self.assertFalse(output.with_name('acks.json.pending').exists())

    def test_native_ready_record_requires_consistent_stability_and_revocation(self):
        from tools.ci.run_grand_prix_route_evaluator_native import check_native, CLAIM
        import copy
        good = dict(claim=CLAIM, configuration=reference_course(5).identifier,
            webots='R2025a', timestep_ms=8,
            ready=dict(time_ms=1120, stable_since_ms=616, sample_time_ms=1120,
                       ranges_m=[2.] * 5, position=[0., 0., .015], velocity=[0.] * 6,
                       contact_count=0), mutated_ms=1128, refused_ms=1128,
            restored_still_refused_ms=1160)
        # Parser shape tests only, never a real native claim.
        check_native(good)
        for mutation in ('absent', 'short-window', 'stale', 'no-revoke',
                         'prior-tick-mutation', 'nan', 'motion', 'range'):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(good)
                if mutation == 'absent': del bad['ready']
                elif mutation == 'short-window': bad['ready']['stable_since_ms'] = 624
                elif mutation == 'stale': bad['ready']['sample_time_ms'] = 1080
                elif mutation == 'no-revoke': bad['refused_ms'] += 8
                elif mutation == 'prior-tick-mutation': bad['mutated_ms'] -= 8
                elif mutation == 'nan': bad['ready']['position'][2] = float('nan')
                elif mutation == 'motion': bad['ready']['velocity'][3] = .11
                elif mutation == 'range': bad['ready']['ranges_m'][0] = 2.002
                with self.assertRaises(RuntimeError): check_native(bad)

    def test_zero_exit_without_native_bytes_refuses_and_keeps_diagnostics(self):
        from tools.ci import run_grand_prix_route_evaluator_native as runner
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            out = root / 'evidence'
            with patch.object(runner, 'OUT', out), patch.object(runner.subprocess, 'Popen') as spawned:
                spawned.return_value.wait.return_value = 0
                spawned.return_value.poll.return_value = 0
                with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                    runner.run_case(home, {}, 'idle')
                self.assertTrue(spawned.call_args.kwargs['start_new_session'])
            self.assertEqual(len(list(out.glob('*-invocation-*/native.log'))), 1)
            self.assertFalse(list(out.glob('*-invocation-*/sha256.json')))
            import stat
            self.assertEqual(stat.S_IMODE(next(out.glob('*-invocation-*')).stat().st_mode), 0o755)

    def test_native_flight_record_requires_failed_outcome_land_reset_and_second_takeoff(self):
        from tools.ci.run_grand_prix_route_evaluator_native import check_native, FLIGHT_CLAIM
        import copy
        def ready(now):
            return dict(time_ms=now, stable_since_ms=now - 504, sample_time_ms=now,
                        ranges_m=[2.] * 5, position=[0., 0., .015], velocity=[0.] * 6, contact_count=0)
        good = dict(claim=FLIGHT_CLAIM, configuration=reference_course(5).identifier,
            webots='R2025a', timestep_ms=8, ready=ready(1120), reset_ready=ready(5632),
            start_ms=1152, stalled_ms=2080, failure_observed_ms=2112, airborne_z=.4,
            fresh_epoch=True, acks=dict(takeoff_ack_ms=2048, land_ack_ms=4096, reset_ack_ms=4480,
                                        second_takeoff_ack_ms=7016),
            second_takeoff=dict(start_ms=5640, observed_ms=7024, airborne_z=.4))
        # API-shaped record only. The native runner additionally requires the
        # original C guard's LAND/ACK/RESET stdout and exact generated sources.
        check_native(good)
        for mutation in ('no-acks', 'land-before-failure', 'old-epoch', 'old-window', 'not-airborne',
                         'bad-clock', 'no-second-takeoff', 'stale-second-start', 'second-ack-in-future',
                         'second-not-airborne'):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(good)
                if mutation == 'no-acks': del bad['acks']
                elif mutation == 'land-before-failure': bad['acks']['land_ack_ms'] = 2064
                elif mutation == 'old-epoch': bad['fresh_epoch'] = False
                elif mutation == 'old-window': bad['reset_ready'] = ready(4680)
                elif mutation == 'not-airborne': bad['airborne_z'] = .015
                elif mutation == 'bad-clock': bad['start_ms'] = True
                elif mutation == 'no-second-takeoff': del bad['second_takeoff']
                elif mutation == 'stale-second-start': bad['second_takeoff']['start_ms'] = 5624
                elif mutation == 'second-ack-in-future': bad['acks']['second_takeoff_ack_ms'] = 7032
                elif mutation == 'second-not-airborne': bad['second_takeoff']['airborne_z'] = .015
                with self.assertRaises(RuntimeError): check_native(bad)


if __name__ == '__main__':
    unittest.main()
