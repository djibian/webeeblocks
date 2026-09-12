#!/usr/bin/env python3
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuity

JOURNAL = """CONTINUITY_V1 seq=1 event=CONTROLLER_STARTED pid=321
CONTINUITY_V1 seq=2 event=WB_INIT_RETURN time=0.000000
CONTINUITY_V1 seq=3 event=PROVIDER_CALLED
CONTINUITY_V1 seq=4 event=PROVIDER_RETURNED
CONTINUITY_V1 seq=5 event=LOOP_BEGIN time=0.000000
CONTINUITY_V1 seq=6 event=STEP n=1 result=0 time=0.032000
CONTINUITY_V1 seq=7 event=STEP n=2 result=0 time=0.064000
CONTINUITY_V1 seq=8 event=STEP n=3 result=0 time=0.096000
CONTINUITY_V1 seq=9 event=STEP n=4 result=0 time=0.128000
CONTINUITY_V1 seq=10 event=STEP n=5 result=0 time=0.160000
CONTINUITY_V1 seq=11 event=STEP n=6 result=0 time=0.192000
CONTINUITY_V1 seq=12 event=STEP n=7 result=0 time=0.224000
CONTINUITY_V1 seq=13 event=STEP n=8 result=0 time=0.256000
CONTINUITY_V1 seq=14 event=LOOP_END before=0.000000 after=0.256000
CONTINUITY_V1 seq=15 event=CAPABILITIES operationsReady=false
CONTINUITY_V1 seq=16 event=PROVIDER_DESTROYED
CONTINUITY_V1 seq=17 event=PRE_SHUTDOWN_READY
"""
LOG = """Q87 WB_INIT_RETURN
Q87 PROVIDER_CALLED
Q87 DIALOG_EXEC
Q87 DIALOG_EXPOSED pid=321 wid=987 width=600 height=400
Q87 DIALOG_CANCELLED result=Rejected
"""
WITNESS = {"pid": 321, "window": 987, "map_state": "IsViewable",
           "focus_verified": True, "cancel": "XTEST_ESCAPE"}


class ContinuityTests(unittest.TestCase):
    def test_exact_pre_shutdown_record_passes_synthetic_oracle(self):
        proof = continuity.parse_continuity(JOURNAL)
        self.assertIsNotNone(proof)
        self.assertEqual(continuity.evaluate(LOG, WITNESS, 0, True, True, proof, True), "PASS")

    def test_missing_or_refuting_evidence_never_passes(self):
        proof = continuity.parse_continuity(JOURNAL)
        self.assertIsNone(continuity.parse_continuity(JOURNAL.replace("event=PROVIDER_DESTROYED\n", "")))
        self.assertIsNone(continuity.parse_continuity(JOURNAL.replace("n=4 result=0", "n=4 result=-1")))
        self.assertEqual(continuity.evaluate(LOG, WITNESS, 0, True, True, None, True), "UNPROVEN")
        self.assertEqual(continuity.evaluate(LOG, WITNESS, 0, True, True, proof, False), "FAIL")
        self.assertEqual(continuity.evaluate(LOG, WITNESS, 1, True, True, proof, True), "FAIL")
        self.assertEqual(continuity.evaluate(LOG, WITNESS, 0, False, True, proof, True), "FAIL")
        self.assertEqual(continuity.evaluate(LOG + "Q87 FATAL\n", WITNESS, 139, True, True, proof, True), "FAIL")


if __name__ == "__main__":
    unittest.main()
