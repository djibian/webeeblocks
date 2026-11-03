"""Pure offline checks; these are not native Webots qualifications."""
import unittest
from analyze import diagnose


def sample():
    s = dict(valid="1", enabled="1", gravity_mode="0", joints="0",
             contacts="0", joint_truncated="0", has_after="1",
             mass="0.05", linear_damping="0", angular_damping="0",
             max_angular_speed="inf")
    for prefix, values in (
        ("g", [0, 0, 0]), ("p", [0, 0, 0]),
        ("r", [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]),
        ("v", [0, 0, 0]), ("w", [0, 0, 0]),
        ("f", [0, 0, 0]), ("t", [0, .01, 0]),
        ("I", [3.5e-5, 0, 0, 0, 0, 3.5e-5, 0, 0, 0, 0, 3.5e-5, 0])):
        s.update({f"{prefix}{i}": str(v) for i, v in enumerate(values)})
    return s


class WrenchAnalysis(unittest.TestCase):
    def test_known_free_torque(self):
        p, q = sample(), sample()
        q["w1"] = str(.032 * .01 / 3.5e-5)
        x = diagnose(p, q, .032)
        self.assertEqual(x["status"], "MEASURED")
        self.assertLess(x["torque_norm_Nm"], 1e-12)

    def test_contact_like_residual_is_not_attributed(self):
        p, q = sample(), sample()
        p["contacts"] = "1"
        q["w1"] = "1"
        x = diagnose(p, q, .032)
        self.assertEqual(x["status"], "MEASURED")
        self.assertGreater(x["torque_norm_Nm"], .008)
        self.assertNotIn("contact_cause", x)

    def test_unknown_reset_and_clamp(self):
        p, q = sample(), sample()
        p["enabled"] = "0"
        self.assertEqual(diagnose(p, q, .032)["status"], "INDETERMINATE")
        p = sample()
        q["w1"] = "2"
        p["max_angular_speed"] = "1"
        self.assertEqual(diagnose(p, q, .032)["status"], "INDETERMINATE")


if __name__ == "__main__":
    unittest.main()
