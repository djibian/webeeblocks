#!/usr/bin/env python3
"""A5 two-world *source* hypothesis only. A static test is NEVER Webots proof."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"worlds/scenes"
A=BASE/"reactive-L-factor-hnear-gleft-proto.wbo"
B=BASE/"reactive-L-factor-hnear-gright-proto.wbo"

class FactorSourceTests(unittest.TestCase):
    def test_identical_fixed_H_and_pads(self):
        a=A.read_text(encoding="utf-8")
        b=B.read_text(encoding="utf-8")
        marker="  DEF A5_FACTOR_G_LOWER Solid {"
        self.assertEqual(a.count(marker),1)
        self.assertEqual(b.count(marker),1)
        # Exclude descriptive comments and variant-specific DEF identifiers.
        # Compare exactly the four visual markers and BOTH physical H Solids.
        before_a=a.split(" children [",1)[1].split(marker,1)[0]
        before_b=b.split(" children [",1)[1].split(marker,1)[0]
        self.assertEqual(before_a,before_b)
        self.assertEqual(a.count(" Solid {"),7)
        self.assertEqual(b.count(" Solid {"),7)
        self.assertEqual(a.count("boundingObject Box"),7)
        self.assertEqual(b.count("boundingObject Box"),7)
    def test_only_gate_geometry_changes_and_all_boxes_are_physical(self):
        a=A.read_text(encoding="utf-8")
        b=B.read_text(encoding="utf-8")
        for text in (a,b):
            self.assertNotIn("Robot {",text)
            self.assertNotIn('controller "',text)
            self.assertNotIn("USE ",text)
            self.assertEqual(len(re.findall(r"(?m)^  DEF A5_FACTOR_.* Solid \{",text)),7)
            for name in ("H_CUE_ARM","H_CUE_TIP","G_LOWER","G_UPPER",
                         "G_SIDE_ARM","G_LEFT_BOUNDARY","G_RIGHT_BOUNDARY"):
                self.assertEqual(text.count("DEF A5_FACTOR_"+name+" Solid {"),1)
            self.assertIn("boundingObject Box",text)
        self.assertIn("translation 2.450 -0.580 0.550",a)
        self.assertIn("translation 2.450 0.580 0.550",b)
        self.assertIn("translation 3.100 -0.550 0.550",a)
        self.assertIn("translation 3.100 0.550 0.550",b)
    def test_no_mission_or_distribution_has_been_authorized(self):
        doc=(ROOT/"docs/A5_H_FIXED_G_BINARY_EXPERIMENT.md").read_text()
        for phrase in ("NOT QUALIFIED","Native R2025a","motorized","four variants","Blockly"):
            self.assertIn(phrase,doc)

if __name__=="__main__":
    unittest.main()
