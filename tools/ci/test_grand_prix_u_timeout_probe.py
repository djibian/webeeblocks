"""Falsify the expired-attempt versus recovered-attempt evidence boundary."""
import copy
import unittest
import tempfile
from unittest.mock import patch
from run_grand_prix_u_prototype import validate_timeout_probe, native_webots_launch, has_native_land_completion
import run_grand_prix_u_geometry as geometry
from pathlib import Path


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
