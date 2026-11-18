"""A6-B native ray parser: fail closed on samples 10–13 and negative controls."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_a6_b_native_ranges import validate

G={"matched":{1:(.36,),2:(-.85,.36),3:(-.85,-.31,.36)},
   "sampling":{1:(.48,),2:(-.8,.48),3:(-.8,-.16,.48)}}
def witness(family,n):
 fid=int(family=="sampling");lines=[]
 for slot in range(3*n+5):
  gate=slot<3*n
  if gate:
   g=slot//3;off=slot%3-1;x=G[family][n][g]+off*.04
  else:
   g=n+slot-3*n;off=-1;x=(-.85,-.31,0,.85,1.48)[slot-3*n]
  up=.2 if gate and off==0 else 2.
  lines.append(f"A6_B_NATIVE_RAY family={fid} n={n} slot={slot} "
      f"kind={int(gate)} gate={g} offset={off} x={x:.9f} "
      f"up={up:.9f} front=1.000000000 contact=0")
 lines.append(f"A6_B_NATIVE_RANGE_PASS family={fid} n={n} "
              f"samples={3*n+5} physical_h=true motor=false pupil=false")
 return "\n".join(lines)+"\n"
class NativeRayParser(unittest.TestCase):
 def test_complete_6_worlds_including_two_digit_slots(self):
  for f in G:
   for n in (1,2,3):
    with self.subTest(f=f,n=n):
     x=validate(witness(f,n),f,n)
     self.assertEqual(len(x["samples"]),3*n+5)
 def test_corrupt_records_fail_closed(self):
  s=witness("sampling",3)
  self.assertIn("slot=13",s)
  for bad in (s.replace("slot=10","slot=oops",1),
              s.replace("contact=0","contact=1",1),
              s.replace("up=0.200000000","up=2.000000000",1),
              s.replace("family=1 n=3 samples=14","family=0 n=3 samples=14",1),
              s.replace("A6_B_NATIVE_RANGE_PASS","A6_B_NATIVE_FATAL",1)):
   with self.subTest(case=bad[-90:]):
    with self.assertRaises(AssertionError):validate(bad,"sampling",3)
 def test_wrong_physical_sampling_coordinates_fail_closed(self):
  genuine=witness("sampling",3)
  # A correct count, label, sensor and native PASS marker cannot substitute
  # for the exact actual position. Check a two-digit terminal slot too.
  for before,after in (
   ("slot=4 kind=1 gate=1 offset=0 x=-0.160000000",
    "slot=4 kind=1 gate=1 offset=0 x=-0.060000000"),
   ("slot=10 kind=0 gate=4 offset=-1 x=-0.310000000",
    "slot=10 kind=0 gate=4 offset=-1 x=0.500000000"),
   ("slot=13 kind=0 gate=7 offset=-1 x=1.480000000",
    "slot=13 kind=0 gate=7 offset=-1 x=1.200000000"),
  ):
   with self.subTest(site=before):
    self.assertIn(before,genuine)
    corrupted=genuine.replace(before,after,1)
    with self.assertRaisesRegex(AssertionError,"wrong physical x"):
     validate(corrupted,"sampling",3)

if __name__=="__main__":unittest.main()
