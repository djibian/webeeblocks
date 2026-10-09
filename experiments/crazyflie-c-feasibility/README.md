# Candidate C: complete-lifetime reachability and mixed-depth ambiguity

**Lab-only analytical implementation, 9 October 2026. Crossing UNPROVEN.**

## Decision and increment over existing work

The current contract/vision/roadmap were read at exact
`main@ec34ed5264ff4434cb58e4a46291bbdc460c3fb5`. Owner D1–D3 and current
[#70](https://github.com/djibian/webeeblocks/issues/70) permit only C:
IMU/barometer-derived world Z, lower range as local Flow information. No A/B,
ceiling, additional hardware, Runtime change, flight, flash, parameter operation
or checkpoint request is introduced. #72 over uniform floor remains separate.

At reconstruction, [#576](https://github.com/djibian/webeeblocks/pull/576) is
Ready on `36108e47e3fc070482115ac7f4f8dfda1d3c6995`, still unmerged. This result
is based directly on main and does not mutate or stack on that candidate.
Its C1/C2/C3 prototype, #561 replays and preserved failure cases are reused as
scientific premises, not reclassified as flight evidence. The existing
[fixed-table ambiguity](https://github.com/djibian/webeeblocks/issues/70#issuecomment-6085786532),
[finite-bound corollary](https://github.com/djibian/webeeblocks/issues/70#issuecomment-6085927839)
and [paired C3 replay](https://github.com/djibian/webeeblocks/issues/70#issuecomment-6086208169)
are not repeated. This follow-up supplies:

1. An executable support-function calculation for **all sampled times** and a
   conservative enclosure between them, including recovery and gyro projection.
2. A backward adversary attaining the final vertical bound, independently
   replayed; the bound cannot be dismissed as merely pessimistic propagation of
   uncorrelated Z/V boxes.
3. A mixed-depth velocity interval and two identical-input horizontal trajectories
   with **identical initial X/V**. A hypothetical nearest-range return and good
   quality cannot resolve their scale ambiguity in the declared model.
4. A positive narrow-domain control, so the conclusion does not become an
   unsupported claim that every C architecture is physically impossible.

## Reproduction and oracle

From repository root, Python 3.10+ with standard library only:

```sh
python3 tools/ci/test_c_feasibility.py -v
python3 experiments/crazyflie-c-feasibility/budget.py --output /tmp/c-budget.json
cmp -- experiments/crazyflie-c-feasibility/results.json /tmp/c-budget.json
```

The canonical `ci.yml` selector-contract step executes the 12-test oracle,
including byte equality of retained/recomputed JSON and rejection of a fabricated
5 mm bound. An independent six-input exhaustive sign enumeration checks a short
horizon; an adjoint computation checks longer horizons against a scalar forward
replay. Continuous interior points, signed Flow/noise cases, invalid domains,
recovery and a narrow positive domain are tested. No oracle invokes radio code.
CI proves this conditional algebra and evidence integrity, not flight acceptance.

## Vertical derivation (demonstration within the declared model)

Use errors `e=[z_hat-z,v_hat-v]`. Each interval has constant projected
acceleration error `u_a`, `|u_a|≤B_a(k)`, and actual duration `dt`:

`e^- = F e + G u_a`,
`F=[[1,dt],[0,1]]`, `G=[dt²/2,dt]ᵀ`.

Every second 10 ms step has a synchronous barometer correction:

`e^+ = M e^- + K u_p`,
`K=[2ω db,ω² db]ᵀ`, `M=[[1-Kz,0],[-Kv,1]]`, `db=20 ms`, `|u_p|≤B_p`.

This is the exact real-arithmetic sampled counterpart of C2's fixed-gain
predict/correct equations. It is **not** the continuous transfer bound, C1,
an execution of #576's binary32 C, full Bitcraze firmware or a controller replay.
It assumes synchronous readings; sensor age, colored pressure, timing, filter
lag and discretization relative to actual acceleration need independently
supported allowances. Arbitrary bounded pressure sequences are conservative;
specific bandwidth/rate constraints could narrow this domain if justified.

Represent all independent box coordinates by columns `g_i`, initially
`[Ez0,0]ᵀ,[0,Ev0]ᵀ`; transform existing columns by F/M and append the bounded
new input columns G/K. For any direction `l`, the exact support is
`sum_i |lᵀ g_i|`. Correlations of Z/V due to the same past disturbance survive;
they are never replaced by a new rectangular state box. Each displayed sampled
maximum checks before **and** after correction at every step.

For the interior of a prediction interval,
`|ez(s)|≤Ez(k)+s Ev(k)+B_a(k)s²/2`. Its value at dt is a conservative enclosure
for the whole interval. This bound also covers pre-update states even if a
pressure correction makes the endpoint smaller. The continuous maximum in the
JSON is this enclosure, not an assertion of an attained continuous extremum.

To construct the terminal worst case, propagate `l=[1,0]ᵀ` backward through
the transposed transitions. Choose each input sign to match its scalar adjoint
coefficient, then replay the chosen sequence forward. It attains the box-domain
terminal support. Binary64 agreement is tested; calculations are reference
numerics, **not a directed-rounding formal arithmetic certificate**.

### C3 attitude allowance

If the estimated vertical differs from true vertical by at most θ, true
horizontal acceleration is at most H, and `|a_z|≤V`, then

`|Δa_z|≤B_base + H sin θ + (g+V)(1-cos θ)`.

Decompose specific force into true horizontal and vertical components and bound
their projections. The H term is first order; gravity leakage is second order.
The implementation uses `θ(k)=θ0+Bgyro*t_end` at the end of each interval.
This is **conditional on that being a valid attitude bound**, not a proof that
a raw gyro specification implies it: calibration, scale, cross-axis errors,
coning, integration, synchronization and vibration still matter. B_base must
include remaining sensor/model/time errors. Absolute yaw is not needed for this
Z projection, but remains relevant to world XY. The illustrative gyro lifetime
starts at time zero and is never reset at a table edge. A real budget must include
time since the last independently valid alignment/calibration, including takeoff.

### Conditional vertical results (simulation/algebra, not measured limits)

Common illustrative domain: Ez0=5 mm, Ev0=2 cm/s, B_base=1 mg,
B_p=30 cm, ω=0.01 rad/s. C3 adds θ0=0.1°, Bgyro=0.1°/s, H=1 m/s²,
V=0.5 m/s². None is a qualified Crazyflie bound or an acceptance threshold.

| Full lifetime | Inertial enclosure | C2 enclosure | C3 with projection allowance |
| --- | ---: | ---: | ---: |
| 2 s | 6.46 cm | 7.52 cm | 8.10 cm |
| 4 s | 16.35 cm | 18.12 cm | 21.38 cm |
| 8 s | 47.89 cm | 49.48 cm | 69.95 cm |

The 8 s terminal adversary actually attains **49.4745605 cm** for C2 in this
model. The whole-interval enclosure is 49.4823608 cm. With inertial propagation,
4 s gives 16.348 cm; extending the same lifetime by 2 s recovery gives 30.158 cm.
Recovery cannot use a newly assumed VZ=0 or a returning-floor ToF reanchor.

All exploratory gain comparisons are retained. The seven declared ω values
`0.001,0.01,0.03,0.1,0.3,0.5,1` give 8 s enclosures approximately
`48.07,49.48,51.75,53.32,43.40,40.42,39.14 cm`. This is not an exhaustive
optimality proof or a firmware tuning prescription. It supports stopping blind
gain adjustment in this domain. The earlier architecture-independent finite-bound
corollary already excludes a universal 5 cm guarantee for its admitted domain;
these observer-specific calculations add practical sampled/recovery accounting.

Positive control: Ez0=2 mm, Ev0=2 mm/s, projected B_a=0.2 mg,
B_p=1 cm, ω=0.5 gives an 8 s enclosure of **1.971 cm**. It establishes a
nonempty hypothetical vertical domain, not available sensor performance. It
omits additional controller/clearance/XY/roundoff allowances and cannot authorize
a crossing. The archive's nominal small windows establish neither these bounds
nor an in-flight 1 cm pressure bound. No choice is fitted into a physical PASS.

## Mixed-depth Flow derivation and its strict scope

Source inspected at official `2026.08@54f31e243a0b28b67efef5ba20dbb6d9890a5478`:

| Source path | SHA-256 | Inspected property |
| --- | --- | --- |
| `src/modules/src/kalman_core/mm_flow.c` | `1365472549ff33d315c4864c21af34a0135a6432a35e6eede30da15e9ab41c42` | One translation scale with Z/tilt and gyro/lever arm; no depth distribution. |
| `src/deck/drivers/src/flowdeck_v1v2.c` | `6e81daa5eeeeda576e291efabc92e949a41f7f5f9f1d45d2c77dd213997bcabe` | Delta X/Y, motion, shutter, quality and intensity summaries; motion-gated fusion. |
| `src/drivers/src/pmw3901.c` | `8e42e827dd49d4774165a6cd2af6a82ad6d8e7e051c4658f77016ed268f9f574` | Motion burst acquisition, no spatial depth reconstruction. |
| `src/drivers/interface/pmw3901.h` | `dffdade7eb9570c1ef7331ba6c50f986153df26eaa9dd5dfc774e74cad6e311d` | Aggregate burst structure, not a per-feature flow/depth map. |

Links: [measurement model](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/kalman_core/mm_flow.c),
[deck driver](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/deck/drivers/src/flowdeck_v1v2.c).
Bitcraze's [Flow tutorial](https://www.bitcraze.io/documentation/tutorials/getting-started-with-flow-deck/)
also describes the flat-floor assumption and obstacle/texture limitations;
the [Flow V2 datasheet](https://www.bitcraze.io/documentation/hardware/flow_deck_2/flow_deck_2-datasheet.pdf)
does not certify mixed-scene metric velocity accuracy. No quality-to-depth
guarantee is supplied by the inspected code. This absence is not a proof that
no future detector could exploit additional temporal constraints.

For a **declared ideal weighted model**, level translation after exact rotation
compensation gives `q = v μ + n`, `μ=sum_i w_i/d_i`, `w_i≥0`, `sum_i w_i=1`.
If every contributing depth has independently supported `dmin≤d_i≤dmax`,
then `μ∈[1/dmax,1/dmin]`. With `|n|≤N`, evaluate all products of
`(q-N,q+N)` and `(dmin,dmax)` to enclose v, including negative/zero Flow.
No table height/map or world-Z measurement enters this inversion. These are
**caller-provided scene-domain assumptions**; a local ToF value by itself does
not establish them, nor does low image noise establish the mixture law.

At q=1 rad/s, dmin=0.35 m and dmax=1.10 m with no noise, v ranges from
0.35 to 1.10 m/s. Any scalar point estimate has worst-case error at least
0.375 m/s over that observation class. The return need not be the Flow-weighted
depth. The bounds are informative when narrow and correctly supported; they
are not an autonomous single-plane classifier.

### Identical-initial-state horizontal counterexample

For 0≤t≤2 s, let B=5 mg and
`v_±=0.4±Bt`, `x_±=0.4t±Bt²/2`, `a_±=±B`, acceleration errors `∓B`.
The admitted measured horizontal acceleration is zero in both cases, with exact
same initial X/V. Set common `q=0.4*(0.5/0.35+0.5/1.10)` and choose
`w_±=(q/v_±-1/1.10)/(1/0.35-1/1.10)`.
Both constructed mixtures have `0.3096<w<0.8142`, identical q and the same
hypothetical nearest depth 0.35 m. Their final positions differ by 19.62 cm;
any estimator using only these admitted observations has worst-case error
at least **9.81 cm**, despite exact initialization. Fixed true Z is common.

This is a demonstration for an abstract convex-mixture/acceleration-error
observation class. It is **not** a pixel-level PMW3901 replay, a full-airframe
indistinguishability theorem, a claim of identical shutter/intensity/squal
hardware outputs, or a proof about every actual fixed table/texture. Scene
weights are constructed; tilt/thrust dynamics and correlated physical IMU errors
could narrow the class. Additional quality fields have no certified constraint
in this model; arbitrary equal values cannot manufacture hardware validation.
Real correlation failure/occlusion could also violate the convex-mixture model
and make its intervals insufficient. A calibrated error/model bound is still U.

Rejecting unreliable Flow leaves the conditional inertial coast bound
`Ex0+Ev0*T+Bxy*T²/2`. With Ex0=5 mm, Ev0=2 cm/s, Bxy=5 mg, 2 s permits
14.31 cm. Narrow uncertainty and short losses can make coasting useful, but
reacquisition cannot erase previously unknown X without an independent position
observation. Velocity reacquisition alone is not a position reset. An IMU/Flow
consistency gate may reduce risk, but cannot distinguish the two admitted worlds
above. Lateral Multi-ranger measurements could help in constrained scenes with
independently supported observable geometry; they supply no general reference
for translation along an open table corridor and are not analyzed as a mapping
fallback here. No universal hardware impossibility is inferred from this model.

## Scientific decision and remaining indispensable information

**C remains conditionally possible on a narrow supported domain; a safe complete
crossing with the actual Crazyflie sensor/flight domain remains UNPROVEN.**
In the declared broad disturbance domains, the tested point observers cannot
guarantee a 5 cm vertical/horizontal error. That comparison quantity preserves
historical context and introduces no new qualification tolerance. Robust scene
intervals improve honesty, but cannot create missing observations.

The next necessary result is not another estimator variant or another generic
hand-carried table pass. It is an independently supported **joint operating
envelope**: full calibration-to-recovery lifetime; initial state and projected
IMU/attitude/timing errors; in-flight pressure including rotors; valid Flow
scale/error or bounded losses; persistent XY uncertainty, control error, stopping
and clearance margins. None may be inferred from covariance, a setpoint, finite
sensor values, selected replay windows or the returning surface.

Existing #561 props-off data can reject a design on recorded inputs, but cannot
bound rotor pressure/vibration or calibrate the PMW3901 spatial mixture law.
The earlier continuous props-off discriminator could reject further hypotheses;
it cannot by itself settle safe-flight viability. No such acquisition is
requested here: its decision value must be justified against these remaining
unknowns first. Preserve all earlier FAILs, #572's live resolution boundary and
the one-open-checkpoint rule. Further work is justified only if it narrows this
envelope, supplies a defensible stricter observation constraint, or resolves an
applicable review finding. A new EKF/UKF state cannot substitute for that evidence.

This is a reviewable analytical result, not self-GO. Independent V5 review and
exact-candidate CI govern integration; separate physical safety/qualification
still governs every future device action.
