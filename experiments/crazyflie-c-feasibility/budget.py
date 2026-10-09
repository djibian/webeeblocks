#!/usr/bin/env python3
"""Conditional, adversarial error envelopes. Offline Lab; no device interface.

All bounds are caller hypotheses, never inferred from sensor quality/covariance.
Arithmetic is binary64 reference algebra, not a certified rounding enclosure.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

G = 9.81


def nonnegative(*values: float) -> None:
    if any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("bounds must be finite and nonnegative")


def projection_bound(base: float, horizontal: float, vertical: float,
                     tilt: float) -> float:
    """Tilt between true/estimated vertical, rad; yaw error is irrelevant to Z.

    |f_z| <= g + |a_z|; |f_xy| <= horizontal. Sensor/timing errors in base.
    """
    nonnegative(base, horizontal, vertical, tilt)
    if tilt > math.pi / 2:
        raise ValueError("declared tilt envelope exceeds supported domain")
    return base + horizontal * math.sin(tilt) + (G + vertical) * (1 - math.cos(tilt))


def vertical_envelope(duration: float, *, dt: float = .01, omega: float = .01,
                      z0: float = .005, v0: float = .02, acceleration: float = G*.001,
                      pressure: float = .3, tilt0: float = 0,
                      gyro_rate: float = 0, horizontal: float = 0,
                      vertical: float = 0, baro_stride: int = 2) -> dict:
    """Exact sampled support function of the linear C2 reference error model.

    Constant acceleration error within each prediction interval; arbitrary
    bounded pressure error at each correction. Each input is an independent
    box coordinate. Columns retain correlations between Z/V; a marginal box
    is NOT reapplied at each step. omega=0 is inertial propagation.
    """
    nonnegative(duration, dt, omega, z0, v0, acceleration, pressure,
                tilt0, gyro_rate, horizontal, vertical)
    if type(baro_stride) is not int or baro_stride < 1:
        raise ValueError("baro_stride must be a positive integer")
    if duration <= 0 or dt <= 0 or dt * baro_stride > .1 or omega * dt * baro_stride >= .1:
        raise ValueError("unsupported duration/cadence/gain")
    steps = round(duration / dt)
    if not math.isclose(steps*dt, duration, rel_tol=0, abs_tol=1e-10):
        raise ValueError("duration must contain whole prediction intervals")
    columns = [[z0, 0.], [0., v0]]
    max_sampled_z = z0
    max_continuous_z = z0
    peak_time = 0.
    for step in range(1, steps + 1):
        # Monotone gyro envelope uses END-of-interval tilt, never an edge reset.
        tilt = tilt0 + gyro_rate * (step*dt)
        ba = projection_bound(acceleration, horizontal, vertical, tilt)
        ez = math.fsum(abs(c[0]) for c in columns)
        ev = math.fsum(abs(c[1]) for c in columns)
        # Triangle enclosure for every time inside this interval, before update.
        max_continuous_z = max(max_continuous_z, ez + dt*ev + .5*ba*dt*dt)
        columns = [[c[0] + dt*c[1], c[1]] for c in columns]
        columns.append([.5*dt*dt*ba, dt*ba])
        pre = math.fsum(abs(c[0]) for c in columns)
        if pre > max_sampled_z:
            max_sampled_z, peak_time = pre, step*dt
        if step % baro_stride == 0 and omega:
            kb_z = 2*omega*dt*baro_stride
            kb_v = omega*omega*dt*baro_stride
            columns = [[(1-kb_z)*c[0], c[1]-kb_v*c[0]] for c in columns]
            columns.append([kb_z*pressure, kb_v*pressure])
        post = math.fsum(abs(c[0]) for c in columns)
        if post > max_sampled_z:
            max_sampled_z, peak_time = post, step*dt
        max_continuous_z = max(max_continuous_z, post)
    return dict(terminal_z_m=math.fsum(abs(c[0]) for c in columns),
                terminal_v_m_s=math.fsum(abs(c[1]) for c in columns),
                maximum_sampled_z_m=max_sampled_z,
                continuous_enclosure_z_m=max_continuous_z,
                sampled_peak_time_s=peak_time,
                assumptions=dict(duration_s=duration, dt_s=dt, omega_rad_s=omega,
                    z0_m=z0, v0_m_s=v0, acceleration_m_s2=acceleration,
                    pressure_m=pressure, tilt0_rad=tilt0,
                    gyro_rate_rad_s=gyro_rate, horizontal_m_s2=horizontal,
                    vertical_m_s2=vertical, baro_stride=baro_stride))


def terminal_witness(duration: float, dt: float, omega: float,
                     z0: float, v0: float, acceleration: float,
                     pressure: float, baro_stride: int = 2) -> dict:
    """Backward adjoint selects the exact box adversary for terminal Z.

    An independent forward recurrence replays it. No projection envelope here.
    """
    nonnegative(duration, dt, omega, z0, v0, acceleration, pressure)
    if duration <= 0 or dt <= 0 or dt > .1 or type(baro_stride) is not int or baro_stride < 1:
        raise ValueError("invalid cadence/horizon")
    if dt*baro_stride > .1 or omega*dt*baro_stride >= .1:
        raise ValueError("unsupported gain")
    steps = round(duration/dt)
    if steps < 1 or not math.isclose(steps*dt, duration, abs_tol=1e-10):
        raise ValueError("invalid horizon")
    adj = [1., 0.]
    choices = []
    support = 0.
    def sign(x):
        return 1. if x >= 0 else -1.
    for step in range(steps, 0, -1):
        bp = 0.
        if step % baro_stride == 0 and omega:
            kz, kv = 2*omega*dt*baro_stride, omega*omega*dt*baro_stride
            c = adj[0]*kz + adj[1]*kv
            bp = pressure*sign(c)
            support += abs(c)*pressure
            adj = [(1-kz)*adj[0]-kv*adj[1], adj[1]]
        c = adj[0]*.5*dt*dt + adj[1]*dt
        ea = acceleration*sign(c)
        support += abs(c)*acceleration
        choices.append((ea, bp))
        adj = [adj[0], dt*adj[0]+adj[1]]
    z, v = z0*sign(adj[0]), v0*sign(adj[1])
    support += abs(adj[0])*z0 + abs(adj[1])*v0
    for step, (ea, bp) in enumerate(reversed(choices), 1):
        z += dt*v + .5*dt*dt*ea
        v += dt*ea
        if step % baro_stride == 0 and omega:
            residual = bp-z
            z += 2*omega*dt*baro_stride*residual
            v += omega*omega*dt*baro_stride*residual
    return dict(support_m=support, replay_terminal_z_m=z)


def flow_interval(angular_rate: float, min_depth: float, max_depth: float,
                  noise: float = 0.) -> tuple[float, float]:
    """q=v*sum(w_i/d_i)+n, w_i>=0, sum(w_i)=1, d_i in [dmin,dmax].

    Level, rotation-compensated, one-dimensional translation only. This
    convex mixture model is NOT a validated PMW3901 mixed-scene specification.
    """
    nonnegative(min_depth, max_depth, noise)
    if not math.isfinite(angular_rate) or min_depth <= 0 or max_depth < min_depth:
        raise ValueError("missing/invalid depth domain")
    corners = [(angular_rate+e)*d for e in (-noise, noise)
               for d in (min_depth, max_depth)]
    return min(corners), max(corners)


def horizontal_pair(duration: float, *, base_speed: float = .4,
                    acceleration: float = G*.005,
                    near: float = .35, far: float = 1.1) -> dict:
    """Same initial X/V, admitted a_m=0 and q, different true X trajectories.

    Constructed scene weights, not a pixel-exact physical sensor replay.
    Both have fixed true Z; nearest-range observation remains near in the model.
    """
    nonnegative(duration, base_speed, acceleration, near, far)
    if duration <= 0 or base_speed <= acceleration*duration or near <= 0 or far <= near:
        raise ValueError("invalid pair domain")
    q = base_speed*(.5/near + .5/far)
    samples = []
    for k in range(101):
        t = duration*k/100
        worlds = []
        for direction in (-1., 1.):
            v = base_speed+direction*acceleration*t
            weight = (q/v-1/far)/(1/near-1/far)
            if not 0 < weight < 1:
                raise ValueError("constructed mixture leaves admissible depth domain")
            worlds.append(dict(x_m=base_speed*t+direction*.5*acceleration*t*t,
                               v_m_s=v, true_a=direction*acceleration,
                               acceleration_error=-direction*acceleration,
                               near_weight=weight, reconstructed_q=v*(weight/near+(1-weight)/far)))
        samples.append(dict(t_s=t, worlds=worlds))
    return dict(duration_s=duration, angular_rate_rad_s=q,
                acceleration_error_bound_m_s2=acceleration,
                nearest_depth_m=near, far_depth_m=far,
                worst_case_position_error_lower_bound_m=.5*acceleration*duration**2,
                samples=samples)


def coast_position_bound(duration: float, position: float, velocity: float,
                         acceleration: float) -> float:
    nonnegative(duration, position, velocity, acceleration)
    return position + duration*velocity + .5*acceleration*duration*duration


def report() -> dict:
    cases = {}
    for t in (2., 4., 8.):
        cases[f"inertial_{t:g}s"] = vertical_envelope(t, omega=0)
        cases[f"C2_{t:g}s"] = vertical_envelope(t)
        cases[f"C3_projection_{t:g}s"] = vertical_envelope(t,
            tilt0=math.radians(.1), gyro_rate=math.radians(.1),
            horizontal=1., vertical=.5)
    narrow = vertical_envelope(8., omega=.5, z0=.002, v0=.002,
                              acceleration=G*.0002, pressure=.01)
    witness = terminal_witness(8., .01, .01, .005, .02, G*.001, .3)
    pair = horizontal_pair(2.)
    weights = [w['near_weight'] for s in pair['samples'] for w in s['worlds']]
    return dict(schema="webeeblocks.c-feasibility.v1",
                scope="CONDITIONAL_MODEL_ONLY_NO_PHYSICAL_QUALIFICATION",
                vertical=cases, terminal_adversary_8s=witness,
                illustrative_gain_comparison_8s=[
                    dict(omega_rad_s=w, continuous_enclosure_z_m=
                         vertical_envelope(8., omega=w)['continuous_enclosure_z_m'])
                    for w in (.001, .01, .03, .1, .3, .5, 1.)],
                narrow_hypothetical_vertical_8s=narrow,
                flow=dict(angular_rate_rad_s=1., depth_domain_m=[.35, 1.1],
                          velocity_interval_m_s=flow_interval(1., .35, 1.1),
                          minimax_velocity_error_m_s=(1.1-.35)/2),
                horizontal_pair_2s={k:v for k,v in pair.items() if k != 'samples'} |
                    dict(min_near_weight=min(weights), max_near_weight=max(weights)),
                coast_2s_m=coast_position_bound(2., .005, .02, G*.005),
                recovery_example_m={"crossing_4s": coast_position_bound(4., .005, .02, G*.001),
                                    "crossing_plus_recovery_6s": coast_position_bound(6., .005, .02, G*.001)})


def canonical_report() -> str:
    return json.dumps(report(), indent=2, sort_keys=True, allow_nan=False) + "\n"


def verify_retained(text: str) -> None:
    if text != canonical_report():
        raise ValueError("retained scientific results differ from recomputation")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(canonical_report(), encoding='utf-8')
