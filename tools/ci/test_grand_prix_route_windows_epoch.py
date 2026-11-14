"""Fail-closed, source-exact checks for Windows route epoch composition."""
import unittest
from tools.grand_prix.route_windows_epoch import (
    ORIGINAL, HEADER, OLD, NEW, compose_route_windows_epoch,
)


class WindowsNativeRouteEpochTest(unittest.TestCase):
    def test_os_rng_source_locked_and_shared_source_unchanged(self):
        before = ORIGINAL.read_text(encoding="utf-8")
        after = compose_route_windows_epoch(before)
        self.assertEqual(before, ORIGINAL.read_text(encoding="utf-8"))
        self.assertEqual(after, compose_route_windows_epoch(before))
        self.assertIn("BCryptGenRandom(nullptr, epoch,", after)
        self.assertIn("BCRYPT_USE_SYSTEM_PREFERRED_RNG", after)
        self.assertIn("clearRouteEpoch();\n        return;", after)
        self.assertEqual(after.count("routeEpoch=token;routeConfig=config;"), 1)
        self.assertEqual(after.count("#else\n      std::random_device random;"), 1)
        self.assertIn("if(random.entropy()<=0)return;", after)
        self.assertIn("GP_ROUTE_CHALLENGE_V1 attempt=%llu", after)

    def test_fails_closed_on_upstream_or_replay(self):
        before = ORIGINAL.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            compose_route_windows_epoch(before.replace(OLD, "// no-epoch", 1))
        with self.assertRaises(ValueError):
            compose_route_windows_epoch(before.replace(HEADER, "", 1))
        with self.assertRaises(ValueError):
            compose_route_windows_epoch(compose_route_windows_epoch(before))


if __name__ == "__main__":
    unittest.main()
