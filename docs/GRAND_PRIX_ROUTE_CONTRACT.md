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
