#!/usr/bin/env python3
"""Refutation oracles for conditional #70 reachability and depth ambiguity."""
import importlib.util
import itertools
import json
import math
from pathlib import Path
import random
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'experiments/crazyflie-c-feasibility'
spec = importlib.util.spec_from_file_location('c_budget', LAB / 'budget.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BudgetTests(unittest.TestCase):
    def test_inertial_closed_form_and_continuous_horizon(self):
        for t in (1., 2., 4., 8.):
            result = b.vertical_envelope(t, omega=0)
            analytic = .005+.02*t+.5*b.G*.001*t*t
            self.assertAlmostEqual(result['terminal_z_m'], analytic, places=12)
            self.assertAlmostEqual(result['maximum_sampled_z_m'], analytic, places=12)
            self.assertAlmostEqual(result['continuous_enclosure_z_m'], analytic, places=12)

    def test_tiny_horizon_exhaustive_independent_box_oracle(self):
        # Enumerate all signs of initial Z/V, three acceleration errors and
        # the one pressure correction. The oracle is a scalar forward replay.
        values = []
        for sz, sv, sa, sb, sc, sp in itertools.product((-1, 1), repeat=6):
            z, v = sz*.005, sv*.02
            for step, sign in enumerate((sa, sb, sc), 1):
                z, v = z + .01*v + .00005*sign*.02, v+.01*sign*.02
                if step == 2:
                    residual = sp*.3-z
                    z, v = z+.0004*residual, v+.000002*residual
            values.append(abs(z))
        result = b.vertical_envelope(.03, acceleration=.02)
        self.assertAlmostEqual(result['terminal_z_m'], max(values), places=14)

    def test_backward_adversary_attains_forward_support(self):
        for t, omega in ((2., 0.), (8., .01), (2., .1)):
            w = b.terminal_witness(t, .01, omega, .005, .02, b.G*.001, .3)
            r = b.vertical_envelope(t, omega=omega)
            self.assertAlmostEqual(w['support_m'], r['terminal_z_m'], places=11)
            self.assertAlmostEqual(w['replay_terminal_z_m'], w['support_m'], places=11)

    def test_recovery_is_part_of_lifetime_without_reset(self):
        e4 = b.vertical_envelope(4., omega=0)['terminal_z_m']
        e6 = b.vertical_envelope(6., omega=0)['terminal_z_m']
        self.assertGreater(e6, 1.7*e4)
        # Reanchoring at the second edge cannot replace continuous propagation.
        self.assertGreater(e6, b.vertical_envelope(2., omega=0)['terminal_z_m'])

    def test_gyro_projection_bound_attained_by_aligned_force(self):
        for theta in (0., .001, .1, .5):
            # True force (-H,0,g+V), estimated vertical (sin(theta),0,cos(theta)).
            error = abs(-2*math.sin(theta)+(b.G+.5)*(math.cos(theta)-1))
            self.assertAlmostEqual(b.projection_bound(.01, 2., .5, theta), .01+error)
        r = b.vertical_envelope(4., tilt0=.001, gyro_rate=.002, horizontal=1.)
        self.assertGreater(r['terminal_z_m'], b.vertical_envelope(4.)['terminal_z_m'])

    def test_sampled_random_trajectories_remain_inside_enclosure(self):
        rng = random.Random(70)
        bound = b.vertical_envelope(.2, acceleration=.03)
        for _ in range(40):
            z, v = rng.uniform(-.005,.005), rng.uniform(-.02,.02)
            peak = abs(z)
            for step in range(1, 21):
                ea = rng.uniform(-.03,.03)
                for fraction in (.25,.5,.75,1.):
                    h = .01*fraction
                    peak = max(peak, abs(z+h*v+.5*h*h*ea))
                z, v = z+.01*v+.00005*ea, v+.01*ea
                if step % 2 == 0:
                    residual = rng.uniform(-.3,.3)-z
                    z, v = z+.0004*residual, v+.000002*residual
                    peak = max(peak, abs(z))
            self.assertLessEqual(peak, bound['continuous_enclosure_z_m']+1e-14)

    def test_flow_interval_covers_every_convex_depth_weight_and_sign(self):
        for q in (-1., 0., 1.):
            low, high = b.flow_interval(q, .35, 1.1, .02)
            for weight in (0., .01, .2, .5, .9, 1.):
                inv_depth = weight/.35+(1-weight)/1.1
                for n in (-.02, 0., .02):
                    v = (q-n)/inv_depth
                    self.assertLessEqual(low-1e-14, v)
                    self.assertGreaterEqual(high+1e-14, v)
        self.assertEqual(b.flow_interval(1., .5, .5), (.5, .5))

    def test_horizontal_indistinguishability_with_exact_initial_state(self):
        pair = b.horizontal_pair(2.)
        q = pair['angular_rate_rad_s']
        a = pair['acceleration_error_bound_m_s2']
        for sample in pair['samples']:
            for w in sample['worlds']:
                self.assertAlmostEqual(w['reconstructed_q'], q, places=14)
                self.assertAlmostEqual(w['true_a']+w['acceleration_error'], 0., places=14)
                self.assertLessEqual(abs(w['acceleration_error']), a)
                self.assertGreater(w['near_weight'], 0.)
                self.assertLess(w['near_weight'], 1.)
        first, last = pair['samples'][0]['worlds'], pair['samples'][-1]['worlds']
        self.assertEqual(first[0]['x_m'], first[1]['x_m'])
        self.assertEqual(first[0]['v_m_s'], first[1]['v_m_s'])
        half_separation = (last[1]['x_m']-last[0]['x_m'])/2
        self.assertAlmostEqual(half_separation, pair['worst_case_position_error_lower_bound_m'])
        self.assertGreater(half_separation, .05)

    def test_bad_bounds_do_not_become_optimistic_results(self):
        for value in (-1., float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                b.vertical_envelope(2., acceleration=value)
            with self.assertRaises(ValueError):
                b.flow_interval(1., value, 2.)
        with self.assertRaises(ValueError):
            b.flow_interval(1., 0., 2.)
        with self.assertRaises(ValueError):
            b.horizontal_pair(20.)
        with self.assertRaises(ValueError):
            b.vertical_envelope(2.001)
        with self.assertRaises(ValueError):
            b.vertical_envelope(2., tilt0=math.pi)

    def test_retained_numerical_evidence_matches_recomputation(self):
        retained = (LAB/'results.json').read_text(encoding='utf-8')
        current = b.canonical_report()
        self.assertEqual(retained, current)
        b.verify_retained(retained)
        tampered = json.loads(retained)
        tampered['vertical']['C2_8s']['continuous_enclosure_z_m'] = .005
        with self.assertRaisesRegex(ValueError, 'differ from recomputation'):
            b.verify_retained(json.dumps(tampered, indent=2, sort_keys=True)+'\n')

    def test_canonical_ci_executes_this_oracle(self):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
        block = workflow.split('- name: Verify selector and repository contracts', 1)[1]
        block = block.split('- name: Select required suites', 1)[0]
        self.assertIn('          python3 tools/ci/test_workflow_contract.py\n', block)
        contract = (ROOT / 'tools/ci/test_workflow_contract.py').read_text(encoding='utf-8')
        runner = contract.split(
            '    def test_c_feasibility_oracle_runs_in_mandatory_select_job(self)', 1
        )[1].split('\n    def ', 1)[0]
        self.assertIn('subprocess.run(', runner)
        self.assertIn('str(ROOT / "tools/ci/test_c_feasibility.py")', runner)
        self.assertIn('check=True', runner)

    def test_narrow_domain_can_pass_model_budget_without_qualifying_drone(self):
        r = b.vertical_envelope(8., omega=.5, z0=.002, v0=.002,
                               acceleration=b.G*.0002, pressure=.01)
        self.assertLess(r['continuous_enclosure_z_m'], .02)
        w = b.terminal_witness(8., .01, .5, .002, .002, b.G*.0002, .01)
        self.assertAlmostEqual(w['support_m'], r['terminal_z_m'], places=11)


if __name__ == '__main__':
    unittest.main()
