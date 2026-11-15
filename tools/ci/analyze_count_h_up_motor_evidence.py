#!/usr/bin/env python3
"""A6 CI-only genuine upward ray evidence during real Webots motor flight.

The certified H identities, colliders, contacts and success belong to the
separate C observer. This parser checks sampled range_up rays from the
school-only process with the genuine runtime/PID and exact Webots 32-ms steps.
It does NOT implement or prove a pupil Blockly algorithm or state variable.
"""
import math
import re

RECORD=re.compile(
    r"WEBEEBLOCKS_A6_UP_MOTOR t=([0-9.]+) x=(-?[0-9.]+) "
    r"y=(-?[0-9.]+) z=(-?[0-9.]+) up=([0-9.]+) step=(\d+)"
)
GATE_POSITIONS=(-0.850,0.000,0.850)


def attest_up_motor_trace(text,variant):
    if type(variant) is not int or variant not in (1,2,3):
        raise ValueError("invalid bounded H variant")
    rows=[]
    for fields in RECORD.findall(text):
        t,x,y,z,up=map(float,fields[:5])
        step=int(fields[5])
        if (not all(map(math.isfinite,(t,x,y,z,up))) or
            step!=32 or up<0 or up>2.001 or z<0 or z>2 or
            abs(x)>3.5 or abs(y)>2):
            raise ValueError("invalid native motor-ray sample")
        rows.append((t,x,y,z,up))
    if len(rows)<100:
        raise ValueError("missing consecutive native flight samples")
    for a,b in zip(rows,rows[1:]):
        dt=b[0]-a[0]
        if dt<=0 or abs(dt-.032)>.001:
            raise ValueError("native ray trace is missing/duplicating physics steps")
    evidence=[]
    for index,gate in enumerate(GATE_POSITIONS[:variant],1):
        suitable=[row for row in rows
                  if abs(row[2])<=.16 and .32<=row[3]<=.53]
        before=[v for v in suitable if gate-.35<=v[1]<=gate-.18]
        under=[v for v in suitable if abs(v[1]-gate)<=.045]
        after=[v for v in suitable if gate+.18<=v[1]<=gate+.35]
        if not before or not under or not after:
            raise ValueError(f"physical motor flight never sampled H {index} phases")
        in_beam=[v for v in under if v[4]<.75]
        if not in_beam or max(v[4] for v in before)<1.3 or (
                max(v[4] for v in after)<1.3):
            raise ValueError(f"no authentic far/near/far upper ray at H {index}")
        evidence.append({
            "gate_index":index,
            "physical_x_m":gate,
            "pre_high_m":max(v[4] for v in before),
            "under_min_m":min(v[4] for v in under),
            "post_high_m":max(v[4] for v in after),
            "in_beam_samples":len(in_beam),
            "under_sample_count":len(under),
        })
    return {
        "schema":"webeeblocks-a6-native-up-motor-v1",
        "variant":variant,
        "native_motor_ray_observed":True,
        "total_32ms_samples":len(rows),
        "gates":evidence,
        "not_pupil_wbb_or_counter_qualification":True,
        "not_hardware_flight_qualification":True,
    }
