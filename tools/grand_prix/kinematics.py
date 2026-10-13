"""Reanalyse native R2025a traces, never feed diagnostics into the AST/oracle.

Distances below are observations of completed command trajectories, not a
qualified stopping bound or guarantees for a different speed/attitude/noise.
"""
import csv
import math
RADIUS=.09


def local(gate, point):
    dx,dy=point[0]-gate.x,point[1]-gate.y
    return dx*math.cos(gate.heading)+dy*math.sin(gate.heading), -dx*math.sin(gate.heading)+dy*math.cos(gate.heading)

from .simulation_time import milliseconds
from .timing import analyze as timing


def box_gap(position, box):
    return math.sqrt(sum(max(abs(p-c)-s/2, 0)**2 for p,c,s in
                         zip(position,(box.x,box.y,box.z),(box.sx,box.sy,box.sz))))


def range_prediction(row, direction, boxes):
    """R2025a pencil ray from the pinned MULTIRANGER pose, including attitude."""
    angle={'front':0.,'back':3.14,'left':1.57,'right':-1.57}[direction]
    origin=tuple(row[key]+.01*row[f'r{axis*3+2}']
                 for axis,key in enumerate(('x','y','z')))
    ray=tuple(row[f'r{axis*3}']*math.cos(angle)+row[f'r{axis*3+1}']*math.sin(angle)
              for axis in range(3))
    result=2.
    for box in boxes:
        lower,upper=0.,math.inf
        for p,d,c,s in zip(origin,ray,(box.x,box.y,box.z),(box.sx,box.sy,box.sz)):
            if abs(d)<1e-12:
                if not c-s/2<=p<=c+s/2:
                    upper=-1;break
            else:
                a,b=(c-s/2-p)/d,(c+s/2-p)/d
                lower=max(lower,min(a,b));upper=min(upper,max(a,b))
        if upper>=lower:
            result=min(result,lower)
    if ray[2]<0:
        result=min(result,-origin[2]/ray[2])
    return result


def analyze(path, log, layout, seconds, attempt=1, ranges=None):
    with open(path) as stream:
        rows = [{key:float(value) for key,value in row.items()}
                for row in csv.DictReader(stream)]
    required={'time','attempt','x','y','z','vx','vy','vz',*(f'r{i}' for i in range(9))}
    if any(set(row)!=required or not all(math.isfinite(v) for v in row.values()) for row in rows):
        raise ValueError('malformed or nonfinite native trace')
    rows = [row for row in rows if row['attempt']==attempt]
    if not rows or any(milliseconds(a['time'])+32!=milliseconds(b['time'])
                       for a,b in zip(rows,rows[1:])):
        raise ValueError('missing, duplicate or noncontiguous native trace')
    by_ms = {milliseconds(row['time']):row for row in rows}
    position = lambda row: (row['x'],row['y'],row['z'])
    motion = timing(log,seconds,attempt)
    commands = []
    for command in motion['commands']:
        if command['command'] not in ('MOVE','TURN','VERTICAL','LAND'):
            continue
        begin,end=command['begin_ms'],command['end_ms']
        if begin not in by_ms or end not in by_ms:
            raise ValueError('native command endpoint missing')
        samples=[by_ms[ms] for ms in range(begin,end+1,32)]
        origin=position(samples[0]);finish=position(samples[-1])
        speeds=[math.hypot(row['vx'],row['vy']) for row in samples]
        peak=max(speeds)
        # Last sample >=90% of this command's peak. This is an explicit
        # diagnostic convention, not a control-model deceleration onset.
        decel=max(i for i,speed in enumerate(speeds) if speed>=.9*peak)
        horizontal_drift=max(math.dist(origin[:2],position(row)[:2]) for row in samples)
        remaining=max(math.dist(position(samples[decel])[:2],position(row)[:2])
                      for row in samples[decel:])
        commands.append(dict(id=command['id'],command=command['command'],
                             begin_ms=begin,end_ms=end,peak_horizontal_speed_m_s=peak,
                             endpoint_speed_m_s=speeds[-1],
                             path_extent_from_request_m=horizontal_drift,
                             extent_after_last_90pct_peak_m=remaining,
                             endpoint=finish))
    margins=[]
    for gate in (*layout.gates,*layout.final_gates[:-1]):
        samples=[row for row in rows if abs(local(gate,position(row))[0])<=.11 and abs(local(gate,position(row))[1])<=layout.width/2]
        if not samples:
            raise ValueError('missing native gate traversal')
        margins.append(dict(gate=(gate.x,gate.y),
                            minimum_lateral_m=min(.28-RADIUS-abs(local(gate,position(row))[1]) for row in samples),
                            minimum_upper_m=min(.62-RADIUS-row['z'] for row in samples),
                            minimum_lower_m=min(row['z']-RADIUS-.10 for row in samples)))
    landing=next(row for row in reversed(commands) if row['command']=='LAND')
    closed=layout.final_gates[-1]
    closed_distance=-local(closed,landing['endpoint'])[0]-.02-RADIUS
    low_margins=[]
    for box in layout.boxes:
        if box.sz!=.5:
            continue
        along='x' if box.sx<box.sy else 'y'
        across='y' if along=='x' else 'x'
        samples=[row for row in rows if abs(row[along]-getattr(box,along))<=.13
                 and abs(row[across]-getattr(box,across))<=layout.width/2]
        if not samples:
            raise ValueError('missing native low-obstacle crossing')
        low_margins.append(dict(obstacle=(box.x,box.y),
                                minimum_above_m=min(row['z']-RADIUS-.5 for row in samples)))
    observations=[]
    if ranges is not None:
        range_commands=[command for command in motion['commands'] if command['command']=='RANGE']
        if len(ranges)!=len(range_commands):
            raise ValueError('range/command identity count mismatch')
        for command,reading in zip(range_commands,ranges):
            if reading['direction'] not in ('front','back','left','right') or not math.isfinite(reading['value']) or not 0<=reading['value']<=2:
                raise ValueError('unsupported or nonfinite native range')
            sample=by_ms[command['end_ms']]
            expected=range_prediction(sample,reading['direction'],layout.boxes)
            observations.append(dict(time_ms=command['end_ms'],direction=reading['direction'],
                                     raw_value_m=reading['value'],model_value_m=expected,
                                     residual_m=reading['value']-expected,
                                     position=position(sample),sensor_height_m=sample['z']+.01*sample['r8']))
    return dict(configuration=layout.identifier,attempt=attempt,samples=len(rows),
                minimum_envelope_clearance_m=min(box_gap(position(row),box)-RADIUS
                                                 for row in rows for box in layout.boxes),
                maximum_horizontal_speed_m_s=max(math.hypot(row['vx'],row['vy']) for row in rows),
                maximum_tilt_deg=max(math.degrees(math.acos(max(-1,min(1,row['r8'])))) for row in rows),
                closed_wall_clearance_at_land_ack_m=closed_distance,
                gate_margins=margins,low_obstacle_margins=low_margins,
                commands=commands,range_observations=observations,
                scope='sampled native trajectory only; peak convention is diagnostic, no universal braking bound')


def main():
    import argparse
    import json
    from pathlib import Path
    from types import SimpleNamespace
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout',type=Path,required=True)
    parser.add_argument('--trace',type=Path,required=True)
    parser.add_argument('--log',type=Path,required=True)
    parser.add_argument('--events',type=Path,required=True)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads(args.layout.read_text())
    layout=SimpleNamespace(**data)
    layout.identifier=f'{layout.version}-{layout.seed}'
    layout.gates=[SimpleNamespace(**gate) for gate in layout.gates]
    layout.final_gates=[SimpleNamespace(**gate) for gate in layout.final_gates]
    layout.boxes=[SimpleNamespace(**box) for box in layout.boxes]
    result=json.loads(args.result.read_text())
    if result['status']!='achieved' or result['configuration']!=layout.identifier:
        raise ValueError('analysis requires matching independently achieved native result')
    events=[json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    ranges=next(event['detail'] for event in events if event['event']=='GP_RANGES')
    diagnostic=analyze(args.trace,args.log.read_text(),layout,result['seconds'],result['attempt'],ranges)
    args.output.write_text(json.dumps(diagnostic,indent=2)+'\n')


if __name__=='__main__':main()
