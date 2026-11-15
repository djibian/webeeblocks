#!/usr/bin/env python3
"""A5 experimental v2: geometric precursor of real repeated sensing, NOT flight.

Check an observationally identical two-ray prefix, a later genuine choice
and complete body-radius clearance of hand-selected *reference* centerlines.
Neither a path nor an algorithm is exposed to pupil-facing materials.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
PATHS={v:ROOT/f"worlds/scenes/reactive-L-{v.lower()}-v2.wbo" for v in "ABC"}
COLLIDER=re.compile(
    r"DEF ACTIVITY5_V2_([ABC])_(L[123]_(?:FRONT|SIDE)|TERMINAL) Solid \{"
    r"\s*translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
    r"[\s\S]*?boundingObject Box \{ size "
    r"([0-9.]+) ([0-9.]+) ([0-9.]+) \}"
)


def boxes(letter):
    src=PATHS[letter].read_text(encoding="utf-8")
    if not src.startswith(f"# Activity 5 stage-2 experimental variant {letter}"):
        raise AssertionError("wrong v2 scene identity")
    if src.count(f"DEF WEBEEBLOCKS_REACTIVE_L_V2_{letter}_SCENE Group")!=1:
        raise AssertionError("missing exact V2 scene identity")
    if any(f"WEBEEBLOCKS_REACTIVE_L_V2_{other}_SCENE" in src
           for other in "ABC" if other!=letter) or "Robot {" in src:
        raise AssertionError("ambiguous scene or extra craft")
    values={}
    for match in COLLIDER.finditer(src):
        variant,name,*numbers=match.groups()
        if variant!=letter or name in values:
            raise AssertionError("foreign or duplicated A5 V2 collider")
        values[name]=tuple(map(float,numbers))
    expected={"L1_FRONT","L1_SIDE","L2_FRONT","L2_SIDE","TERMINAL"}
    if letter=="C":expected|={"L3_FRONT","L3_SIDE"}
    if set(values)!=expected or src.count(" Solid {")!=len(expected):
        raise AssertionError("missing/unregistered physical A5 V2 collider")
    if src.count("boundingObject Box")!=len(expected):
        raise AssertionError("nonphysical obstacle in A5 V2")
    return src,values


def ray(pos,direction,colliders):
    """Geometric prediction from actual source Boxes, not a Webots reading."""
    ox,oy=pos
    dx,dy=direction
    distance=2.0
    for x,y,z,sx,sy,sz in colliders.values():
        if not z-sz/2<=.5<=z+sz/2:continue
        x0,x1=x-sx/2,x+sx/2
        y0,y1=y-sy/2,y+sy/2
        near,far=-float("inf"),float("inf")
        for origin,d,lo,hi in ((ox,dx,x0,x1),(oy,dy,y0,y1)):
            if abs(d)<1e-9:
                if not lo<=origin<=hi:
                    far=-float("inf")
                    break
            else:
                a,b=(lo-origin)/d,(hi-origin)/d
                near,far=max(near,min(a,b)),min(far,max(a,b))
        if far>=max(near,0) and near>=0:
            distance=min(distance,near)
    return round(distance,6)


def clear_centerline(a,b,colliders,radius=.09):
    """Conservative 2D craft envelope along an axis-aligned reference segment."""
    (ax,ay),(bx,by)=a,b
    for x,y,z,sx,sy,sz in colliders.values():
        if z-sz/2>.5 or z+sz/2<.5:continue
        lx,hx=x-sx/2-radius,x+sx/2+radius
        ly,hy=y-sy/2-radius,y+sy/2+radius
        if abs(ax-bx)<1e-9:
            if lx<=ax<=hx and max(min(ay,by),ly)<=min(max(ay,by),hy):
                return False
        elif abs(ay-by)<1e-9:
            if ly<=ay<=hy and max(min(ax,bx),lx)<=min(max(ax,bx),hx):
                return False
        else:raise AssertionError("reference line not axis-aligned")
    return True


class ReactiveLV2Tests(unittest.TestCase):
    def test_identical_native_ray_prefix_and_later_branch(self):
        obs={}
        for v in "ABC":
            with self.subTest(variant=v):
                src,world=boxes(v)
                # No pupil algorithm, identifiers or capteur values in scenes.
                self.assertNotIn("range_front",src)
                self.assertNotIn("range_left",src)
                self.assertNotIn("if_then",src)
                self.assertEqual(src.count("Pose { translation"),(4 if v=="C" else 3)+16)
                obs[v]=(
                    ray((0,0),(1,0),world),
                    ray((.8,0),(0,1),world),
                    ray((.8,1.0),(-1,0),world),
                )
        self.assertEqual({tuple(x[:2]) for x in obs.values()}, {(0.98,1.21)})
        self.assertEqual(obs["A"][2],.28)
        self.assertEqual(obs["B"][2],1.78)
        self.assertEqual(obs["C"][2],1.44)
        self.assertEqual(len({row[2] for row in obs.values()}),3)
        # Two observations demonstrably cannot identify a route in V2,
        # unlike old A5 V1. The *functional* need for a loop/state remains
        # a future native pupil-behavior falsification, not a syntax test.

    def test_three_no_contact_reference_corridors_and_pad_margin(self):
        legs={
          "A":[(0,0),(.8,0),(.8,1),(1.58,1)],
          "B":[(0,0),(.8,0),(.8,1),(-.62,1)],
          "C":[(0,0),(.8,0),(.8,1),(-.45,1),(-.45,1.60)]
        }
        pads={"A":(1.58,1.0),"B":(-.62,1.0),"C":(-.45,1.60)}
        for v in "ABC":
            with self.subTest(variant=v):
                src,world=boxes(v)
                for a,b in zip(legs[v],legs[v][1:]):
                    self.assertTrue(clear_centerline(a,b,world),
                                    (v,a,b,"9cm craft hits a box"))
                px,py=pads[v]
                # Visible 32cm square damier, 9cm craft half-extent.
                self.assertIn(
                    f"Pose {{ translation {px:.3f} {py:.3f} 0.002",src)
                self.assertLessEqual(abs(px),1.84)
                self.assertLessEqual(abs(py),1.84)
                # The distinct terminal does not touch the target craft.
                self.assertTrue(clear_centerline(pads[v],pads[v],world))


if __name__=="__main__":unittest.main()
