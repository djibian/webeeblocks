"""Fail-closed synthetic checks of native LAND/contact forensic pairing."""
import unittest

from land_contact_summary import LAND, NATIVE, summarize


def sample(t, contact=0, status="OBSERVED", native_id=12, z=.015,
           pitch=0.0, vx=0.0):
    flight = (f"{LAND} id=12 t={t:.9f} x=.175 y=0 z={z} vx={vx} vy=0 vz=-.6 "
              f"roll=0 pitch={pitch} des_vx=0 des_vy=0 des_z=.015 "
              "motor1=55 motor2=55 motor3=55 motor4=55")
    count = f"{NATIVE} id={native_id} t={t:.9f} status={status} contacts={contact} shown={min(contact, 6)}"
    if status == "OBSERVED":
        count += " velocity=0,0,0,0,0,0"
        for i in range(min(contact, 6)):
            count += f" cp{i}={i}:.1,.2,.0"
    return flight + "\n" + count + "\n"


class LandingContactSummaryTests(unittest.TestCase):
    def test_first_contact_and_next_physical_sample_are_not_outcome(self):
        log = "unrelated event\n" + sample(12.416) + sample(12.448, 1) + sample(12.480, 2, vx=.2, pitch=.42)
        result = summarize(log, 12)
        self.assertEqual(result["samples"], 3)
        self.assertEqual(result["first_observed_contact"]["t"], 12.448)
        self.assertEqual(result["first_observed_contact"]["contacts"], 1)
        self.assertAlmostEqual(result["next_sample"]["vx"], .2)
        self.assertEqual(result["next_sample"]["pitch"], .42)
        self.assertIn("no impulse, causality", result["scope"])

    def test_unproven_before_contact_cannot_be_treated_as_contact_free(self):
        result = summarize(sample(12.416, 0, "UNPROVEN") + sample(12.448, 1), 12)
        self.assertTrue(result["unknown_before_first_observed_contact"])
        self.assertEqual(result["unproven_samples"], 1)
        self.assertEqual(result["first_observed_contact"]["t"], 12.448)

    def test_unavailable_native_contact_list_remains_unproven(self):
        result = summarize(sample(12.416, -1, "UNPROVEN") + sample(12.448, 1), 12)
        self.assertTrue(result["unknown_before_first_observed_contact"])
        self.assertEqual(result["unproven_samples"], 1)
        self.assertEqual(result["first_observed_contact"]["t"], 12.448)
        invalid = sample(12.416, -1, "OBSERVED")
        with self.assertRaises(ValueError):
            summarize(invalid, 12)

    def test_zero_contacts_does_not_invent_first_contact(self):
        result = summarize(sample(12.416) + sample(12.448), 12)
        self.assertIsNone(result["first_observed_contact"])
        self.assertIsNone(result["next_sample"])

    def test_mismatched_pair_truncation_nonfinite_and_missing_geometry_fail(self):
        bad = [
            sample(12.416, 1, native_id=13),
            sample(12.416).splitlines()[0],
            sample(12.416).replace("vx=0.0", "vx=nan"),
            sample(12.416, 1).replace(" cp0=0:.1,.2,.0", ""),
            sample(12.416) + sample(12.416),
            sample(12.416, status="OBSERVED").replace(" velocity=0,0,0,0,0,0", ""),
        ]
        for log in bad:
            with self.subTest(log=log[:90]), self.assertRaises(ValueError):
                summarize(log, 12)

    def test_never_substitute_another_request(self):
        with self.assertRaises(ValueError):
            summarize(sample(12.416), 53)


if __name__ == "__main__":
    unittest.main()
