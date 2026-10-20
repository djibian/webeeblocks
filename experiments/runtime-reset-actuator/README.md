# #637 — actuator-state discrimination

**The historical timeout remains unexplained. These are native experimental
counterexamples and a tested intervention, not a production correction, a
historical replay or restored main health.** The production C is unchanged on
main and restored after every local acquisition.

Question, posed before acquisition: can retained actuator state survive a
root-body teleport/physics reset and create genuine motion while all commanded
motor velocities are zero? If root reset clears that state, a prepared spinning
case should settle like the zero-speed control. If it does not, native motion
and internal predicates should agree on the resulting refusal. A second
intervention restores only the four RotationalMotor node states; unchanged
RESET postconditions still determine acceptance. Each case runs once, with a
fresh output directory and no retry of a refused RESET.

The fixture deliberately holds the body at the initial pose with zero native
body velocity while preparing all four motor targets at +/-600 rad/s for 700
steps (22.4 simulated seconds), then holds this actuator preparation until the
ordinary RESET arrives. No fixture acts after that request. The speed is the
production cap but **this extreme symmetric state has not been demonstrated
in the historical flight**. It is not an initial-state reconstruction.

| Native acquisition | Observation |
| --- | --- |
| 600 rad/s, ordinary RESET | ERR RESET_TIMEOUT at +5.024 s; 157 predicate samples, pose_bad=155, motion_bad=155. Native movement agrees with GPS/predicates beyond the initial two samples. |
| 0 rad/s, same fixture | OK at +416 ms, final stable window 256 ms. |
| 600 rad/s, four motor states restored | OK at +448 ms, final stable window 256 ms. |
| Original real collision sequence + output-only motor command recorder | Seven strict RESETs, real collision 7, UNSAFE_OR_TIMEOUT, fresh attempt 8; RESET 7 at +320 ms. No RESET_TIMEOUT. |

The first 600 preparation failed before Webots launch because the derived
runner's own filename was incorrect. Its files are retained separately as
`actuator600`, never counted as a native RESET. The repaired preparation uses
`run.py`. All acquisitions and their actual scripts/C inputs are retained;
`RESULTS.json` binds compressed bytes, and each archive binds every file.
Run `python3 experiments/runtime-reset-actuator/verify.py` to check both levels
and re-run the integrated phase/contact validators offline.

## Mechanism demonstrated in the synthetic case

Pinned R2025a source is `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`:

- `src/webots/nodes/WbMotor.cpp`, `runKinematicControl`: target velocity approaches
  current velocity with bounded acceleration, capped here by maxTorque=30.
- `src/webots/nodes/WbPropeller.cpp`, `prePhysicsStep`: thrust depends on the
  motor's **current** velocity, not just its command. Crazyflie.proto has
  thrust coefficient +/-4e-5 and body mass 0.05 kg.
- `src/webots/nodes/utils/WbSupervisorUtilities.cpp`, NODE_RESET_PHYSICS:
  resets Solid descendants. The kinematic RotationalMotor current velocity is
  not reset through the Propeller branch. `WbMotor::resetPhysics` exists for
  joint reset, which does not make every non-joint motor a Solid.
- `WbMotor::reset` does explicitly clear current velocity. The tested intervention
  saves/loads the four motor nodes and re-establishes velocity mode/zero command.
  It does not restore GPS, IMU, gyro, body state, world/evaluator state or thresholds.

At +64 ms in the 600 case, native vertical velocity is 36.314527887 m/s from
zero at the previous 32 ms sample. The source model predicts current motor
speed 598.08 rad/s after two 0.96 rad/s deceleration steps:
`(4*4e-5*598.08^2/0.05 - 9.81)*0.032 = 36.31452788736 m/s`.
This agrees numerically with native motion; it is a source-model inference,
not direct motor-speed telemetry. The unphysical extreme grows to kilometres
in simulation, which further forbids treating it as the historical trajectory.

## Boundary to the real collision

The output-only recorder logs every actual `wb_motor_set_velocity` command in
the original four positives/three negatives TCP sequence. Its maximum command
is 131.204826935 rad/s over the whole acquisition. At the last unsafe boundary
(t=1248.416 s), the source recurrence estimates
`[-56.032325442,56.032716782,-55.785135803,55.785218602]` rad/s; at RESET receipt
224 ms later it estimates approximately `[-49.3123,49.3127,-49.0651,49.0652]`.
All seven RESETs succeed; the seventh finishes 320 ms after receipt. Those
numbers are inferred current velocities under the pinned source recurrence,
not direct actuator reads and not historical states. This successful real
collision does **not** justify applying the synthetic intervention as a proven
repair of #637.

The ordinary ROOT reset correctly refuses the genuinely moving synthetic body.
Clearing only finite-difference history would not cure it. A production repair
requires identifying the mechanism in a relevant failing trajectory, preserving
freshness and the negative instability oracles, canonical exact-HEAD CI and an
independent review. PR #653 acquires the internal-controller browser path with
unchanged original oracles. Keep #637 open and ordinary integrations suspended.
