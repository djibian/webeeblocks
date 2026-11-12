"""Independent wall-cycle diagnostics from the original native R2025a trace.

The current step+tick p99 excludes Python glue, observation publication and
other work between consecutive native ticks. Neither value is a display FPS.
"""
import math
import statistics


def quantile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


def measure_wall_cycles(rows, begin_ms, end_ms, step_ms=8):
    """Measure 375 complete tick intervals, with their preceding timestamp.

    The row's wall_elapsed_s is recorded at the END of its tick. We measure
    [t-8,t] for each tick t, thus including all wall time between native rows.
    Refuse missing/duplicated grid points and impossible/nonfinite timing.
    """
    if (type(begin_ms) is not int or type(end_ms) is not int or
            type(step_ms) is not int or step_ms <= 0 or
            begin_ms < step_ms or begin_ms > end_ms or
            (end_ms - begin_ms) % step_ms):
        raise ValueError('invalid native wall-cycle window')
    times = range(begin_ms - step_ms, end_ms + 1, step_ms)
    by_time = {}
    for row in rows:
        t = row.get('time_ms')
        if type(t) is int and begin_ms - step_ms <= t <= end_ms:
            if t in by_time:
                raise ValueError('duplicate native wall-cycle time')
            by_time[t] = row
    if set(by_time) != set(times):
        raise ValueError('missing native wall-cycle predecessor or tick')
    total, observed, step_only, tick_only, overhead = [], [], [], [], []
    for t in range(begin_ms, end_ms + 1, step_ms):
        row = by_time[t]
        if row.get('phase') != 'active':
            raise ValueError('non-active native wall-cycle tick')
        try:
            delta = 1000 * (row['wall_elapsed_s'] - by_time[t-step_ms]['wall_elapsed_s'])
            step = 1000 * row['step_wall_s']
            tick = 1000 * row['tick_wall_s']
        except (KeyError, TypeError) as error:
            raise ValueError('invalid native wall-cycle fields') from error
        if (not all(map(math.isfinite, (delta, step, tick))) or delta <= 0 or
                step < 0 or tick < 0 or delta + 0.001 < step + tick):
            raise ValueError('invalid or nonmonotone native wall-cycle duration')
        total.append(delta)
        step_only.append(step)
        tick_only.append(tick)
        observed.append(step + tick)
        overhead.append(delta - step - tick)
    return dict(
        count=len(total),
        wall_cycle_mean_ms=round(statistics.mean(total), 6),
        wall_cycle_p95_ms=round(quantile(total, .95), 6),
        wall_cycle_p99_ms=round(quantile(total, .99), 6),
        wall_cycle_max_ms=round(max(total), 6),
        wall_speed_x=round((step_ms * len(total)) / sum(total), 6),
        step_p99_ms=round(quantile(step_only, .99), 6),
        tick_p99_ms=round(quantile(tick_only, .99), 6),
        step_plus_tick_p99_ms=round(quantile(observed, .99), 6),
        outside_step_tick_mean_ms=round(statistics.mean(overhead), 6),
        basis='successive native.trace wall_elapsed_s deltas, not step+tick')
