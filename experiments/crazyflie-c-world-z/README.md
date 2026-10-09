# Candidate C: independent world-Z observer and falsification bench

**Lab-only software prototype, 9 October 2026. No qualified table crossing.**

This implements two small vertical observers in portable C, reuses the official
Bitcraze IMU attitude algorithm in a hosted replay, and separates local range
from world altitude. It demonstrates a correct separation of software inputs,
retains concrete counterexamples, and identifies the missing physical bounds.
It is not wired to the product Runtime, Commander, a drone, or a flashing tool.
No new firmware, parameter write, motor action or checkpoint is requested.

## Scope and authority

Owner D1–D3 are integrated by #574 at
`main@035da9ef33a8f316dc9dcebf8fdb323e477ab4bc`. The contract was reconstructed
again at `4580667aaf0d541b940d7936476c2d13ebd8c8bd` (#573 adds only the bounded
#572 front-observation report). Current #70 and #72 agree with candidate C only:
IMU/barometer world-Z, local lower range for Flow, no A/B, ceiling or added
navigation hardware. #157 qualification and #72 on uniform floor remain separate.

The [owner decision](../../docs/DECISION_FINAL_FLIGHT_ALTITUDE_2026-10-09.md),
[vision](../../docs/PRODUCT_VISION.md), [roadmap](../../docs/ROADMAP.md) and
[V5 contract](../../AGENTS.md) retain authority. This research provides no GO,
human PASS or inferred flight permission. It changes no X3 threshold, historical
verdict, health guard or checkpoint mechanism.

Evidence labels below distinguish **D** (equation/source demonstration under its
hypotheses), **S** (declared simulation), **O** (retained observation/descriptive
replay), and **U** (unresolved physical property). A successful software oracle
proves its bounded claim, not the target capability.

## Reproduce

Python 3.10+, a C11 compiler, and the exact upstream checkout are sufficient.
The computation is offline after the checkout; no Python third-party packages
or radio libraries are imported. Run from the WebeeBlocks root:

```sh
git clone --branch 2026.08 --depth 1 \
  https://github.com/bitcraze/crazyflie-firmware.git /tmp/c-world-z-firmware
python3 experiments/crazyflie-c-world-z/test_research.py \
  --firmware /tmp/c-world-z-firmware -v
python3 experiments/crazyflie-c-world-z/research.py \
  --firmware /tmp/c-world-z-firmware --output /tmp/c-world-z-results
```

`upstream.json` locks the exact commit and SHA-256 of thirteen relevant files.
The hosted build rejects another commit or changed source bytes. All nineteen
#561 manifest entries are checked before raw input replay. `results.json` here
retains derived results, separately from original evidence. CI recomputes them
and publishes the full twenty-case simulation CSV (14 vertical, 6 attitude)
as a host-only artifact
named for the exact candidate SHA, behind canonical `CI Gate`.

`test_research.py` requires both successful nominal cases and negative cases:
analytic dynamics, covariance, input/time failures, frame conventions, actual
stock measurement-model coupling, structural input separation, true/mixed
vertical motion, biased pressure, depth mixtures and the original archive.

## Official source reconstruction

The inspected release is `2026.08@54f31e243a0b28b67efef5ba20dbb6d9890a5478`.
Master was separately resolved at `f6e0f0a3b526861328caf3296a7ecf00bb915d39`:
the selected ToF/Flow, EKF/UKF, attitude and PID paths are unchanged. The sensor
driver difference moves a gyro-bias object into another memory region; it does
not add a vertical reference. No future release behavior is presumed.

| Path | Verified behavior and consequence (D) |
| --- | --- |
| `sensors_bmi088_bmp3xx.c` | Gyro bias calibration; accelerometer magnitude scale, alignment and 30 Hz software LPF. BMI088 acceleration ODR 1600 Hz/OSR4, gyro ODR 1000 Hz/bandwidth 116 Hz; software gyro LPF 80 Hz. Acceleration is specific force, not world acceleration. |
| BMP3xx acquisition | Configured 50 Hz, pressure oversampling 8×, IIR coefficient 3. Filtered measurements, repeated readings, processing clock and producer clock must be distinguished. No chip identity or in-flight pressure error is measured here. |
| `estimator_kalman.c` | Prediction 100 Hz with IMU subsampling. `KALMAN_USE_BARO_UPDATE` is disabled by default. Changing `kalman.mNBaro` alone does not enable barometer fusion. |
| `kalman_core.c` | Barometer model is `asl-reference-Z`; reference resets when not flying. The flight prediction assumes dominant body-Z thrust; props-off hand motion is not a faithful replay of that flight model. Covariance mixes world position, body velocity and attitude error. |
| `mm_tof.c` | Predicted range uses Z, tilt and a cone approximation. It treats the measured surface as the reference floor. |
| `mm_flow.c` | Translational scale uses `R22/Z`, Z clamped to 0.1 m; Jacobians involve both Z and velocity. Gyro rotation and camera lever arm are included. |
| `estimator_ukf.c` | ToF innovation gate rejects altitude updates and sets `flowActive=false`; Flow can remain disabled over the whole table. Barometer variance defaults to 6.25 m², with an independent gate. Biases are initialized; pressure is not an independently observed reference. |
| `flowdeck_v1v2.c` | Axis conversion, 0.1 pixel resolution in the model, raw delta outlier test, motion flag, and frame dt from `usecTimestamp()`. `squal` does not certify one depth. |
| `zranger2.c` | 25 ms range budget, range values below 5 m enqueued; this path does not retain full return-status validity. A fresh finite range need not represent Flow depth. |
| `sensfusion6.c` | Default Mahony attitude uses gyro/acceleration only. It is reusable for input independence, but sustained horizontal acceleration can masquerade as tilt. Absolute yaw and unbiased tilt are not guaranteed. |
| PID/HLC | The position cascade consumes estimated Z and VZ, while XY errors request tilt. Another Commander mode or controller cannot manufacture a missing vertical observation. |

Source links are generated by prefixing the locked paths in `upstream.json`
with `https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/`.
Also inspected: [official state estimation documentation](https://www.bitcraze.io/documentation/repository/crazyflie-firmware/master/functional-areas/sensor-to-control/state_estimators/).

Hosted scope: `mm_flow.c` and `mm_tof.c` are compiled unchanged against a minimal
type shim and standard scalar KF/Joseph algebra. This is a replay of the real
measurement functions, **not the full EKF propagation/finalization/supervisor**.
Mahony is the real source, with two explicitly checked host portability changes:
its 32-bit `long`/aliasing inverse-square-root casts become binary32 `memcpy`
operations. The bit operation and algorithm are preserved. A host-only reset
makes repeated experiments reproducible; it is not a firmware parameter.
The C3 experiment additionally disables Mahony's accelerometer correction in
the host, after stationary settling; this is an explicit derived variant,
not the default official attitude behavior or a deployed firmware change.

## Equations and architecture

World Z is up. At a local horizontal plane, lower depth is `c=z-h`. A lower
range does not distinguish real motion from surface height. C never uses it as
a world-Z input, including at a return edge. It never classifies terrain and
then secretly fuses a corrected range as an altitude observation.

With a quaternion from the independent IMU-only path:

`a_m = 9.81 * (e3ᵀ R(q) f_g - 1)`.

`world_z_project()` uses all acceleration axes and normalizes the quaternion.
Attitude, accelerometer calibration and time alignment remain physical error
sources. In particular, using acceleration magnitude instead of projection
would not be a generic solution: horizontal acceleration changes the magnitude.

**C1: bias-aware linear Kalman observer.** State is `[z,v,b_a]`:

`z_dot=v; v_dot=a_m-b_a; b_a_dot=w_b; y_baro=z+b_p+n_b`.

The exact constant-input transition is
`F=[[1,dt,-dt²/2],[0,1,-dt],[0,0,1]]`. Continuous acceleration and bias process
noise are integrated analytically; measurement updates use Joseph covariance.
The barometric origin is frozen from prior calibration, never reset at a table
edge. This avoids the stock hand-carried barometric-reference trap.

For constant known pressure datum, `[H;HA;HA²]` for `[z,v,b_a]` has rank three.
Adding a constant unknown `b_p` gives rank three out of four, with gauge
`[1,0,0,-1]`. Fixing an initial datum removes a constant gauge, not changing
pressure. Adding more bias states does not create an independent measurement.

The initial C1 design profile is explicit in `research.py`, with acceleration
noise density, bias noise density and initial uncertainty. It is an exploratory
comparison profile, not a sensor calibration or a fitted physical bound.
Treating correlated BMP IIR/pressure samples as independent noise is a model
limitation; C1's covariance is demonstrably not a physical acceptance oracle.

**C2: very slow complementary correction.** After C1 was refuted by the replay,
the second exploratory observer keeps the acceleration bias fixed from prior
stationary calibration and uses pressure only weakly:

`z_hat_dot=v_hat+2ω(y_b-z_hat)`;
`v_hat_dot=a_m-b_a0+ω²(y_b-z_hat)`.

`ω=0.01 rad/s` (100 s pole time) deliberately limits authority during a short
crossing; it is not tuned on a successful window and is not a confirmation
result. Its C implementation performs explicit sampled fixed-gain corrections;
it does not freeze Z, impose VZ=0 or infer stillness from a setpoint. The error
dynamics have characteristic polynomial `(s+ω)²`. The pressure transfer is
`(2ωs+ω²)/(s+ω)²`, the acceleration-error transfer `1/(s+ω)²`.
Thus low pressure authority also means weak suppression of residual IMU bias.

For `0≤ωT≤1`, the continuous observer has the conditional bound

`E_z(T) ≤ exp(-ωT)*[(1-ωT)E_z0+T E_v0]`
` + B_a*[1-(1+ωT)exp(-ωT)]/ω²`
` + B_p*[1+(ωT-1)exp(-ωT)]`.

This follows by integrating the impulse responses (positive over this horizon).
`B_a` must include bias, attitude/projection, vibration and acceleration model
error; `B_p` must include origin, pressure, sensor dynamics and lag. Sampling,
timing and controller/airframe response still require separate allowances.
Neither this expression nor the internal covariance validates those bounds.

**C3: C2 with bounded gyro-only attitude propagation.** An IMU-only attitude
can still confound horizontal acceleration with gravity. The hosted variant
retains official quaternion gyro propagation after initial stationary alignment,
then disables the accelerometer gravity correction during the declared horizon.
It removes that particular feedback, at the cost of accumulating gyro bias and
initial tilt errors. It is not an altitude hold or a terrain-based switch.
Neither the 0.1 degree/s injected bias nor initial alignment is a measured bound.
Calibration, bias stability, timing and full mission duration must be bounded
before using this route; a larger bias is retained as a counterexample below.

**Horizontal path.** `local_flow_velocity()` inverts the official close-level
single-plane optical model using fresh local **slant** depth, gyro rotation and
lever arm, with no world-Z argument. The separate vertical state/covariance and
IMU-only attitude cannot be changed by Flow innovations. It checks time, depth,
tilt and an externally established single-plane validity precondition. That
precondition is intentionally explicit: **a production autonomous detector is
not implemented or validated here**. Raw `squal` or a small range innovation
cannot establish it. The function is a measurement adapter, not an onboard
horizontal navigator, odometry confidence model or safe recovery controller.

Simply removing `H_z` in a joint EKF would not provide this separation:
`K_z=P_z,* Hᵀ/(H P Hᵀ+R)` may remain nonzero. The hosted counterexample gives
a 6 cm Z correction for a 0.2 m/s velocity residual with `H_z=0`.
Structural input separation also does **not** imply physical decoupling: an
XY correction can tilt/accelerate the real drone and disturb pressure/world Z.

## Results retained, including failures

### Existing observations

All 97 historical #70 comments were retrieved. Relevant source conclusions,
owner observations, the 9 September independent architecture analysis, archive
audit and later X3 outcomes were examined. The two 8 October scientific
dossiers were also read: `Dossier-decision-altitude-Crazyflie.pdf` and
`Dossier-decision-franchissement-sans-plafond(1).pdf`. Their proposed ceiling/A/B
directions are superseded by D2; their coupling/error-budget evidence is useful.

Keep these distinctions: stock gate 100 followed the surface; gate 20 lost Flow
and drifted; S1 established a local Flow depth path, not world-Z/metric XY;
S2 failed its stronger-barometer configuration, not all possible C observers.
#180 is a terrain FAIL. #236/#251 are diagnostic PASS only. #550/#561 are FAIL.
The gap before #561's -2.814 m health rejection remains unobserved; the replay
does not diagnose its cause. #554/#566 motorized FAILs remain separate evidence.
The old #180/#236/#251 archives lack continuous independent IMU/barometer inputs;
see [the complete archived-input audit](../crazyflie-ukf-surface-range/evidence/analysis-2026-09-11/README.md).

### #561 replay (O, not a flight error measurement)

15016 IMU and 7508 barometer rows are used. Calibration is fixed on device-log
seconds 20–50, then **every** 0.1 s anchor in `51..117-T` is evaluated for each
declared horizon. Each table entry is the maximum absolute **terminal** nominal
displacement across those windows, not the maximum trajectory displacement
inside a window or a physical position error. All overlapping windows are
retained; some anchors lie outside independently witnessed stationary holds.
Initial VZ is nominally
zero at each anchor; this is a diagnostic assumption, not a measured flight
velocity. No pose, ToF, UKF Z/VZ or UKF attitude feeds the vertical replay.

Mahony is replayed at the recorded 100 Hz rate, not the actual 250 Hz firmware
attitude scheduling. The producer timing is unvalidated. The archive's independent
hold witness is not used to manufacture a time-aligned certified error bound.
Barometer plateau differences compare the 0.5 s **before** start and the 0.5 s
**after** end; this differs from the October dossier's window convention and
does not modify the frozen X3 statistic or its 1 s latency criterion.

| Horizon | C1 maximum nominal displacement | C2 maximum nominal displacement | IMU-only maximum nominal displacement |
| --- | ---: | ---: | ---: |
| 1 s | 1.71 cm | 0.71 cm | 0.65 cm |
| 2 s | 15.95 cm | 1.87 cm | 1.51 cm |
| 3 s | 41.01 cm | 3.29 cm | 2.47 cm |
| 4 s | 62.08 cm | 4.70 cm | 3.72 cm |
| 5 s | 74.63 cm | 6.32 cm | 5.09 cm |
| 6 s | 82.94 cm | 8.56 cm | 6.71 cm |

C1 is rejected as a promising fast world-Z reference for this retained domain.
The C1 continuous replay after calibration (without rolling resets) ranges
approximately -0.814..+0.451 m. C2 offers short-horizon software behavior worth
retaining, but already exceeds 5 cm nominal displacement at 5–6 s. A new
confirmation dataset would be required after any data-driven design selection.
The continuous C2 replay ranges -0.0165..+0.6057 m despite ending at +0.0132 m.
Its small final displacement is not evidence of bounded altitude throughout.
C3 is not evaluated against this archive as a physical flight-error measurement.
No percentile from overlapping windows is a failure probability or confidence.

### Simulations (S)

| Injected case | Result / implication |
| --- | --- |
| Both table edges, ideal inputs | C1 world-Z unaffected by range; nominal error below 1 µm. This proves separation in the model, not sensor accuracy. |
| True 20 cm vertical movement + table | C1 maximum error ~6.2 mm; it follows real vertical motion rather than silently assuming stationary altitude. |
| 30 cm pressure-altitude step | C1 maximum false altitude ~38 cm. In the declared ideal PD/double-integrator loop, real altitude excursion ~46 cm. |
| Same pressure step, C2 | False altitude ~3.4 cm over the 8 s simulation; ideal-loop real excursion ~3.0 cm. C2's reduced pressure authority has a useful effect. |
| 1 mg residual acceleration bias, C2 | ~30 cm error by 8 s. Slowing pressure cannot remove the inertial drift trade-off. |
| C1 barometer dropout 3 s + 5 mg | Maximum error ~53 cm including reacquisition. A finite `healthy` state is not safe recovery. |
| Mahony + C2, sustained external horizontal force at level | ~1.14 m false Z over 8 s. This force model refutes generic projection reliability; it is not representative quadrotor thrust. |
| Mahony + C2, tilted acceleration/cruise/braking | ~1.43 cm false Z with true vertical acceleration zero; ~1.20 m horizontal travel. This ideal thrust case isolates acceleration/gravity feedback, without rotor pressure or vibration. |
| C3, same tilted pulse, injected gyro bias 0.1 degree/s | ~3.29 mm maximum false Z. This is a conditional simulation, not a measured gyro bound. |
| C3, same pulse, injected gyro bias 1 degree/s | ~41.4 cm maximum false Z. Gyro-only propagation cannot remove the need for validated attitude/error bounds. |
| Single plane with local range | Correct metric velocity in the ideal model, including gyro/lever-arm roundtrip. |
| Mixed image depths, trusting nearest ToF | Velocity error up to ~0.43 m/s for true 0.4 m/s; net odometry error ~17.5 cm in the constructed out-and-back surface scenario. Good image quality is insufficient. |
| Reject known mixed-depth intervals | An assumed 5 mg coast still yields ~7.1 cm odometry error. The scene oracle is simulation-only, never claimed autonomous. |

The closed-loop model is a deliberately labeled ideal bounded PD/double
integrator, not a replay of Bitcraze PID, thrust distribution, motors, ground
effect, battery, multi-axis dynamics or safe landing. It is a causal
counterexample, not a flight-stability claim. Flow cases test measurement scale
and integrated odometry error, not a full closed-loop XY mission.

### Fundamental impossibility domain (D)

Let `δ(t)=0.1*(1-cos(πt/4))`. The transformations
`z'=z+δ`, `b_a'=b_a-δ''`, `b_p'=b_p-δ`, `h'=h+δ` produce identical vertical
IMU, barometer and local range signals but differ by 20 cm world-Z at 4 s.
The maximum bias term is about 6.29 mg; the pressure-altitude difference is
20 cm. These are **constructed admissible disturbances if such bounds are
unvalidated**, not measured disturbances of this drone.

This refutes a universal guarantee over unrestricted unknown terrain/pressure/
time-varying biases. It does not refute all short crossings of a fixed table
with independently established bounds. The unknown-height surface can be
interpreted along a path; the theorem does not silently assume a known two-plane
map or prove impossibility for every fixed two-plane geometry. Nor does a new
EKF/UKF remove this information limit.

## Physical budget, stop rule and what remains indispensable

Before a crossing is credible, define the entire horizon: start, approach, both
image-depth transitions, table width, exit, braking, hover and recovery. C cannot
reset/reanchor on a presumed returning floor, since that would make lower range
a world-Z reference or require excluded geometry. Recovery/landing must stay
within the same independently bounded vertical lifetime.

For IMU-only propagation the conditional bound is
`E_z0+E_v0*T+0.5*B_a*T²`. Even the illustrative assumptions `E_z0=5 mm`,
`E_v0=2 cm/s`, `B_a=1 mg`, with **no other allowance**, permit only ~1.61 s for
5 cm and ~2.81 s for 10 cm. These are not the drone's measured limits. The 5 cm
value is retained as a historical comparison quantity, not declared a new
qualified mission tolerance. Clearances, body radius, braking and controlled
recovery must determine and preregister the actual flight acceptance envelope.
The analogous C2 bound additionally includes pressure and is wider here.

Approximate 42° image aperture at 1.10 m gives ~0.84 m floor footprint; at
0.4 m/s its traversal alone is ~2.1 s per edge, before a table plateau or
recovery. This is a warning from the official approximate model, not a calibrated
FOV/safe-speed prescription. Neither slowing indefinitely nor accelerating to
hide drift is a justified autonomous solution.

Indispensable U before **any** possible qualification:

1. Independent initial VZ/bias and IMU-only attitude/projection bounds across
   temperature, real acceleration, timing and representative flight vibration.
2. Pressure/datum/filter-lag bounds over the **full mission plus recovery**, with
   correlated errors; props-off results do not establish rotor pressure or
   ground-effect behavior. High pressure authority is currently refuted.
3. Autonomous treatment of mixed-depth Flow, optical return status/freshness,
   gyro synchronization and uncertainty; no ground-truth scene oracle is allowed
   in a product candidate. Prove the associated XY/coast/reacquisition budget.
4. Onboard integration/build/resource compatibility with simultaneous Flow V2
   **and Multi-ranger**, measurement scheduling/age, typed logs and consistent
   Z/VZ/attitude output. No host binary is a flashable firmware candidate.
5. Reviewed sensor-loss, duration-expiry and controlled recovery, plus current
   #157 safety/firmware/teacher qualification and an exact authorized checkpoint.

The smallest potentially useful **future props-off discriminator** is one
continuous acquisition, one declared preparation/settle, prior stationary
calibration, both signs of true vertical displacement, terrain-only transitions,
one mixed segment and return to the original independent rest reference. Retain
all IMU/baro/range/Flow deltas/quality timestamps and preparation evidence; use
simple fixed supports/marks for independent plateau displacement and a stated
uncertainty. A 5 cm transient/1 s claim would need corresponding continuous
reference resolution, not invented precision from plateaus. No X3 guard is
bypassed and no legacy FAIL is reinterpreted. This is a discriminating protocol
outline, not an executable checkpoint request or qualification procedure.

It could reject C2/C3's projection/dynamic response but cannot certify in-flight
disturbance bounds. Before spending on such data, the mission/recovery horizon
must fit a credible **unvalidated-but-defensible** error budget. If it already
cannot, stop that domain without a physical repetition. The live one-open-human-
test rule and #572 remain unaffected; no human-test queue is created.

**Conclusion:** retain C2/C3 as experimentally implemented bounded research
routes, C1 as a reproducible refutation, and structural Flow/world-Z separation
as a software result. A general reliable table crossing is not demonstrated.
Without independent error/horizon/XY/recovery bounds it is UNPROVEN; for the
unrestricted disturbance domain above, a guarantee is impossible. Keep table
flight unavailable, with no implicit A/B fallback and no change to #72 on uniform
floor. Further firmware features are not justified merely to make more code.
