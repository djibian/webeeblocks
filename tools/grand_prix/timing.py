"""Offline diagnostic of native simulation command latency; never scoring input."""
from collections import defaultdict
import re

PREFIX = 'WEBEEBLOCKS_GP_TIMING '
PATTERN = re.compile(r'time_ms=(\d+) attempt=(\d+) phase=(request|response) id=(\d+) (command|payload)=(.*)')


def analyze(text, official_seconds, attempt=1):
    events = []
    for line in text.splitlines():
        if not line.startswith(PREFIX):
            continue
        match = PATTERN.fullmatch(line[len(PREFIX):])
        if not match:
            raise ValueError('malformed timing event')
        ms, identity, phase, request_id, key, value = match.groups()
        if int(identity) == attempt:
            if key != ('command' if phase == 'request' else 'payload'):
                raise ValueError('wrong timing phase')
            events.append((int(ms), phase, int(request_id), value))
    if not events or any(a[0] > b[0] for a, b in zip(events, events[1:])):
        raise ValueError('missing or nonmonotone native timing')
    start = next((i for i, e in enumerate(events) if e[1:] and e[1] == 'request' and e[3] == 'TAKEOFF'), None)
    if start is None:
        raise ValueError('no native takeoff')
    commands = []
    pending = None
    ids = set()
    last_response = events[start][0]
    totals = defaultdict(lambda: {'count': 0, 'service_ms': 0, 'gap_before_ms': 0})
    for ms, phase, request_id, value in events[start:]:
        if phase == 'request':
            if pending is not None or request_id in ids:
                raise ValueError('concurrent or duplicate request')
            ids.add(request_id)
            pending = (ms, request_id, value, ms - last_response)
        else:
            if pending is None or pending[1] != request_id or value != 'OK':
                raise ValueError('unmatched, late or failed response')
            begin, _, command, gap = pending
            if ms < begin or gap < 0:
                raise ValueError('negative command interval')
            row = {'id': request_id, 'command': command, 'begin_ms': begin,
                   'end_ms': ms, 'service_ms': ms - begin, 'gap_before_ms': gap}
            commands.append(row)
            total = totals[command]
            total['count'] += 1
            total['service_ms'] += ms - begin
            total['gap_before_ms'] += gap
            last_response = ms
            pending = None
            if command == 'LAND':
                break
    if pending is not None or not commands or commands[-1]['command'] != 'LAND':
        raise ValueError('incomplete timing, no land response')
    official_ms = round(official_seconds * 1000)
    if abs(official_ms / 1000 - official_seconds) > 1e-9:
        raise ValueError('official duration is not integer milliseconds')
    tail = official_ms - (last_response - events[start][0])
    if tail < 0:
        raise ValueError('timing exceeds official attempt')
    # Receipt->ACK includes movement, braking and the unchanged stability gate.
    # ACK->next receipt includes interpreter/browser/WWI together, not CPU time.
    service = sum(v['service_ms'] for v in totals.values())
    gaps = sum(v['gap_before_ms'] for v in totals.values())
    assert service + gaps + tail == official_ms
    return {'attempt': attempt, 'official_ms': official_ms, 'service_ms': service,
            'intercommand_ms': gaps, 'post_land_certification_ms': tail,
            'by_command': dict(totals), 'commands': commands,
            'scope': 'native receipt-to-ACK; stability included; browser/WWI gaps combined'}
