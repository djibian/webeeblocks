"""Pure scene-generation assertions, not a native sensor/contact qualification."""
import itertools
import unittest

from tools.grand_prix.route_v2 import build_route
from tools.grand_prix.terminal_static_probe_v2 import static_l_terminal_probe_world
from tools.grand_prix.route_terminal_v2 import terminal_boxes


class StaticLTerminalProbeTests(unittest.TestCase):
    def test_all_turns_and_lengths_have_complete_static_physical_inventory(self):
        seen = set()
        for lengths in itertools.product((2.0, 2.5, 3.0), repeat=3):
            for turns in itertools.product(("G", "D"), repeat=2):
                route = build_route(17, lengths, turns)
                seen.add(route.identifier)
                scene = static_l_terminal_probe_world(route)
                self.assertEqual(scene, static_l_terminal_probe_world(route))
                self.assertIn("basicTimeStep 8", scene)
                self.assertEqual(scene.count('EXTERNPROTO "webots://'), 4)
                self.assertEqual(scene.count("DEF GP_V2_L_"), 4)
                self.assertEqual(scene.count("DEF GP_V2_FINAL_"), 4)
                self.assertEqual(scene.count("boundingObject Box { size "), 8)
                self.assertIn('controller "<none>"', scene)
                self.assertIn('window "<none>"', scene)
                self.assertNotIn("DEF GP_V2_RED_", scene)
                self.assertNotIn("GP_ROUTE_EVALUATOR", scene)
                self.assertNotIn('controller "grand_prix_u_flight"', scene)
                self.assertIn("STATIC PROBE (not a mission)", scene)
                for box in terminal_boxes(route):
                    self.assertEqual(scene.count("DEF " + box.name + " Solid {"), 1)
                    self.assertIn(box.vrml(), scene)
        self.assertEqual(len(seen), 108)

    def test_rejects_non_routes(self):
        for invalid in (None, True, object(), (), "gp-route-v2"):
            with self.assertRaises(TypeError):
                static_l_terminal_probe_world(invalid)
