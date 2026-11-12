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

## Host observation before the first TAKEOFF

Only the variable-route profile opts into the backend capability
`simulationAdmission: true`. Generic Runtime READY remains a connection signal,
not evidence that the evaluator has finished its continuous ground window.
Before issuing the single TAKEOFF request, this backend waits for:

```text
WEBEEBLOCKS_RUNTIME_V2 REQUEST N ADMISSION
WEBEEBLOCKS_RUNTIME_V2 RESPONSE N VALUE 0
WEBEEBLOCKS_RUNTIME_V2 RESPONSE N VALUE 1
```

Each query has one response. The route-mode native filter returns 1 only while
idle, before admission, without a latched failure, for the current attempt and
configuration and an exact private READY no older than 32 ms. It returns 0 when
unavailable. This observation neither starts the mission clock nor consumes
ALIVE, creates/rotates a challenge, clears failure, resets or moves the vehicle.
It discloses no course, oracle result, nonce or hidden geometry to Blockly.
The historical U controller does not gain this protocol command.

The host polls at 50 ms wall intervals within one existing request-timeout
budget, using a monotonic clock. Missing/malformed/unsupported responses fail
closed; they never cause an automatic TAKEOFF retry. STOP, RESET and controller
startup invalidate the captured backend epoch, including the gap between a
positive answer and sending TAKEOFF. Only read requests may repeat. The actual
native `gp_u_start` still rechecks its private current READY at the physical
effect boundary; a positive host answer is never execution authority.

Controlled WWI/timer tests exercise bounded waiting, cancellation and one-shot
effects; controlled-channel C++ tests exercise the real filter, epoch/freshness
and non-consumption. Neither establishes a GUI, native flight or Linux file
dialog PASS. An inactive/missing publisher remains unavailable, including in
an explicitly inert editor sandbox.

## Flight-owned device observations

The flight controller additionally owns the **`model` SFString of the plain
`GP_ROUTE_EVALUATOR` Robot**. The evaluator only reads it. This unused descriptive
field does not change a node's Webots type, geometry, controller or device list.
It keeps the existing CHALLENGE/START and READY/ALIVE fields unchanged. The pinned
Crazyflie PROTO does **not** expose `description`; its internal base-node fields
are read-only through `getBaseNodeField`. Do not write those fields or alter the
pinned model to invent a device channel. See the pinned
[Crazyflie interface](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto)
and [Supervisor field contract](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/docs/reference/supervisor.md).

Exact observation message:

```text
GP_ROUTE_SAMPLE_V1 attempt=N config=ID epoch=E time_ms=T period_ms=32 ground=G ranges_um=F,B,L,R,U
```

`N/ID/E` bind the same private flight context as admission. `T` is the **native
pilot observation time**, on the 8-ms world grid, not an invented per-device
acquisition timestamp. The five effective DistanceSensor periods must all be
32 ms. Values come from `wb_distance_sensor_get_value` on the flight Robot after
its native step, in front/back/left/right/up order, converted from millimetres
to metres and encoded as nearest integer micrometres. Each must be finite in
`[0, 2.001]` m, the existing Runtime range domain. This encoding does not change
the student's range results or expose the course to Blockly.

The native producer clears this field on invalid control/range observations,
wrong context, non-increasing clock, deadline or context revocation/RESET. It
uses the existing full finite pose/velocity/attitude/gyro predicates;
`ground=1` comes only from the existing continuously stable native idle/ground
confirmation. The 32-ms sampling period is unchanged. **No absolute phase-zero
assumption** is made: controller restart and the 16-ms shortened deadline step
must not make the next RESET permanently unable to emit observations.

The evaluator reads `model` from the independently verified native Robot and
uses `route_flight_observation_v2.parse_flight_observation` with the parsed
CHALLENGE/START and its current simulation time. Observation age must be in
`[0, 32]` ms. Receipt never refreshes `T`. Because Webots provides no individual
DistanceSensor acquisition timestamp, the conservative measurement-age bound is
**observation age + native sensor period, at most 64 ms**. Do not call this a
32-ms acquisition proof. The READY/ALIVE **message** freshness remains 32 ms;
the independent Supervisor's own pose/velocity/contact observations and scene
checks remain necessary. A packet alone is neither READY, RESET attestation nor
success, and an arbitrary caller's matching string is not native provenance.

The required native geometry job also runs a quarantined two-Robot transport
bench: real near/far range echoes, an off-phase step, invalid sample revocation,
stale replay, reset clearing and a new private attempt epoch. It never calls
TAKEOFF, writes READY/ALIVE, commands motors or opens Blockly. Passing this bench
establishes cross-Robot native range transport only; it cannot qualify a whole
course, flight, RESET recovery or the teacher's Linux journey.

## Native evaluator publisher and remaining delivery gate

`grand_prix_route_evaluator` uses `NativeRouteEvaluator` in
`evaluator_publisher_v2.py`. It consumes the existing coherent native sampler,
full scene/collider check, strict wire state and pure attempt oracle; it accepts
no caller-provided observation or `native_validated` flag. The sole native host
boundary supplies that flag internally after checking real readbacks.

Before READY it requires the flight-owned current attempt marker and private
epoch, five fresh drone ranges, and **500 continuous simulation milliseconds**
of native start position, upright attitude, bounded linear/angular motion,
floor-only contact coordinates and the pilot's stable-ground bit. Native steps
must advance exactly 8 ms. The fixed ground reference comes from the real
pinned centered `Cylinder(height=.03, radius=.05)` above the validated z=0
Plane; restarting an evaluator in flight cannot move that reference. A changed
body or missing Physics refuses startup. During unused startup only, a new
pilot nonce may discard a partial ground window before any READY was issued.
After authority or a refutation, only a newer runtime RESET attempt may rearm.

START must match this process's fresh READY. Missing/inconsistent observations,
lost cadence or scene changes revoke evidence irreversibly for that attempt;
the independent pilot retains LAND authority. Deadline is tested before any
first success at **210000 ms**. Directed gates, swept geometry, altitude and
terminal dwell use the unchanged pure oracle. A positive terminal additionally
requires native landed evidence. ALIVE continues with current landing evidence
after the one positive publication, until consumed by the pilot; there is no
new acknowledgement protocol. Valid ticks publish one final response without
an intermediate empty field visible to the pilot. A later fault revokes ALIVE
without repeatedly overwriting an outcome the pilot may already have latched.
The evaluator publishes a negative outcome once and only while the flight
channel still names that attempt. A RESET marker belongs to the broker and
must survive closure of an older evaluator attempt.

The existing required geometry job runs two isolated native projects with the
production evaluator class. The first keeps the real pilot **idle**: native
ground/range data must establish READY, then a genuinely moved L must revoke it;
restoring that L cannot revive the old attempt. The second wraps only the test
pilot's WWI input and outgoing ACK observation. Generated C/broker bytes must
equal production exactly; pose, sensors, PID, clocks and safety hooks are real.
It supplies **one TAKEOFF request**, waits for real native airborne/ALIVE and
TAKEOFF ACK, then stops the evaluator service without clearing its last ALIVE.
The pilot must independently fail and initiate LAND within its bounded liveness
interleaving (at most two 32-ms pilot steps); **no LAND request is injected**.
Only its genuine forced-LAND ACK permits the test's sole RESET request through
the normal broker. The same evaluator instance must then attest attempt 2, a new
private epoch and fresh ground window; the old outcome must be gone. Each case
requires unique JSON, agreeing native stdout and zero exit. No pupil program or
solution trajectory is supplied by either probe.

These are bounded automated obligations, **not a claim that they have passed**.
Even successful native probes would not qualify complete L/H flight, the twelve
courses, a successful pupil mission or Linux GUI acceptance. Before offering the
variable launcher, qualify those remaining paths, reconfiguration and the real
same-file Blockly Save/Open workflow. The Linux launcher deliberately remains
gated; no expert solution or new pupil block is supplied by this publisher.

### Trusted classroom static-scene contract — owner decision 2026-11-12

The Grand Prix is a **teacher-managed pedagogical simulation**, not an
adversarial anti-tamper authority. Its canonical static course is generated by
trusted host components. Before any READY, each native evaluator process must
independently validate the *instantiated* scene: exact course/configuration,
root and controller identities, Floor, obstacle inventory, visual and physical
collider dimensions, placement and topology, as well as the pinned vehicle model.
A failed initial attestation refuses admission.

After that successful initial attestation, the physical **static** geometry is
assumed unchanged throughout the current loaded world and its successive normal
RESET attempts. There are **no per-step VRML root exports, collider geometry
walks, static Floor checks, or per-box visual/physical remeasurements** in the
classroom evaluator. The previously attested native vehicle node/ID remains
bound to the same process, and live identity continuity is checked per tick.
A replacement evaluator process performs a new full native attestation. An
explicit activity/world switch or reload requires a new evaluator incarnation
and full attestation *before* further READY; no launcher may reuse an attestation
after a world replacement without restart.

**Assumption and limitation:** direct editing in the Webots scene tree/3D UI,
arbitrary Supervisor writes by trusted components, PROTO regeneration, or scene
change-and-restore mid-flight are **outside** the supported classroom model.
This mode does not prevent, detect or revoke those deliberate edits; any such
session is noncanonical and cannot establish pedagogical success. If reliable
in-process replacement without an evaluator restart is introduced, its lifecycle
must be addressed explicitly before that launcher is supported. This restriction
must not be misrepresented as engine-level immutability.

Every native 8-ms observation must still use fresh vehicle kinematics,
independently read contacts and flight-owned sensor samples; check time,
attempt/epoch, native vehicle/evaluator identity continuity and publication
freshness; evaluate swept-geometry route/zone/collision/landing oracles; and
enforce failed STOP/RESET/LAND and **210000-ms** deadline exactly as before.
A changed observed drone trajectory, missed step, missing sample or evaluator
loss still revokes authorization as required. **No student AST or Blockly code
may provide scene evidence or select the trust policy.**

The *historical* strict per-tick scene path remains available as a diagnostic
comparison during qualification. Its repeated root VRML export, snapshot,
PROTO/Floor and collider rechecks were originally intended to detect deliberate
between-step scene mutation. Their removal is an **explicitly accepted
pedagogical threat-model change**, not a proof of native confinement or a reason
to weaken physical-flight safety or mission oracles.

The required real publisher witness must still pass within its bounded wall
budget: 120 seconds for idle and
420 seconds for flight-reset. The latter bound follows the retained native
trace (7088 ms simulated in 113.41 s wall time, before TAKEOFF completion); it
does not alter the 8-ms cadence or 210000-ms mission limit.

The isolated witness retains elapsed wall time, wall and process CPU time for
both the step and the evaluator tick, and native observed position. It also
retains the actual outgoing pilot response buffer after
broker forwarding. These are diagnostics only, not substitutes for the original
JSON/stdout/exit, TAKEOFF/independent LAND/RESET or fresh native authority proofs.
