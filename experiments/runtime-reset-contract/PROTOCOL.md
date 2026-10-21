# Bounded RESET contract discriminator — 21 October 2026

Base main: b478f9dd1854d83345abe13ed20fcf7baeffaca5. This is experimental
evidence, not a production change, CI Gate, historical replay or repair of #637.

## Question fixed before acquisition

Does an actuator state within the directly measured domain invalidate the
production RESET's accepted pose/motion state during subsequent idle, or break
a TAKEOFF sent on the first native step after its ACK? Compare A (body RESET)
with B (the same RESET plus public loadState of only the four motor nodes).
No assumption that nonzero angular velocity itself violates RESET is made.

The original ZIP 12303527298 was independently reverified: 25,317,049 bytes,
SHA256 1033ddddd492d0bb69251f090e49089f2d034ee5fa92371dc342ed88eb543684,
35 manifest members, unchanged source transforms and all original oracles.
Its largest absolute motor speed at an accepted RESET is 34.37361302687335.
That RESET246 receives at 357.472 s and accepts at 357.792 s; its directly read
receipt speeds are [-43.97307910799943,43.955769775850364,
-43.95630369565706,43.97361302687336] rad/s. These four values define this fixture.
They are representative measured actuator inputs, NOT a reconstruction of its
full body/contact state or of the historical failing collision.

## Minimal native arrangement and intervention

One stock R2025a Crazyflie and a horizontal plane, 32 ms/seed1/one physics
thread. Actual production C, PID and activity-scene code are compiled unchanged
through a fixture translation unit. Public-API wrappers replace only the
transport and define preparation/observations. Actual REQUEST parsing, RESET,
TAKEOFF, LAND, thresholds and responses remain production code. No browser,
additional robot, physics plugin, internal ABI access or ODE mutation.

After normal two-second sensor initialization, save each initially idle motor's
node state. Hold the body at its initial pose with public teleport/resetPhysics
while commanding the selected four targets for 70 steps. Source-derived
30 rad/s² convergence reaches these targets within 46 steps. Target/getVelocity
cache is NOT claimed to be a direct current measurement. Sensor/native pose
and actual target calls are logged. Stop all preparation when the original
RESET request is delivered. A saves a sham motor snapshot; B loads the saved
idle state. Both make four synchronous node-state calls, re-establish velocity
mode/zero targets, then let production RESET run without further intervention.
B necessarily resets other motor-controller internals too; an A/B difference
would identify this bounded motor-state operation, not uniquely currentVelocity.

Exactly four fresh processes, fixed order A-idle, B-idle, A-takeoff, B-takeoff.
Idle observes 1.6 seconds after ACK (longer than 43.974/30). TAKEOFF0.5 is
injected at the first native step after ACK, followed by normal LAND. No SCENE,
UI, mission/evaluator freshness or original negative oracle is replaced by
this fixture. Those product obligations remain separately applicable.

## Predictions, criteria and stopping

* A-idle: if the accepted state loses the original pose/motion predicates while
  targets remain zero and B does not, investigate a post-ACK contract defect.
* A-takeoff: if the original parser/controller refuses or cannot complete the
  bounded takeoff/land but B completes, investigate a motor-state interaction.
* If both complete and idle predicates remain valid, this tests compatibility
  in the selected domain, without universal guarantee or historical attribution.
  Different timings/trajectories alone are NOT a product defect: RESET does
  not promise bitwise replay or zero thrust.
* Unexpected preparation, absent/malformed/nonfinite measurements, missing
  responses or original controller errors stop immediately and are preserved.
  No replacement, blind retry, cohort extension or fifth native process.
* 5 s RESET, 250 ms continuous window, original physical thresholds, fail-closed
  errors and 25 s action timeout are unchanged. No fixture forces an ACK.
* End after these four cases or first refusal. Even a successful B cannot
  establish a repair of #637 without a relevant failing A and historical link.

Limitations: artificial held-body initialization; measured motor vector but no
collision; synchronous Supervisor logging influences scheduling; transport is
direct in-process, not RobotWindow. A/B semantics include motor-mode restoration
and finite-precision/contact evolution, with no identical ODE-state claim.
