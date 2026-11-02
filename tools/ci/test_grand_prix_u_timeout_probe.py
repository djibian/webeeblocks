"""Falsify the expired-attempt versus recovered-attempt evidence boundary."""
import copy
import unittest
import tempfile
from unittest.mock import patch
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
        # R3_GP_TWO_LAYER_STATIC_CONTRACT: the native C runtime owns admission.
        # The separate file namespace remains fenced BEFORE Qt/provider effects.
        # The old raw-runtime prefilter expectation became unsafe with AUTH R3.
        prepare()
        generated=(ROOT/'controllers/grand_prix_u_flight/build/file_broker_u.cpp').read_text()
        product=(ROOT/'controllers/crazyflie_runtime_v2/file_broker_runtime.cpp').read_text()
        runtime=(ROOT/'controllers/grand_prix_u_flight/build/runtime_u.c').read_text()
        shared=(ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c').read_text()
        guard='    if (isBrokerMessage(message) && !gp_u_filter_raw(message)) continue;'
        receive='  while ((message = wb_robot_wwi_receive_text()) != nullptr) {'
        admission='if (request.kind != REQUEST_RANGE && request.kind != REQUEST_ELAPSED && !authenticated)'
        replay='if (authenticated && request.id <= last_owner_id)'
        consumed='last_owner_id = request.id;'
        recovery='int recovery_state = wb_rg_refresh(&recovery_guard);'
        gp='if (!gp_u_filter_raw(effective_message))'
        mission='webeeblocks_file_broker_authorized_mission(effective_message)'
        reset='webeeblocks_file_broker_record_admitted_reset(request.id)'
        stop='if (request.kind == REQUEST_STOP) {'
        reset_effect='if (request.kind == REQUEST_RESET) {'

        def protected(broker, controller):
            try:
                assert broker.count(receive)==1 and broker.count(guard)==1
                section=broker.split(receive,1)[1].split(
                    'extern "C" int webeeblocks_file_broker_authorized_mission',1)[0]
                assert section.startswith('\n'+guard+'\n')
                files=section.index('if (!isBrokerMessage(message))')
                provider=section.index('wb_file_broker_create_qt()')
                assert 0<section.index(guard)<files<provider
                # Raw Robot Window requests must reach C unmodified; no
                # mission publication or RESET attempt bookkeeping in the loop.
                assert 'handleMissionCompletionRequest(message)' not in section
                assert 'handleMissionFailureProbeRequest(message)' not in section
                assert 'handleOutcomeRequest(message)' not in section
                assert 'gPendingResetRequest = resetId' not in section
                assert controller.count(gp)==1 and controller.count(mission)==1
                assert controller.count(reset)==1
                assert '\n#ifdef WEBEEBLOCKS_GP_U_HOOK_H\n      '+gp in controller
                tokens=(admission,replay,consumed,recovery,gp,mission,reset,stop,reset_effect)
                positions=[controller.index(token) for token in tokens]
                assert positions==sorted(positions) and len(set(positions))==len(positions)
                return True
            except (ValueError,AssertionError):
                return False

        self.assertNotIn('gp_u_filter_raw(',product,
                         'shared broker must stay independent of the GP profile')
        self.assertTrue(protected(generated,runtime),
                        'native R3 admission must precede GP and mission effects; '
                        'file access must be fenced before Qt')
        # Keep the compiler's shared source equivalent to the original C
        # dispatch for these security-critical gates.
        for marker in (admission,replay,consumed,recovery,gp,mission,reset,stop,reset_effect):
            self.assertIn(marker,shared)
        # Mutant controls: no acceptance if the file fence moves after provider
        # access, disappears, doubles, or if the native guard is moved after
        # the admitted pedagogical effect / bypassed.
        missing=generated.replace(guard,'',1)
        late=missing.replace('    if (!gBroker)',guard+'\n    if (!gBroker)',1)
        doubled=generated.replace(guard,guard+'\n'+guard,1)
        missing_gp=runtime.replace(gp,'if (1)',1)
        late_gp=runtime.replace('\n      '+gp,'',1).replace(
            '      if (request.kind == REQUEST_STOP) {',
            '      '+gp+'\n      if (request.kind == REQUEST_STOP) {',1)
        early_mission=runtime.replace(mission,'0',1).replace(
            '      '+gp,
            '      '+mission+';\n      '+gp,1)
        for name,broker,controller in (
            ('missing-file-fence',missing,runtime),
            ('late-file-fence',late,runtime),
            ('double-file-fence',doubled,runtime),
            ('bypassed-runtime-guard',generated,missing_gp),
            ('late-runtime-guard',generated,late_gp),
            ('early-mission',generated,early_mission)):
            with self.subTest(mutant=name):
                self.assertFalse(protected(broker,controller),
                                 'unsafe R3/GP mutation passed the composition contract')

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


if __name__=='__main__':unittest.main()
