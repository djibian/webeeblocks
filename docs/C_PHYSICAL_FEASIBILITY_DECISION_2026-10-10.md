# C physical-feasibility decision — 10 October 2026

**Scientific verdict: INDETERMINATE (INDÉTERMINÉ). Recommend suspending further
development and new acquisitions for #70 under the present evidence.** A safe
floor → table → floor crossing has no demonstrated physically supported
operating domain with the Crazyflie 2.1, Flow Deck V2 and Multi-ranger alone.
Neither a universal hardware impossibility nor a qualified safe flight follows.

This is a bounded research conclusion for
[#70](https://github.com/djibian/webeeblocks/issues/70), not an independent V5
integration GO, a human PASS, permission to fly, or an owner decision to abandon
the product goal. Keep table flight unavailable and the research issue open
unless the owner decides otherwise. #157 qualification and #72's final mission
over a qualified uniform floor remain independent.

## Baseline and incremental question

Reconstructed baseline: `main@a07af4e532fa92a3748ba5f199fdf6a32f03dddb`.
[#576](https://github.com/djibian/webeeblocks/pull/576) and
[#577](https://github.com/djibian/webeeblocks/pull/577) are integrated; source
heads were respectively `36108e47e3fc070482115ac7f4f8dfda1d3c6995` and
`8cc2b488f953844ff0788c0133b3e1ceb0c5f289`.
[#578](https://github.com/djibian/webeeblocks/pull/578) already offers the
roadmap baseline update. This separate dossier addresses the physical decision,
without editing that candidate or reopening its completed model/replay stage.

The [owner D1–D3 decision](DECISION_FINAL_FLIGHT_ALTITUDE_2026-10-09.md),
[AGENTS.md](../AGENTS.md), [vision](PRODUCT_VISION.md) and
[roadmap](ROADMAP.md) govern this work. Only C is considered: independent
IMU/barometer world Z, downward range for local clearance/Flow depth. No terrain
following, mapped-table compensation, ceiling reference or additional hardware
is proposed. No Runtime, firmware, parameter, motor or checkpoint change occurs.

The increment is a manufacturer-specification audit against the already derived
requirements, an explicit control/recovery closure test and a decision about
the value of further acquisition. No new observer or simulator is needed to
answer whether existing evidence supplies the missing physical bounds.

Labels: **D** = derivation/source property within stated assumptions;
**S** = simulation/model result; **O** = real recorded observation or descriptive
replay; **U** = unestablished physical property. A typical specification is not
a deterministic bound; a statistical specification requires an applicable
population, conditions and risk interpretation.

## Established results reused, not reclassified

See the integrated [world-Z dossier](../experiments/crazyflie-c-world-z/README.md)
and [complete-lifetime dossier](../experiments/crazyflie-c-feasibility/README.md),
their immutable upstream manifest and retained results. In particular:

| Evidence | Established conclusion | Limit for this decision |
| --- | --- | --- |
| D/S: C structural separation, hosted official models | Local range need not contaminate C world Z; stock Flow/EKF covariance paths can contaminate it. | Software input independence does not bound sensor error. |
| O: #561 stationary, props-off IMU/barometer archive | Rejects high barometer authority on those inputs; some anchored C2/C3 windows are small. | Neither true moving Z/V nor rotor effects are measured. Selected endpoints are not whole-trajectory bounds. |
| D: fixed-table finite-bound ambiguity | With admitted unknown pressure/acceleration errors, indistinguishable vertical trajectories exclude some guarantees. | A conditional observation-class theorem, not a measured Crazyflie error floor. |
| D/S: #577 sampled reachability | For its illustrative 8 s domain C2 admits about 49.48 cm and C3 about 69.95 cm error; recovery extends the lifetime. | Illustrative disturbance bounds are not qualified device bounds. |
| D/S: #577 positive control | A hypothetical 8 s vertical domain reaches a 1.971 cm enclosure. | Its 0.2 mg projected acceleration, 1 cm pressure and initial-state bounds lack physical support; XY/control margins are omitted. |
| D/S: mixed-depth Flow ambiguity and coasting | Good aggregate Flow plus a local range need not identify metric velocity in the declared model; lost position uncertainty persists after velocity reacquisition. | Not a PMW3901 pixel-level or full-airframe indistinguishability theorem. |

The broad modeled domains fail their historical 5 cm comparison; the positive
control prevents an unjustified universal negative conclusion. These facts are
compatible. Neither settles the physical device domain. All historical FAILs,
#572's own result boundary and existing qualification thresholds remain intact.

## Manufacturer values versus flight requirements

The official [Crazyflie 2.1 datasheet][CF] identifies BMI088 and BMP388. Audit
these parts, rather than treating later Crazyflie variants as interchangeable.
Official firmware remains the locked `2026.08` release
`54f31e243a0b28b67efef5ba20dbb6d9890a5478`; this is source evidence, not proof
of the exact binary/configuration on a future physical subject.

### Vertical inertial and attitude errors

The [BMI088 datasheet][IMU], rev. 1.9, tables 4–5, gives typical acceleration
offset 20 mg, temperature drift below 0.2 mg/K, Z noise density
190 µg/√Hz at ±3 g, cross-axis sensitivity 0.5% and package alignment 0.5°.
Typical gyro offset is ±1°/s, temperature coefficient ±0.015°/s/K and noise
0.014°/s/√Hz; gyro g-sensitivity has a 0.1°/s/g maximum entry. Section 1
describes min/max values as ±3σ. These entries do not specify the combined
post-calibration residual under the mounted drone's vibration and temperature
history. Constant offset can be calibrated; its full value is not drift after
calibration. Bias instability, noise and residual bias are distinct quantities.

The [sensor driver][SENSOR] selects ±24 g and ±2000°/s, stationary gyro bias,
one scalar acceleration-magnitude calibration, alignment and software filtering.
It does not implement a full per-axis offset/scale/cross-axis calibration.
Its acceleration step is `48/65536 g = 0.73242 mg`, not the product page's
minimum-range resolution. Averaging/dither can yield sub-LSB estimates; this
step is neither a minimum attainable estimation error nor a bound on filtered
residual bias. A coherent half-step *remaining after calibration* would alone
integrate to 11.50 cm over 8 s. That conditional calculation does not assert
such a residual occurs.

For ideal inertial propagation (D),

`Ez(T) ≤ Ez0 + Ev0 T + Ba T²/2`.

The following sensitivity quantities reuse the historical 5 cm comparison,
**not a new flight acceptance tolerance**. Each row spends the entire budget on
one error and idealizes every other term, so none is sufficient for a crossing.

| Conditional comparison | Consequence at T = 8 s |
| --- | --- |
| Constant projected residual acceleration, exact initial state, no barometer correction | At most 0.1593 mg to spend only 5 cm on this term. |
| Initial Z error 5 mm, no other error | Initial VZ uncertainty at most 5.625 mm/s. |
| Constant small vertical-direction error, horizontal acceleration 1 m/s², first-order projection only | About 0.0895° spends 5 cm; gravity and other terms tighten it. |
| A post-calibration constant acceleration change of 0.2 mg | 6.28 cm drift. A typical temperature coefficient does not prove the change or bound it. |

The #576 finite-bound corollary's separate 8 s requirement of about 0.460 mg
to exclude its 5 cm ambiguity is an architecture-independent *necessary*
condition in that observation class, not the sufficient inertial budget above.
Do not interchange them.

To challenge a premature negative verdict, ideal white acceleration noise with
one-sided density `N = 190 µg/√Hz` gives
`σz = N g sqrt(T³/6) ≈ 1.72 cm` at 8 s. This is an optimistic statistical
calculation, borrowing the ±3 g typical value, with perfect initialization,
attitude and bias. It is not a device confidence interval or a time-uniform
guarantee. It shows why chip noise alone cannot establish impossibility.
Conversely, zero-mean noise does not justify setting low-frequency error to zero.

### Pressure, filtering and timing

The [BMP388 datasheet][BARO], rev. 1.7, table 8 gives **0.9 Pa typical RMS**
at pressure oversampling 8× and IIR coefficient 3, matching the inspected driver.
Section 3.4.4 measures noise in controlled pressure from 32 consecutive points,
explicitly excluding long-term drift. Table 2's typical relative accuracy
±8 Pa is specified per 10 kPa step; it is neither a short-path error floor nor
a flight bound. Its typical temperature coefficient is ±0.75 Pa/K. Calibration
can cancel a common offset but not unknown pressure changes at the vent.

For an illustrative near-ground density `ρ = 1.2 kg/m³` and
`g = 9.81 m/s²`, hydrostatics gives `δz ≈ -δp/(ρg)` (D):

- 0.9 Pa corresponds to 7.65 cm **per-reading typical RMS**, before observer
  filtering; it does not prove a 7.65 cm fused-error floor.
- A pressure-only 5 cm reference allowance would be 0.589 Pa; 1 cm would be
  0.118 Pa. The positive control's hard 1 cm input bound is not supplied by
  this noise table. Slower filtering could reduce random output noise but adds
  lag and does not remove coherent pressure disturbance.
- A dynamic-pressure perturbation `κ ρ U²/2` gives an equivalent
  `κ U²/(2g)` height error. At U = 1 m/s and κ = 1 this is 5.10 cm.
  **Neither U nor κ is a measured rotor-to-vent coupling here.** This scale
  calculation identifies the missing disturbance, not an observed propwash error.

At nominal 50 Hz, coefficient 3 implements
`y[k] = 3/4 y[k-1] + 1/4 p[k]`: DC group delay is 3 samples, about 60 ms,
before conversion/read/queue/observer age. Constant reference-pressure changes
pass with unit DC gain. #561 cannot supply motorized pressure/temperature bounds.
Pressure correlation forbids treating all filtered samples as independent.

The previously identified release-clock factor 85/84 is deterministic and
repairable; it is not the decisive obstacle. Full age/phase allowances remain U.
For example, an acceleration delay Δ and jerk bound J imply a `JΔ` acceleration
allowance, only if J and Δ are supported. Do not rescale #561's distinct clocks
or reopen the dominated interrupt investigation as a substitute for flight bounds.

## Both Flow transitions and horizontal recovery

The [Flow V2 datasheet][FLOW] identifies PMW3901 and VL53L1x but gives no
mixed-depth metric-velocity bound. Bitcraze's [Flow tutorial][TUTORIAL] states
the flat-floor assumption and texture/obstacle limitations. The manufacturer
[PMW3901 datasheet][PMW], v1.00, table 3, lists an 80 mm minimum working
distance, typical 42° viewing angle and 7.4 rad/s maximum angular speed under
specified conditions. Detecting motion across that distance range does not
identify one depth for all tracked texture.

The locked [Flow driver][FLOWDRIVER] returns aggregate deltas, motion, shutter
and quality/intensity summaries. Its optional shutter-based noise model was
fitted over texture conditions; it does not certify depth homogeneity.
The [measurement model][FLOWMODEL] uses one translation depth and rotational
compensation. Simultaneously visible floor/table texture can give different
angular motions. PMW3901's proprietary correlation can select one region or
fail; the #577 convex mixture is a declared abstraction, not guaranteed chip
behavior. A nearest/local ToF return is not a measured optical weighting depth.

Even the favorable level-camera, sharp-edge, 42° pinhole geometry has a mixed
table/floor opportunity over a nominal width `2 c tan(21°)`, where c is local
camera clearance over the upper plane. At c = 0.35 m this is 0.269 m, or about
1.34 s at 0.2 m/s **per edge**. This idealized geometry excludes attitude,
vertical face texture, offsets and effective correlation support, so it is not
a certified maximum loss interval. It uses illustrative geometry for a safety
analysis, not a table map in C's estimator.

Slowing down reduces some angular/actuation demands but lengthens ambiguous
Flow exposure and the world-Z lifetime. Speeding up shortens that exposure but
raises braking and acceleration/attitude demands. Neither extreme independently
solves the problem. Two transitions and recovery must be budgeted together.

Gating Flow would require a physically supported false-accept/error bound or
bounded loss duration; quality alone establishes neither. During loss,
`Ex ≤ Ex0 + Ev0 τ + Bxy τ²/2` is conditional on its inertial bounds.
The retained 2 s example permits 14.31 cm. Reacquired velocity cannot erase
accumulated position error; returning-floor range cannot reset C world Z.
Multi-ranger may supply local hazard constraints, but in an open table corridor
it supplies no general along-track position or vertical datum. Its availability
and avoidance envelope cannot be assumed from finite readings or #572's separate
front-observation report.

## Can a joint physically credible domain be closed?

A candidate domain must specify full time since independently valid alignment,
initial Z/V/XY/yaw uncertainty, duration through both transitions **and safe
recovery**, textures/light, clearance and battery/payload configuration.
For every relevant surface and every time in that domain, a sufficient margin
must include at least (D):

`clearance > swept-body allowance + state-estimation error + tracking error
             + delayed-detection/recovery travel`.

World-Z and persistent XY errors must be included in the actual swept volume,
not only compared to the setpoint. For a simple braking model, latency L,
approach speed v and independently supported minimum deceleration a give
`v L + v²/(2a)` travel, before estimation uncertainty. This formula does not
measure achievable a. Controlled landing/recovery also consumes time and must
respect C's reference independence; an emergency stop/drop is not proof of a
controlled recovery.

The locked [PID cascade][PID] limits requested tilt/velocity and the
[mixer][MIXER] saturates motor commands. Limits and gains do not supply minimum thrust reserve,
tracking-error bounds or recovery deceleration for the actual payload, battery,
rotor disturbance and table proximity. The integrated simulations supply
conditional observer bounds, not this coupled airframe/sensor/control closure.
Adding an ideal IMU, guessed pressure disturbance and single-plane Flow to a
new simulator would assume the unknowns and would not change the verdict.

No intersection of a **supported** Z envelope, supported two-edge XY envelope
and positive recovery margins is established. That is failure to demonstrate
viability, not proof that the intersection is empty in nature. Shorter lifetimes,
repeatable calibration, benign scenes and ample clearance could help; no sourced
joint bounds currently justify labeling such a domain physically credible.

Published evidence was also checked against this conclusion. Bitcraze/SINTEF's
[2022 edge-crossing demonstration][SINTEF] uses an upward range and terrain
states, with motion-capture evaluation; it cannot qualify C's independent
IMU/barometer architecture. It is not proposed as a substitute. The published
[2021 BMP388 experiment][BENCH] hand-moves a props-off CF2.1 with stronger
filtering: evidence of signal response and latency, not motorized error bounds.
These favorable demonstrations therefore do not close the missing C domain.

## Exact decision-changing unknowns and acquisition value

Only the following joint information could change this verdict. Each needs
independent provenance and an explicit applicable domain; a covariance or an
unreferenced internal estimate is not measurement truth.

| Missing information (U) | Decision it could change | Can a new props-off trace settle it now? |
| --- | --- | --- |
| Full-lifetime projected IMU/attitude/initial-state and pressure error envelope, including low-frequency thermal and rotor effects, signal ages and bandwidth | Whether C's Z support fits the available vertical/recovery margin | No. It can falsify a calibration/model on the bench, but a pass leaves rotor/vibration/pressure terms unresolved. |
| Actual two-edge PMW3901 metric error/loss envelope, admissible textures/light/attitude, detection latency and inertial coast error | Whether persistent XY uncertainty stays within the corridor and braking margin | A geometrically referenced props-off traverse can test a **specified** sensor-only scene hypothesis. It cannot bound in-flight tilt, vibration, all admitted textures or feedback behavior. No such deciding hypothesis is presently supported. |
| Actual control/tracking/thrust-reserve and recovery envelope for the admitted battery/payload and near-table domain | Whether the combined error tube remains collision-free through recovery | No. Props-off acquisition has no rotor-generated thrust or aerodynamic interaction. |

An independently referenced, timestamped props-off trace could move an exact
proposed **bench** envelope from untested to refuted. To justify one now, even
its favorable outcome would need to unlock a concrete decision path, and the
other indispensable terms would need an independently credible source. They
do not have one here. An additional stationary record duplicates #561's role;
a generic hand-carried pass cannot settle the joint flight problem. A finite
successful trace also cannot establish an unrestricted worst-case guarantee.

**Do not request a new acquisition, TEST_REQUIRED, rotor test or flight in this
phase.** This is a decision-value conclusion, not a newly imposed governance
restriction or a claim that bench data can never be useful. No checkpoint is
created or resolved; the trusted mechanism and one-open-request rule are unchanged.

## Final verdict and investment recommendation

1. **VIABLE SOUS CONDITIONS is not established:** the positive modeled domain
   lacks jointly applicable measured/specification-backed bounds and control
   margins.
2. **NON VIABLE DANS LE DOMAINE ÉTUDIÉ is not established for the physical
   mission.** Some previously declared mathematical guarantees are refuted
   within their error domains. Typical noise, conditional adversaries and
   missing evidence cannot be upgraded into a universal physical impossibility.
3. **INDÉTERMINÉ is the physical verdict:** the available evidence cannot
   demonstrate a safe C crossing or rigorously exclude every realistic short
   domain. The three missing envelopes above are the exact reopening boundary.

Recommend **suspending #70 implementation, estimator tuning, new simulation
frameworks and new experimental spending**, while retaining its Lab results and
the owner goal. Reopen substantive investment only if independently applicable
existing evidence supplies a joint domain that can close all margins, or one
specific acquisition has a demonstrated decision path despite its limitations.
Another unbounded exploration cycle is not warranted. Qualification of a future
flight would remain a separate obligation even after physical credibility were
established. #157/#72 do not inherit a dependency on this suspended research.

This dossier must receive independent exact-candidate V5 review and canonical
CI before integration. Its scientific verdict provides no self-GO.

## Sources and verification

Primary sources accessed 10 October 2026. Datasheet page numbers above are
printed pages, not zero-based PDF indexes. No source wording is reproduced as a
long quotation. Simple sensitivity calculations use the stated density/g,
one-sided noise convention and equations; they do not introduce a new device
threshold. Existing #576/#577 results and their oracle remain unchanged.

[CF]: https://www.bitcraze.io/documentation/hardware/crazyflie_2_1/crazyflie_2_1-datasheet.pdf
[IMU]: https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi088-ds001.pdf
[BARO]: https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp388-ds001.pdf
[FLOW]: https://www.bitcraze.io/documentation/hardware/flow_deck_2/flow_deck_2-datasheet.pdf
[PMW]: https://wiki.bitcraze.io/_media/projects:crazyflie2:expansionboards:pot0189-pmw3901mb-txqt-ds-r1.00-200317_20170331160807_public.pdf
[TUTORIAL]: https://www.bitcraze.io/documentation/tutorials/getting-started-with-flow-deck/
[SENSOR]: https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/hal/src/sensors_bmi088_bmp3xx.c
[FLOWDRIVER]: https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/deck/drivers/src/flowdeck_v1v2.c
[FLOWMODEL]: https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/kalman_core/mm_flow.c
[PID]: https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/controller/position_controller_pid.c
[MIXER]: https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/power_distribution_quadrotor.c
[SINTEF]: https://www.bitcraze.io/2022/01/a-modified-ekf-for-constant-altitude-flights/
[BENCH]: https://bot-motion.github.io/posts/2021/05/baro-bmp388-intro/
