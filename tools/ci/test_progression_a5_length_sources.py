#!/usr/bin/env python3
"""A5 physical L length × direction SOURCE contract, not native PASS.

The only active sensor oracle remains separate until R2025a samples the
four new worlds. This test prevents fake length variation via labels or
pure visuals and checks exactly which immutable original objects moved.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCENES=ROOT/"worlds/scenes"
CONFIG={
    "short":{"wall":"2.900","arm":"1.975","width":"1.250",
             "boundary":"2.800","pad":"3.950","mark":"2.300"},
    "long":{"wall":"3.300","arm":"2.175","width":"1.650",
            "boundary":"3.200","pad":"4.350","mark":"2.700"}
}

def source(length,side):
    if length not in CONFIG or side not in ("left","right"):
        raise ValueError("not a known physical L hypothesis")
    return (SCENES/f"reactive-L-length-{length}-g{side}-proto.wbo").read_text()

def reference(length,side):
    if length not in CONFIG or side not in ("left","right"):
        raise ValueError("not a known physical L hypothesis")
    v=CONFIG[length]
    base=(SCENES/f"reactive-L-factor-hnear-g{side}-proto.wbo").read_text()
    letter="L" if side=="left" else "R"
    replacements=(
      (f"# A5 isolated source prototype: H fixed / G {side}, NOT a pupil scene.",
       f"# A5 DRAFT ONLY: original Crazyflie H-near, G-{side}, {length} physical L. Not published.",1),
      ("# Real R2025a sensor and motor tests are REQUIRED; coordinates are a hypothesis.",
       "# R2025a native sensor and motor evidence required; NOT an oracle or released activity.",1),
      ("# Same initial H cue, same pads, same stage; only G side varies.",
       "# Physical G L-arm starts x=1.350, terminates x=gate-0.300; length and gate position vary.",1),
      (f"DEF WEBEEBLOCKS_A5_FACTOR_G{letter}_SCENE Group {{",
       f"DEF WEBEEBLOCKS_A5_LENGTH_{length.upper()}_G{letter}_SCENE Group {{",1),
      ("translation 2.500 0.000 0.002",
       f"translation {v['mark']} 0.000 0.002",1),
      ("translation 4.150 ",f"translation {v['pad']} ",2),
      ("translation 3.100 ",f"translation {v['wall']} ",2),
      ("translation 2.450 ",f"translation {v['arm']} ",1),
      ("size 0.700 0.080 1.100",
       f"size {v['width']} 0.080 1.100",2),
      ("translation 3.000 ",f"translation {v['boundary']} ",2))
    for old,new,n in replacements:
        assert base.count(old)==n,(length,side,old,base.count(old))
        base=base.replace(old,new)
    return base

class PhysicalLSourceContract(unittest.TestCase):
    def test_only_exact_original_crazyflie_fixtures_are_permitted(self):
        for length in CONFIG:
            for side in ("left","right"):
                with self.subTest(length=length,side=side):
                    s=source(length,side)
                    self.assertEqual(s,reference(length,side))
                    self.assertEqual(s.count(" Solid {"),7)
                    self.assertEqual(s.count("boundingObject Box"),7)
                    self.assertEqual(s.count(" Pose {"),4)
                    self.assertEqual(s.count("DEF A5_FACTOR_"),7)
                    self.assertNotIn('controller "',s)
                    self.assertNotIn(" Robot {",s)
                    self.assertNotIn("USE ",s)
                    self.assertIn("Not published.",s)
                    self.assertIn(
                      f"WEBEEBLOCKS_A5_LENGTH_{length.upper()}_G"
                      f"{'L' if side=='left' else 'R'}_SCENE Group",s)

    def test_length_is_native_collision_geometry_not_just_markers(self):
        for length,params in CONFIG.items():
            for side in ("left","right"):
                s=source(length,side)
                self.assertIn(
                    f"translation {params['arm']} "
                    f"{'-0.580' if side=='left' else '0.580'} 0.550",s)
                self.assertEqual(
                    s.count(f"size {params['width']} 0.080 1.100"),2)
                self.assertEqual(s.count(
                    f"translation {params['wall']} "),2)
                self.assertEqual(s.count(
                    f"translation {params['boundary']} "),2)
                self.assertEqual(s.count(
                    f"translation {params['pad']} "),2)
                # H cue is kept exactly at its initial physical position.
                self.assertIn("translation 0.000 0.580 0.550",s)
                self.assertIn("translation 0.200 0.780 0.550",s)
        self.assertAlmostEqual(float(CONFIG["long"]["width"])-
                               float(CONFIG["short"]["width"]),.4,places=7)
        self.assertAlmostEqual(float(CONFIG["long"]["wall"])-
                               float(CONFIG["short"]["wall"]),.4)

    def test_blind_front_original_landing_point_misses_both_new_pads(self):
        # This is a geometrical hypothesis; only real native Floor contact
        # may determine whether a fixed .wbb physically fails.
        original_fixed_x=4.15
        for params in CONFIG.values():
            self.assertGreater(abs(original_fixed_x-float(params["pad"])),.1)
        self.assertNotEqual(CONFIG["short"]["mark"],
                            CONFIG["long"]["mark"])

    def test_historical_worlds_and_public_catalogue_remain_untouched(self):
        catalog=(ROOT/"plugins/robot_windows/blockly/webeeblocks/activities.js").read_text()
        self.assertNotIn("reactive-L-length-short",catalog)
        self.assertNotIn("reactive-L-length-long",catalog)
        self.assertNotIn("progression-reactive-hg-fixed-blind-ci-only",catalog)

    def test_fail_closed_unknown_dimensions(self):
        for length,side in ((None,"left"),("short",None),("medium","left"),
                            ("long","up"),("","right")):
            with self.assertRaises(ValueError):
                source(length,side)

if __name__=="__main__":
    unittest.main()
