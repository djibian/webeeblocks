import copy
import importlib.util
import json
from pathlib import Path
import unittest
from analyze import summarize
from instrument import instrument
ROOT=Path(__file__).resolve().parents[2]

class EvidenceTests(unittest.TestCase):
    def test_transform_only_inserts_two_print_statements(self):
        import subprocess
        source=subprocess.check_output(['git','show','HEAD:controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'],cwd=ROOT,text=True)
        original=source
        result=instrument(source)
        import re
        stripped=re.sub(r'(?m)^[ \t]*fprintf\(stderr, PREFIX " RESET_PHASE_(?:BEGIN|SAMPLE).*?;\n','',result,flags=re.S)
        self.assertEqual(stripped,original)
        for altered in ('',source.replace('if (!pose_ready)','if (pose_ready)')):
            with self.assertRaises(ValueError):instrument(altered)

    def test_receipt_jump_then_stability_and_adverse_evidence(self):
        # A teleport crossing is intentionally bad motion; it cannot synthesize
        # the later stable window. A completed ACK alone must remain insufficient.
        begin='WEBEEBLOCKS_RUNTIME_V2 RESET_PHASE_BEGIN id=7 time=10 origin=0,0,.015 origin_rpy=0,0,0\n'
        def sample(t,pos,prev,velocity,pose,motion,stable):
            return f'WEBEEBLOCKS_RUNTIME_V2 RESET_PHASE_SAMPLE id=7 time={t:.9f} elapsed={t-10:.9f} dt=.032 position={pos} previous={prev} rpy=0,0,0 gyro=0,0,0 velocity={velocity} pose_ready={pose} motion_ready={motion} stable_since={stable}\n'
        rows=[sample(10,'1,0,.015','1,0,.015','0,0,0',0,1,-1),
              sample(10.032,'0,0,.015','1,0,.015','-31.25,0,0',1,0,-1)]
        rows += [sample(10.064+i*.032,'0,0,.015','0,0,.015','0,0,0',1,1,-1 if i==0 else 10.064) for i in range(9)]
        text=begin+''.join(rows)+'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 7 OK\n'
        result=summarize(text)['resets'][0]
        self.assertAlmostEqual(result['final_stable_span'],.256)
        for altered in (text.replace(begin,''), text.replace('id=7 time=10.032','id=8 time=10.032'),
                        text.replace('elapsed=0.032','elapsed=0.096'),
                        text.replace('velocity=-31.25','velocity=-30'),
                        text.replace('pose_ready=0','pose_ready=1'),
                        text.replace('stable_since=10.064','stable_since=10.096'),
                        begin+''.join(rows[:4])+'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 7 OK\n',
                        text.replace('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 7 OK','')):
            with self.assertRaises(ValueError):summarize(altered)

if __name__=='__main__':unittest.main()
