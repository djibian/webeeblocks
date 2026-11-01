"""Falsify the expired-attempt versus recovered-attempt evidence boundary."""
import copy
import json
import subprocess
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch
import run_grand_prix_u_prototype as runner
from run_grand_prix_u_prototype import validate_timeout_probe, native_webots_launch, has_native_land_completion
import run_grand_prix_u_geometry as geometry
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.grand_prix.prepare_u_runtime import prepare


def observations(accepted):
    rows=[{'event':'late-command-rejected','detail':{'command':c,'code':'TIME_LIMIT'}}
          for c in ('COMPLETE','FAILURE','MOVE')]
    rows += [{'event':'late-stop-rejected','detail':{'code':'TIME_LIMIT'}},
             {'event':'late-outcome-read','detail':{'status':'not-achieved'}},
             {'event':'request','detail':'WEBEEBLOCKS_RUNTIME_V2 REQUEST 71 RESET'}]
    if accepted:
        rows += [{'event':'recovery-reset-accepted','detail':{}},
                 {'event':'recovery-outcome-error','detail':{'code':'OUTCOME_UNAVAILABLE'}}]
    else:rows += [{'event':'recovery-reset-rejected','detail':{'code':'TIME_LIMIT'}}]
    return rows


NATIVE=('WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1\n'
        'WEBEEBLOCKS_RUNTIME_V2 TRACE RESET x=0 y=0 z=.015 origin_x=0 origin_y=0 origin_z=.015\n'
        'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 71 OK\n')


class TimeoutEvidenceTests(unittest.TestCase):
    def test_composed_broker_filters_before_any_reset_or_mission_dispatch(self):
        # The GP U compiler consumes the *actual* common broker after textual
        # composition. An early rejected RESET must never enter the broker's
        # pending-reset state; a rejected file operation must never create Qt.
        prepare()
        generated=(ROOT/'controllers/grand_prix_u_flight/build/file_broker_u.cpp').read_text()
        product=(ROOT/'controllers/crazyflie_runtime_v2/file_broker_runtime.cpp').read_text()
        receive='  while ((message = wb_robot_wwi_receive_text()) != nullptr) {'
        guard='    if (!gp_u_filter_raw(message)) continue;'
        reset='    if (resetRequestId(message, &resetId) && gPendingResetRequest < 1)'
        mission='    if (handleMissionCompletionRequest(message))'
        files='    if (!isBrokerMessage(message))'
        def prefiltered(source):
            if any(source.count(token)!=1 for token in (receive,guard,reset,mission,files)):
                return False
            after=source.split(receive,1)[1]
            return (after.startswith('\n'+guard+'\n') and
                    0<after.index(guard)<after.index(mission)<after.index(reset)<after.index(files))
        self.assertEqual(product.count('gp_u_filter_raw(message)'),0,
                         'the shared broker must not depend on Grand Prix U')
        self.assertTrue(prefiltered(generated),
                        'the generated U broker must reject requests before side effects')
        # Mutation controls: moving the filter after RESET bookkeeping, removing
        # it, or inserting two hooks must *each* fail this same contract.
        moved=generated.replace('\n'+guard+'\n','\n',1).replace(reset,reset+'\n'+guard,1)
        removed=generated.replace('\n'+guard+'\n','\n',1)
        doubled=generated.replace('\n'+guard+'\n','\n'+guard+'\n'+guard+'\n',1)
        for case,mutant in (('late-filter',moved),('missing-filter',removed),('double-filter',doubled)):
            with self.subTest(mutant=case):
                self.assertFalse(prefiltered(mutant),
                                 'broken Grand Prix filter placement escaped the oracle')

    def test_touchdown_does_not_prove_terminal_land(self):
        diagnostic = 'WEBEEBLOCKS_RUNTIME_V2 TRACE LAND_TOUCHDOWN time=212.3\n'
        self.assertTrue(has_native_land_completion(NATIVE))
        self.assertTrue(has_native_land_completion(diagnostic + NATIVE))
        for text in ('', diagnostic, diagnostic + 'command=LAND\n',
                     'WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=0\n',
                     'WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=10\n',
                     'WEBEEBLOCKS_RUNTIME_V2 TRACE LAND_TOUCHDOWN stop=1\n'):
            with self.subTest(text=text):
                self.assertFalse(has_native_land_completion(text))

    def test_geometry_real_launch_is_minimized_with_rendering_preserved(self):
        # Reach the actual Popen boundary of both supported native transports;
        # stop before launching Webots rather than faking perception evidence.
        for tcp in (False, True):
            with self.subTest(tcp=tcp), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / 'webots'
                (home / 'resources').mkdir(parents=True)
                (home / 'resources/version.txt').write_text('R2025a\n')
                (root / 'worlds').mkdir()
                with (patch.object(geometry, 'ROOT', root),
                      patch.object(geometry, 'OUT', root / 'evidence'),
                      patch.object(geometry, 'cases', return_value=[0]),
                      patch.object(geometry.subprocess, 'Popen',
                                   side_effect=RuntimeError('launch boundary')) as launch):
                    with self.assertRaisesRegex(RuntimeError, '^launch boundary$'):
                        geometry.run_native(home, tcp=tcp)
                argv = launch.call_args.args[0]
                self.assertEqual(argv, [str(home / 'webots'), '--stdout', '--stderr',
                    '--batch', '--mode=fast', '--minimize', '--port=1257',
                    str(root / 'worlds/ci_gp_u_geometry.wbt')])
                self.assertEqual(argv.count('--minimize'), 1)
                self.assertNotIn('--no-rendering', argv)
                self.assertFalse((root / 'evidence/summary.json').exists())
                self.assertFalse((root / 'worlds/ci_gp_u_geometry.wbt').exists())

    def test_minimize_world_progress_gui_keeps_native_launch_contract(self):
        actual=native_webots_launch(Path('/opt/webots'),12345,Path('/workspace/worlds/ci_gp_u.wbt'))
        self.assertEqual(actual,['/opt/webots/webots','--stdout','--stderr','--batch',
            '--mode=fast','--no-rendering','--minimize','--port=12345',
            '/workspace/worlds/ci_gp_u.wbt'])
        self.assertEqual(actual.count('--minimize'),1)

    def test_native_descent_and_confirmed_recovery_are_distinct(self):
        validate_timeout_probe(observations(False),'')
        validate_timeout_probe(observations(True),NATIVE)

    def test_early_reset_stale_outcomes_wrong_ids_and_continuation_fail(self):
        failures=[]
        for accepted in (False,True):
            rows=observations(accepted)
            bad=copy.deepcopy(rows);bad[0]={'event':'late-command-accepted','detail':{'command':'COMPLETE'}};failures.append((bad,NATIVE))
            bad=copy.deepcopy(rows);bad[4]['detail']['status']='achieved';failures.append((bad,NATIVE))
            bad=copy.deepcopy(rows);bad.insert(0,bad.pop(5));failures.append((bad,NATIVE))
            bad=copy.deepcopy(rows);bad.append({'event':'late-stop-accepted','detail':{}});failures.append((bad,NATIVE))
        for text in ('',NATIVE.replace('TRACE LAND stop=1','TRACE LAND stop=0'),
                     NATIVE.replace('TRACE LAND stop=1','TRACE LAND_TOUCHDOWN stop=1'),
                     NATIVE.replace('RESPONSE 71 OK','RESPONSE 72 OK'),
                     '\n'.join(reversed(NATIVE.splitlines()))):
            failures.append((observations(True),text))
        bad=observations(True);bad[-1]={'event':'recovery-stale-outcome','detail':{'status':'not-achieved'}};failures.append((bad,NATIVE))
        bad=observations(False);bad[-1]['detail']['code']='RESET_TIMEOUT';failures.append((bad,NATIVE))
        for rows,text in failures:
            with self.subTest(rows=rows,text=text),self.assertRaises(RuntimeError):
                validate_timeout_probe(rows,text)



class NormalQuitHostTests(unittest.TestCase):
    """Host-only refusal tests; native outcomes remain an independent CI obligation."""

    @staticmethod
    def prepare(root, attempts):
        (root/'events.jsonl').write_text('{}\n')
        (root/'result.json').write_text('{}')
        (root/'webots.log').write_text('GP_U_RESULT {}\n')
        for attempt in attempts:
            (root/f'native-result-{attempt}.json').write_text('{}')
            (root/f'native-diagnostic-{attempt}.json').write_text(json.dumps(
                {'time': 1.0, 'position': [0, 0, 0], 'velocity': [0, 0, 0]}))

    def test_normal_exit_follows_complete_second_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.prepare(root,[1,2])
            class Child:
                pid=123
                returncode=0
                def wait(self,timeout):
                    request=(root/'normal-quit.request').read_text()
                    assert request.split()[0]=='2'
                    (root/'normal-quit.ack').write_text(request)
            class Log:
                def finish(self):pass
            with patch.object(runner,'owned_process_group_state',return_value={'status':'empty','members':[]}):
                runner.normal_quit_after_validation(root,Child(),Log(),[1,2])
            self.assertTrue(json.loads((root/'normal-quit.json').read_text())['normal_success'])

    def test_missing_second_reset_proof_and_nonfinite_diagnostic_refuse_request(self):
        for failure in ('missing', 'nonfinite'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                self.prepare(root,[1,2])
                diagnostic=root/'native-diagnostic-2.json'
                if failure=='missing': diagnostic.unlink()
                else: diagnostic.write_text('{"time": NaN, "position":[0,0,0], "velocity":[0,0,0]}')
                with self.assertRaises((OSError,ValueError)):
                    runner.normal_quit_after_validation(root,None,None,[1,2])
                self.assertFalse((root/'normal-quit.request').exists())

    def test_refuses_every_unproven_retirement(self):
        for fault in ('timeout','exit','ack','crash','eof','mutation','survivor','census-unknown'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                self.prepare(root,[1])
                class Child:
                    pid=123
                    returncode=139 if fault=='exit' else 0
                    def wait(self,timeout):
                        if fault=='timeout':raise subprocess.TimeoutExpired('webots',timeout)
                        request=(root/'normal-quit.request').read_text()
                        (root/'normal-quit.ack').write_text('invalid' if fault=='ack' else request)
                        if fault=='mutation':(root/'native-result-1.json').write_text('{"mutated":true}')
                        if fault=='crash':(root/'webots.log').write_text('malloc(): corrupted\n')
                def finish():
                    if fault=='eof':raise RuntimeError('stdout still held')
                group = ({'status':'unknown','reason':'proc-list:OSError'} if fault=='census-unknown'
                         else {'status':'nonempty','members':[{'pid':9}]} if fault=='survivor'
                         else {'status':'empty','members':[]})
                with (patch.object(runner,'owned_process_group_state',return_value=group),
                     patch.object(runner.time,'monotonic',side_effect=[0,3] if fault=='survivor' else [0]),
                     self.assertRaises(Exception)):
                    runner.normal_quit_after_validation(root,Child(),SimpleNamespace(finish=finish),[1])
                self.assertFalse(json.loads((root/'normal-quit.json').read_text())['normal_success'])

    def test_owned_group_census_refuses_unreadable_or_partial_proc(self):
        with patch.object(runner.os,'listdir',side_effect=PermissionError('proc unavailable')):
            self.assertEqual(runner.owned_process_group_state(123)['status'],'unknown')
        for data in (OSError('stat unreadable'),'incomplete stat'):
            with self.subTest(data=str(data)), patch.object(runner.os,'listdir',return_value=['789']):
                with patch.object(runner.Path,'read_text',side_effect=data if isinstance(data,Exception) else None,
                                  return_value=None if isinstance(data,Exception) else data):
                    self.assertEqual(runner.owned_process_group_state(123)['status'],'unknown')

    def test_owned_group_census_requires_kernel_confirmation(self):
        with (patch.object(runner.os,'listdir',return_value=['789']),
              patch.object(runner.Path,'read_text',return_value='789 (other) S 1 1 1 0 0 0')):
            with patch.object(runner.os,'killpg',side_effect=ProcessLookupError()):
                self.assertEqual(runner.owned_process_group_state(123)['status'],'empty')
            with patch.object(runner.os,'killpg',return_value=None):
                self.assertEqual(runner.owned_process_group_state(123)['status'],'nonempty')
            with patch.object(runner.os,'killpg',side_effect=PermissionError()):
                self.assertEqual(runner.owned_process_group_state(123)['status'],'unknown')
        with (patch.object(runner.os,'listdir',return_value=['789']),
              patch.object(runner.Path,'read_text',return_value='789 (webots) S 1 123 123 0 0 0'),
              patch.object(runner.os,'killpg') as kernel):
            self.assertEqual(runner.owned_process_group_state(123)['status'],'nonempty')
            kernel.assert_not_called()

    def test_unknown_group_preserves_original_retirement_and_refuses_success_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.prepare(root,[1])
            world=root/'world.wbt'
            class Child:
                pid=123
                returncode=0
                def wait(self,timeout):
                    request=(root/'normal-quit.request').read_text()
                    (root/'normal-quit.ack').write_text(request)
            child=Child()
            log=SimpleNamespace(finish=lambda:None)
            runtime=SimpleNamespace(cleanup=lambda:None)
            with (patch.object(runner,'owned_process_group_state',
                               return_value={'status':'unknown','reason':'proc-list:OSError'}),
                  patch.object(runner,'stop_groups',side_effect=RuntimeError('retirement cannot be verified')) as stop):
                with self.assertRaisesRegex(RuntimeError,'membership unobservable'):
                    try:
                        runner.normal_quit_after_validation(root,child,log,[1])
                    finally:
                        runner.retire_trial([child],log,None,[],runtime,root,world)
            stop.assert_called_once_with([child])
            self.assertFalse(json.loads((root/'normal-quit.json').read_text())['normal_success'])
            self.assertFalse((root/'sha256.json').exists())

    def test_native_non_tcp_cases_enable_graceful_quit_without_changing_tcp_or_camera(self):
        source=(ROOT/'tools/ci/run_grand_prix_u_prototype.py').read_text()
        trial=source.split('def trial(',1)[1].split('\ndef retire_trial(',1)[0]
        gate=trial.index('normal_quit_after_validation(out,')
        for anchor in ('second identical program after native RESET failed',
                       'missing independent forced LAND/failure','wrong native subject',
                       "(out/'result.json').write_text"):
            self.assertLess(trial.index(anchor),gate)
        self.assertIn("normal_quit=not args.tcp",source)
        self.assertIn("children[1:] if normal_quit_confirmed else children",source)
        self.assertIn("if camera_probe is not None:",trial[:gate])

if __name__=='__main__':unittest.main()
