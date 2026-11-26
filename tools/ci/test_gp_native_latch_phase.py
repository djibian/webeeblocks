"""Parser-only checks: no simulated flight is inferred from fixtures."""
import json
import unittest

from tools.ci.gp_native_latch_phase import (
    OFFSETS, PhaseSchedule, ReboundUnproven, instrument_phase, verify_phase,
)
from tools.ci.a7_native_rebound import instrument_pilot
from tools.ci.test_a7_native_rebound import fixture_8ms
from tools.grand_prix.prepare_u_runtime import prepare
from pathlib import Path
import tempfile


class NativeLatchPhaseTests(unittest.TestCase):
    def test_instrumentation_is_isolated_and_requires_unique_anchors(self):
        with tempfile.TemporaryDirectory() as d:
            prepare(d, legacy_worlds=False, route_observations=True)
            product = (Path(d) / 'runtime_u.c').read_text()
            self.assertNotIn('gp_phase_mark', product)
            source = instrument_phase(instrument_pilot(product))
            self.assertEqual(source.count('gp_phase_mark("phase-land"'), 1)
            self.assertEqual(source.count('gp_phase_mark("phase-force"'), 1)
            self.assertEqual(source.count('gp_phase_mark("phase-tick"'), 1)
            with self.assertRaises(RuntimeError):
                instrument_phase(source)

    def test_non_requested_phase_cannot_pass(self):
        journal, ode, wwi = fixture_8ms('stop')
        with self.assertRaises(RuntimeError):
            verify_phase('stop', 16, journal, ode, wwi, 'gp-progression-v1-a7-v5')

    def test_missing_native_admission_cannot_pass(self):
        journal, ode, wwi = fixture_8ms('stop')
        with self.assertRaises(ReboundUnproven):
            verify_phase('stop', 0, journal, ode, wwi, 'gp-progression-v1-a7-v5')
