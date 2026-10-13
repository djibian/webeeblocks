#!/usr/bin/env python3
"""Diagnostic integrity tests with explicitly synthetic, non-flight fixtures."""
import csv
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.kinematics import analyze, range_prediction

LOG='''WEBEEBLOCKS_GP_TIMING time_ms=0 attempt=1 phase=request id=1 command=TAKEOFF
WEBEEBLOCKS_GP_TIMING time_ms=32 attempt=1 phase=response id=1 payload=OK
WEBEEBLOCKS_GP_TIMING time_ms=64 attempt=1 phase=request id=2 command=RANGE
WEBEEBLOCKS_GP_TIMING time_ms=64 attempt=1 phase=response id=2 payload=VALUE 2.000000000
WEBEEBLOCKS_GP_TIMING time_ms=96 attempt=1 phase=request id=3 command=MOVE
WEBEEBLOCKS_GP_TIMING time_ms=192 attempt=1 phase=response id=3 payload=OK
WEBEEBLOCKS_GP_TIMING time_ms=224 attempt=1 phase=request id=4 command=TURN
WEBEEBLOCKS_GP_TIMING time_ms=256 attempt=1 phase=response id=4 payload=OK
WEBEEBLOCKS_GP_TIMING time_ms=288 attempt=1 phase=request id=5 command=LAND
WEBEEBLOCKS_GP_TIMING time_ms=352 attempt=1 phase=response id=5 payload=OK
'''


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'trace.csv'
        self.layout=N(identifier='synthetic-not-native',width=1.,gates=(),
                      final_gates=(N(x=0.,y=-.75,heading=-math.pi/2,closed=True),),
                      boxes=(N(x=0.,y=-.75,z=.65,sx=.56,sy=.04,sz=1.3),))
        self.rows=[]
        for tick in range(14):
            x=[0,0,0,0,.0064,.0112,.0128,.0128,.0128,.0128,.0128,.0128,.0128,.0128][tick]
            speed=[0,0,0,.2,.2,.15,0,0,0,0,0,0,0,0][tick]
            self.rows.append(dict(time=tick*.032,attempt=1,x=x,y=0.,z=.415 if tick<10 else .015,
                                  vx=speed,vy=0.,vz=0.,**{f'r{i}':float(i in (0,4,8)) for i in range(9)}))
        self.write()

    def tearDown(self):self.temp.cleanup()

    def write(self):
        with self.path.open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(self.rows[0]));writer.writeheader();writer.writerows(self.rows)

    def test_known_margins_and_explicit_peak_convention(self):
        result=analyze(self.path,LOG,self.layout,.416,ranges=[dict(direction='front',value=2.)])
        self.assertAlmostEqual(result['minimum_envelope_clearance_m'],.64)
        self.assertAlmostEqual(result['closed_wall_clearance_at_land_ack_m'],.64)
        move=next(row for row in result['commands'] if row['command']=='MOVE')
        self.assertAlmostEqual(move['extent_after_last_90pct_peak_m'],.0064)
        self.assertEqual(move['endpoint_speed_m_s'],0.)
        self.assertEqual(result['range_observations'][0]['residual_m'],0.)
        self.assertIn('no universal braking bound',result['scope'])

    def test_trace_gap_duplicate_and_wrong_attempt_refuse(self):
        original=list(self.rows)
        for mutate in ('gap','duplicate','identity'):
            self.rows=list(original)
            if mutate=='gap':self.rows.pop(5)
            elif mutate=='duplicate':self.rows.insert(5,dict(self.rows[4]))
            else:
                self.rows=[dict(row,attempt=2) for row in self.rows]
            self.write()
            with self.assertRaises(ValueError):analyze(self.path,LOG,self.layout,.416)

    def test_missing_command_end_and_range_identity_refuse(self):
        with self.assertRaises(ValueError):analyze(self.path,LOG.replace('time_ms=192','time_ms=193'),self.layout,.416)
        with self.assertRaises(ValueError):analyze(self.path,LOG,self.layout,.416,ranges=[])
        with self.assertRaises(ValueError):analyze(self.path,LOG.replace('id=3 payload','id=8 payload'),self.layout,.416)
        with self.assertRaises(ValueError):analyze(self.path,LOG.rsplit('\n',2)[0],self.layout,.416)

    def test_nonfinite_trace_and_ranges_refuse(self):
        for key in ('x','vx','r8'):
            original=self.rows[4][key];self.rows[4][key]=math.nan;self.write()
            with self.assertRaises(ValueError):analyze(self.path,LOG,self.layout,.416)
            self.rows[4][key]=original
        self.write()
        for value in (math.nan,math.inf,-1,2.01):
            with self.assertRaises(ValueError):analyze(self.path,LOG,self.layout,.416,ranges=[dict(direction='front',value=value)])

    def test_native_multiranger_origin_includes_attitude(self):
        row=dict(self.rows[0]);box=N(x=1.,y=0.,z=.65,sx=.04,sy=.56,sz=1.3)
        self.assertAlmostEqual(range_prediction(row,'front',[box]),.98)
        angle=.1
        row.update(r0=math.cos(angle),r2=math.sin(angle),r6=-math.sin(angle),r8=math.cos(angle))
        self.assertAlmostEqual(range_prediction(row,'front',[box]),(.98-.01*math.sin(angle))/math.cos(angle))


if __name__=='__main__':unittest.main()
