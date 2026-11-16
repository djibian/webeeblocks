"""Prevent a stale A6 n=1 marker from masquerading as 3->1 admission."""
import unittest
from tools.ci.count_h_cdp_evidence import attest_visit


def response(index, symbol):
    return ("WEBEEBLOCKS_RUNTIME_V2 RESPONSE " + str(index + 1) +
            " SCENE_OK " + symbol * 64 + "\n")


def observer(n):
    return ("WEBEEBLOCKS_A6_MOTOR_READY n=" + str(n) +
            " origin_z=0.014980 colliders=" + str(3*n+2) + "\n")


class A6NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.seen = set()
        self.counts = {1: 0, 2: 0, 3: 0}

    def accept(self, trace, index, variant):
        result = attest_visit(trace, index, variant, self.counts, self.seen)
        self.assertIsNotNone(result)
        self.seen.add(result["nonce"])
        self.counts[variant] = result["ready_count"]
        return result

    def three_successes(self):
        trace = ""
        for index, variant, symbol in ((0, 1, "a"), (1, 2, "b"), (2, 3, "c")):
            trace += response(index, symbol) + observer(variant)
            self.accept(trace, index, variant)
        return trace

    def test_four_separate_native_scene_incarnations(self):
        trace = self.three_successes() + response(3, "d") + observer(1)
        last = self.accept(trace, 3, 1)
        self.assertEqual(last["request_id"], 4)
        self.assertEqual(last["ready_count"], 2)
        self.assertEqual(self.counts, {1: 2, 2: 1, 3: 1})
        self.assertEqual(len(self.seen), 4)

    def test_old_first_observer_cannot_certify_return_a(self):
        trace = self.three_successes()
        self.assertIsNone(attest_visit(trace, 3, 1, self.counts, self.seen))
        # Even with a valid fourth SCENE_OK, the old n=1 READY is stale.
        self.assertIsNone(attest_visit(
            trace + response(3, "d"), 3, 1, self.counts, self.seen))

    def test_new_observer_without_fourth_scene_ack_is_rejected(self):
        trace = self.three_successes() + observer(1)
        self.assertIsNone(attest_visit(trace, 3, 1, self.counts, self.seen))

    def test_nonce_reuse_fails(self):
        trace = self.three_successes() + response(3, "a") + observer(1)
        with self.assertRaisesRegex(AssertionError, "reused"):
            attest_visit(trace, 3, 1, self.counts, self.seen)

    def test_observer_prior_to_fourth_ack_cannot_certify_return(self):
        trace = self.three_successes() + observer(1) + response(3, "d")
        self.assertIsNone(attest_visit(trace, 3, 1, self.counts, self.seen))

    def test_duplicate_ack_or_observer_fails_closed(self):
        trace = self.three_successes()
        with self.assertRaisesRegex(AssertionError, "duplicate native SCENE_OK"):
            attest_visit(trace + response(3, "d") * 2 + observer(1),
                         3, 1, self.counts, self.seen)
        with self.assertRaisesRegex(AssertionError, "duplicate A6 native observer"):
            attest_visit(trace + response(3, "d") + observer(1) * 2,
                         3, 1, self.counts, self.seen)

    def test_wrong_request_id_never_certifies_return(self):
        trace = self.three_successes() + response(4, "d") + observer(1)
        self.assertIsNone(attest_visit(trace, 3, 1, self.counts, self.seen))


if __name__ == "__main__":
    unittest.main()
