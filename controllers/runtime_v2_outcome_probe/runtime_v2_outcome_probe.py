#!/usr/bin/env python3
from controller import Supervisor

ATTEMPT_PREFIX = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 '
COMPLETION_PREFIX = 'WEBEEBLOCKS_ACTIVITY_COMPLETION_V1'
OUTCOME_PREFIX = 'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1'
ORACLE = 'ci-outcome-v1'


def parse_attempt(value):
    if not value.startswith(ATTEMPT_PREFIX):
        return None
    token = value[len(ATTEMPT_PREFIX):]
    try:
        attempt = int(token)
    except ValueError:
        return None
    return attempt if attempt >= 1 else None


def parse_completion(value):
    parts = value.split()
    if len(parts) != 3 or parts[0] != COMPLETION_PREFIX:
        return None
    fields = {}
    for item in parts[1:]:
        if '=' not in item:
            return None
        key, field_value = item.split('=', 1)
        if key in fields or not field_value:
            return None
        fields[key] = field_value
    if set(fields) != {'attempt', 'oracle'}:
        return None
    try:
        attempt = int(fields['attempt'])
    except ValueError:
        return None
    if attempt < 1:
        return None
    return attempt, fields['oracle']


robot = Supervisor()
step = int(robot.getBasicTimeStep())
crazyflie = robot.getFromDef('OUTCOME_CRAZYFLIE')
if crazyflie is None:
    raise RuntimeError('OUTCOME_CRAZYFLIE unavailable')
custom_data = crazyflie.getField('customData')
if custom_data is None:
    raise RuntimeError('Crazyflie customData unavailable')

current_attempt = None
published = False

while robot.step(step) != -1:
    value = custom_data.getSFString() or ''
    attempt = parse_attempt(value)
    if attempt is not None:
        if attempt != current_attempt:
            current_attempt = attempt
            published = False
            print(f'WEBEEBLOCKS_OUTCOME_PROBE observe attempt={attempt}', flush=True)
        continue

    completion = parse_completion(value)
    if completion is None or published:
        continue
    attempt, oracle = completion
    if attempt != current_attempt or oracle != ORACLE:
        continue

    status = 'achieved' if current_attempt == 1 else 'not-achieved'
    custom_data.setSFString(
        f'{OUTCOME_PREFIX} attempt={current_attempt} oracle={ORACLE} status={status}'
    )
    published = True
    print(
        f'WEBEEBLOCKS_OUTCOME_PROBE publish attempt={current_attempt} status={status}',
        flush=True,
    )