# RESET architecture audit — Webots R2025a

Examined upstream tag R2025a, peeled commit
`c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, including its bundled ODE.
Examined WebeeBlocks main `b478f9dd1854d83345abe13ed20fcf7baeffaca5`.
No upstream fault is presumed from the difference between body and motor state.

## Public promises and exact implementation

All upstream links below are pinned to that exact source, not `master`:

| Mechanism | Source and consequence |
| --- | --- |
| Node resetPhysics | [supervisor documentation](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/docs/reference/supervisor.md#wb_supervisor_node_reset_physics), lines 1397–1406: stops physics-enabled bodies' linear/angular velocity. The reset matrix explicitly makes Motor/Propeller reset N/A for physics-only reset. No promise of motor extinction, controller restart, seed reset or full state restoration. |
| Public request | [supervisor.c](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/controller/c/supervisor.c), 2697–2713: sends and flushes the node request synchronously. This does not refresh local C sensor variables already read by WebeeBlocks. |
| Engine dispatch | [WbSupervisorUtilities.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/utils/WbSupervisorUtilities.cpp), 1000–1022: resets Solid nodes and descendants, temporarily pauses their physics; not an invocation of resetPhysics on every arbitrary descendant device. |
| Body reset | [WbSolid.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbSolid.cpp), 2260–2341: zeros body velocities, accumulated force/torque, resets attached joints and handles body activation. It does not traverse Propeller motor state as a joint. |
| Joint motor distinction | [WbJoint.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbJoint.cpp), 108–114, calls motor.resetPhysics; [WbMotor.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbMotor.cpp), 845–847, zeros mCurrentVelocity. Existence of this method does not imply a Propeller path calls it. |
| Actual motor state | WbMotor.hpp, currentVelocity, returns mCurrentVelocity. WbMotor.cpp 471–521 ramps it towards target, with a 1e-6 deadband. Kinematic acceleration is min(configured acceleration, available motor force/torque); -1 falls back to the latter. Stock Crazyflie acceleration=-1 and maxTorque=30 yield 30 rad/s², NOT an instantaneous stop. [Public motor documentation](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/docs/reference/motor.md), kinematics section, documents this fallback. |
| Forces on following steps | [WbPropeller.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbPropeller.cpp), 200–247: updates motor current, computes thrust and torque from it, and adds force at centerOfThrust plus resisting torque to the ODE body. Resetting the body's existing force accumulator does not suppress future additions. Stock coefficients have zero advance-speed term; total upward scalar thrust is 4e-5 sum(omega_i²) for the intended rotation signs. Mass is 0.05 kg. |
| Broader motor restoration | WbMotor.cpp 806–820 reset(id) clears current and PID/mode internals, sets target velocity to maxVelocity and target position to the saved/current position. Public loadState invokes node.reset. A motor-only loadState must re-establish velocity mode and zero targets; it is broader than assigning currentVelocity=0. Never transplant the experimental operation without examining its other effects. |

## Ordering and contacts: an additional important boundary

`WbSolid::postPhysicsStep`, 1956–1967, explicitly performs a second body reset
after the paused step, then clears artificial disable. Its source comment
explains why: moving a Solid and resetting it in the same step could otherwise
let ODE overwrite velocities/forces through the teleport's jerk. Consequently
the immediate zero-body observation is neither proof of motor extinction nor
proof that the body remains unaffected on later steps.

`WbSimulationWorld.cpp`, 218–274, processes immediate requests, calls Solid and
Propeller prePhysicsStep, runs the physics plugin, steps the simulation cluster,
calls plugin stepEnd, then Solid postPhysicsStep and finally advances time.
An observer at plugin stepEnd and a controller reading after the step are not
automatically observing the same phase of the reset; do not equate timestamps
without specifying those phases.

`WbSimulationCluster.cpp`, 109–129, uses `dWorldStepAndSpaceCollide`, swaps its
contact buffers and empties the older contact joint groups. Bundled ODE
`src/ode/ode/src/ode_MT/ode_MT.cpp`, 262–299, in its non-MT branch steps then
collides to prepare contacts. `WbOdeContext.cpp`, 101–120, empties enabled-body
groups conditionally. The node RESET handler is not a global contact-buffer or
solver reset. Neither old contact candidates nor absence of a reported contact
at one instant establish the actual constraint forces across an interval.

Bundled `ode.cpp` dBodySetLinearVel / dBodySetAngularVel / dBodySetForce /
dBodySetTorque assign their respective body arrays. They do not own Webots'
WbMotor state. Nothing in the inspected contract or these observations
demonstrates an ODE implementation fault, stale-contact fault or invalid solver
step. Such possibilities require distinct failing evidence, not terminology.

## What WebeeBlocks actually accepts

The main C REQUEST_RESET handler commands zero targets, teleports/restores body
physics, turns the LED off, reinitializes its PID and command/clock state, then
enters CMD_RESET. It accepts only after the existing pose/motion predicates
remain true for >=0.25 s, and refuses after >5 s. These predicates concern
position, attitude, horizontal/vertical motion and yaw rate. They do not require
zero propeller forces or equality of every hidden motor/world state. In
particular, they do not measure all three angular velocity components.

Sensors are read before WWI request processing. The receipt-step locals precede
teleport, and the first following GPS finite difference crosses it. Subsequent
samples determine the unchanged stability window. Source and acquired controls
do not connect those first transients to the historical five-second refusal.

At the backend, reset invalidates pending operations, scene identity, elapsed
observation epoch and outcome/failure-probe authority. A fresh attempt and its
evaluator identity are distinct from bitwise restoration of the entire simulator.
Reset does not restart every world controller or reset time/random seeds.

**ACK with nonzero thrust is therefore compatible with the implemented current
contract when its pose/motion/freshness conditions hold.** Nonzero thrust alone
does not refute it. A bounded subsequent excursion, false fresh outcome or
failure of a valid immediate next command could refute a useful product
guarantee. That consequence must be demonstrated rather than assumed.

The product requires safe, deterministic scene restoration and usable reruns;
it does not explicitly promise identical microscopic actuator states, identical
liftoff timing or an infinite future stability invariant after one sampled
window. Choosing a stronger motor-extinction postcondition now would be a
prospective design decision, not a proven repair of #637.

## Classification

* A — External conformity: established for the observed retained-current
  mechanism, from public documentation, source and direct acquired measurements.
* B — Incomplete WebeeBlocks API use: not established relative to its current
  explicit acceptance conditions. Body reset would be insufficient for a new
  requirement of complete actuator-state restoration, but that is a different
  requirement requiring its own justification.
* C — Webots/ODE defect: not demonstrated.
* D — Ordering: transient body disable/re-reset, sensor locals and contact
  buffering are identified mechanisms. Their responsibility for historical
  #637 remains unproven.

Overall verdict concerning a product defect: **INDETERMINATE**. No causal
production correction is justified by this audit. This is not a claim that
the historical failure was harmless or that current main is healthy.
