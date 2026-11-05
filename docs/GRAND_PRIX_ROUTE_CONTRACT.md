# Variable Grand Prix integration boundary

The existing `CoursePlan` is host geometry. The launcher, world builder and
native evaluator exchange its **single canonical identifier**, for example
`gp-route-v2-L2000-2500-3000-TGD-s17-H2`.
`route_courses_v2.course_from_identifier()` reconstructs the complete plan and
rejects aliases, unsupported versions and invalid domains. Configuration identity
does not establish native qualification, a fresh attempt or mission success.
`reference_course(0..11)` uses this same contract, not another configuration
format. New seeds and valid length/turn/count combinations use `plan_course()`.

## Identities for the dedicated variable integration

| Boundary | Stable value or contract |
| --- | --- |
| Activity/profile ID | `progression-grand-prix-route-v2` |
| Logical `profile.world` | `worlds/grand_prix_route_v2.wbt` |
| Evaluation oracle | `grand-prix-route-v2` |
| Native evaluator DEF | `GP_ROUTE_EVALUATOR` |
| Both native robots' `controllerArgs` | One string: `CoursePlan.identifier` |
| Attempt | Fresh runtime attempt identity, separate from configuration |

These are integration contracts, **not a declaration that the variable world,
profile or evaluator is implemented**. Keep the historical U identities and
evidence intact. The logical world identity stays the same when the launcher
generates a different temporary `.wbt` path. The existing project loader compares
resolved `profile.world` values on Open; it must not select another world or
restore a historical U merely because the file is reopened.

Only native host components receive course parameters. Blockly, the pupil
workspace and the backend-neutral AST receive no seed, true direction, gate
count, route coordinates or oracle state. One unchanged `.wbb` must remain
compatible across configurations of this activity. No expert starter is needed.

## Native composition requirements

The world and evaluator reconstruct the **same** CoursePlan. They consume the
same complete named collider inventory and the same full corridor/arrival
boundary. The evaluator must verify native collider poses and dimensions before
admission. Presence of a Supervisor node alone is insufficient: an evaluator
script can fail while its node still exists. Readiness must be explicitly bound
to the active configuration and fresh attempt after the checks and confirmed
RESET; stale readiness and an absent/crashed evaluator must refuse admission.

### Boundary: native sensors belong to the flight Robot

In Webots R2025a a separate Supervisor Robot **cannot read the internal
DistanceSensor measurements of the Crazyflie Robot**. A call such as
`getDevice("range_front")` on the route evaluator refers to its own
devices, not the Crazyflie's front Multi-Ranger. See the pinned
[Webots R2025a Supervisor reference](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/supervisor.md).
The evaluator may independently inspect the scene, collider readback,
vehicle pose/velocity and available contact points through Supervisor APIs;
none of these observations establishes a live drone range sample.

The native publisher must **not** claim that its own `getDevice()`,
static PROTO sensor names, predicted Python rays or #825 test-bench traces
attest live in-attempt front/back/left/right readings. If fresh drone
ranges are necessary for a runtime safety claim, they must be measured
on the flight Robot and conveyed through a separately specified and
reviewed **host-only** channel bound to configuration, attempt and RESET.
No student Blockly, AST or project file may supply that evidence.

Before READY, distinguish scene geometry attestation from actual sensor
measurement provenance; absent, stale or evaluator-local readings must
never be labelled as readings from the flight Robot. This clarification
does not implement a new channel, waive any existing native admission
condition, authorize flight, or substitute for the real R2025a perception
and contact qualifications required by #825.

Route progress, directed H crossings, low-altitude bands, complete swept craft
envelope, collision, stable correct landing and irreversible failure remain
independent of the pupil algorithm. The native authority retains independent
LAND at exactly **210000 ms**. Matching identity strings alone proves none of
these properties.

Implementation boundaries and falsifiable exits live in [#824](https://github.com/djibian/webeeblocks/issues/824)
(native composition), [#811](https://github.com/djibian/webeeblocks/issues/811)
(oracle), [#825](https://github.com/djibian/webeeblocks/issues/825)
(native perception/contact), and [#826](https://github.com/djibian/webeeblocks/issues/826)
(Linux/profile/project files). These are independent code/validation surfaces,
not task reservations or a central execution queue.

The first Linux milestone is a safe mixed-length GD course with ordinary Blockly,
sensing, step/continue, stop/reset and real Save/Open. A failed or incomplete
pupil attempt is a valid experimentation result; it must never bypass safety.
Extend the same vertical path to the twelve configurations. Proving one winning
pupil program and obtaining pedagogical acceptance are subsequent obligations.

## Native flight admission and evaluator liveness

`grand_prix_route_flight` composes the existing U flight/PID, Runtime v2 broker,
Qt file provider, full native ground confirmation and RESET. It builds in its
own directory with `prepare_route_runtime.py`; it never generates or activates
a variable world. The shared deadline hook enables this protocol only with
`WEBEEBLOCKS_GP_ROUTE_MODE`; the historical U uses its unchanged protocol.

Native fields have one writer per direction on `DEF GP_ROUTE_EVALUATOR`:

| Field | Writer | Exact message |
| --- | --- | --- |
| `customData` | Flight | `GP_ROUTE_CHALLENGE_V1 attempt=N config=ID epoch=E` |
| `description` | Evaluator | `GP_ROUTE_READY_V1 attempt=N config=ID epoch=E time_ms=T` |
| `customData` | Flight | `GP_ROUTE_START_V1 attempt=N config=ID epoch=E start_ms=B state=admitted` |
| `description` | Evaluator | `GP_ROUTE_ALIVE_V1 attempt=N config=ID epoch=E time_ms=T` |

`ID` is the canonical identifier above, taken from the flight robot's sole
`controllerArgs` entry. The evaluator must decode it independently, compare its
own arguments and verify the complete native scene. The flight guard checks a
bounded token, not a duplicate geometry parser. `N` is the positive canonical
integer in the broker's `WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 N`. `E` is a fresh,
private 128-bit random challenge (32 lowercase hexadecimal characters), created
only during native idle/ground observations. Missing entropy refuses admission.
RESET, loss of pre-admission idle, changed attempt or changed configuration
invalidate it. A restarted flight process cannot reuse an earlier response.

Before publishing READY, the evaluator must independently check canonical
colliders/scene, sensor/contact availability, finite pose and confirmed fresh
initial/reset state. Node presence is insufficient. It echoes the exact
challenge only after these checks and refreshes READY while waiting for START.
Both READY and ALIVE require a canonical nonnegative integer native simulation
timestamp, no earlier than challenge creation, no later than the current native
time, and at most **32 ms** old. After START the evaluator must publish ALIVE
from fresh native observations; each pilot tick consumes a strictly newer
timestamp, strictly after admission. An evaluator stepping at the world's **8 ms**
basic step supplies this without writing the flight-owned field. Repeated
pre-admission idle polling therefore cannot erase READY, and an old ALIVE cannot
hide a crashed evaluator. These are product safety messages, not Controller
execution coordination.

Admission failure refuses TAKEOFF. Loss/mismatch/staleness after admission
latches `grand-prix-route-v2 status=not-achieved` and invokes the existing
independent native LAND path once; late success cannot rescue it. The flight
publishes START with `state=failed` or `state=deadline` on these terminal paths.
The **210000 ms** cap runs before ALIVE or success processing, with the existing
shortened native step at the exact boundary. Success must have been observed
with native landed confirmation before that boundary. RESET and file operations
retain the existing landing/idle fences. The evaluator must clear its own
evidence on invalid state and must not infer success from READY or ALIVE.

The controlled-channel C++ tests exercise refusal, replay, liveness, expiry and
RESET; the canonical native job also builds the complete adapter against
R2025a. Neither is a route trajectory, sensor/contact qualification, or Linux
GUI acceptance. The native evaluator publisher, active world/Robot Window and
the real Blockly/Save/Open journey remain required in #824/#825/#826 before a
variable experiment can be offered.
