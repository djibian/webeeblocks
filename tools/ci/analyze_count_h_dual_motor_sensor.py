#!/usr/bin/env python3
"""A6 diagnostic: count native H-like pulses using only TWO robot sensor rays.

Deliberately NO geometry, scene variant, GPS or pupil syntax in the classifier.
The genuine PID/R2025a motor flight and native independent behavioral oracle
remain separate. A signal-only count is not a Blockly/.wbb PASS and cannot
prove resistance to backtracking across the same physical H.
"""
import math
import re

RAY=re.compile(
    r"WEBEEBLOCKS_A6_UP_MOTOR t=([0-9.]+) x=-?[0-9.]+ y=-?[0-9.]+ "
    r"z=-?[0-9.]+ up=([0-9.]+) step=(\d+) front=([0-9.]+)"
)


def extract_after_takeoff(native_log):
    lines=native_log.splitlines()
    try:
        first=next(i for i,line in enumerate(lines)
                   if "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK" in line)
        last=next(i for i in range(first+1,len(lines))
                  if "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1" in lines[i])
    except StopIteration:
        raise ValueError("native TAKEOFF ACK or LAND trace missing") from None
    data=[]
    for line in lines[first+1:last]:
        m=RAY.search(line)
        if m:
            t,up,step,front=m.groups()
            if int(step)!=32:
                raise ValueError("wrong motor flight sampling step")
            data.append((float(t),float(up),float(front)))
    if len(data)<100:
        raise ValueError("insufficient real native motor sensor samples")
    return data


def count_from_sensor_stream(records):
    """No scene/variant/XYZ input: test observability, not pupil strategy."""
    if len(records)<10:
        raise ValueError("not enough sensor evidence")
    count=0
    near_ticks=0
    far_ticks=0
    inside=False
    # H beams can briefly read FAR then NEAR again while the Crazyflie
    # crosses the SAME physical H. Re-arm only after a sustained FAR interval.
    # 20 consecutive 32-ms samples = 0.64 s; distinct H centres are 0.85 m
    # apart and the actual PID speed is <=0.20 m/s. No scene/XYZ/AST inputs.
    armed=True
    last_t=None
    observed_terminal=False
    for t,up,front in records:
        if (not all(map(math.isfinite,(t,up,front))) or
            up<0 or up>2.001 or front<0 or front>2.001):
            raise ValueError("nonfinite/out-of-range physical sensor stream")
        if last_t is not None and abs(t-last_t-.032)>.001:
            raise ValueError("gapped/duplicated physical sensor ticks")
        last_t=t
        # The existing terminal solid is ALSO an up-facing obstruction.
        # Do not count its identical upper ray pulse after the frontal wall
        # becomes close. This uses a second authentic sensor, not scene ID.
        if front<=.82:
            observed_terminal=True
            break
        if up<.75:
            near_ticks+=1
            far_ticks=0
            if armed and near_ticks>=3:
                inside=True
        elif up>1.30:
            far_ticks+=1
            near_ticks=0
            if inside and far_ticks>=3:
                count+=1
                if count>3:
                    raise ValueError("more than three distinct H pulses")
                inside=False
                armed=False
            if not armed and far_ticks>=20:
                armed=True
        else:
            near_ticks=0
            far_ticks=0
    return {"count":count,"terminal_detected":observed_terminal,
            "variant_blind_two_sensor_evidence":True,
            "no_pupil_wbb_or_backtracking_proof":True}


def inspect_motor_sensor_count(native_log):
    rows=extract_after_takeoff(native_log)
    result=count_from_sensor_stream(rows)
    result["schema"]="webeeblocks-a6-dual-motor-sensor-v1"
    result["native_samples_after_takeoff"]=len(rows)
    return result
