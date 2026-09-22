#!/usr/bin/env python3
from controller import Supervisor

ATTEMPT_PREFIX = 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 '
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


robot = Supervisor()
step = int(robot.getBasicTimeStep())
crazyflie = robot.getFromDef('OUTCOME_CRAZYFLIE')
if crazyflie is None:
    raise RuntimeError('OUTCOME_CRAZYFLIE unavailable')
custom_data = crazyflie.getField('customData')
if custom_data is None:
    raise RuntimeError('Crazyflie customData unavailable')

current_attempt = None
marker_seen_at = None
published = False

while robot.step(step) != -1:
    value = custom_data.getSFString() or ''
    attempt = parse_attempt(value)
    if attempt is None:
        continue
    if attempt != current_attempt:
        current_attempt = attempt
        marker_seen_at = robot.getTime()
        published = False
        print(f'WEBEEBLOCKS_OUTCOME_PROBE observe attempt={attempt}', flush=True)
    if published:
        continue

    delay = 0.75 if current_attempt == 1 else 3.0
    if robot.getTime() - marker_seen_at < delay:
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
