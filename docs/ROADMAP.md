# WebeeBlocks — product roadmap

This file is a compact, versioned projection of product intent, dependencies and
exit criteria. It is not a workflow-state database.

Authority order:

`PRODUCT_VISION.md -> product issues -> ROADMAP.md -> Controller execution`

GitHub commits, PRs, checks, reviews, issues and evidence describe live execution
state. Do not duplicate agent/session state, WIP counters, ownership or queues
here.

## Product priority

1. **#81 — Windows classroom deployment**
2. **#157 — broader useful reference-capability coverage**
3. **#66 — progressive pedagogical activity model**

#80 (one-click unified classroom interface) and #79 (fully French student
interface) are validated baseline, not active priority nodes. The narrow #157 →
#66 prerequisite is also satisfied: the C1a simulation baseline is established.
Broader #157 C1b coverage continues incrementally and may proceed in parallel
with #66; it must not block the representative progression unless a concrete
activity demonstrates that a missing simulation capability is indispensable.

Research / later work:

- **#70 — world altitude over surface discontinuities**
- **#87 — Firefox direct `.wbb` parity**
- **#72 — teacher-authorized final real-flight activity**, gated by the
  pedagogical progression and proven physical backend/capabilities.

Controllers choose useful work from the current GitHub state and this dependency
graph under `AGENTS.md`. Parallelism and PR lifecycle are not encoded in this
file.

## Validated Windows and interface baseline

The low-end classroom reference path has now passed both real Windows gates on
the Dell OptiPlex 3050 with Windows 11, Chrome and Webots R2025a.

### W1 — coherence: PASS

Exact Windows artifact evidence on issue #81 established:

- one-action offline startup to Robot Window `PRÊT`;
- normal and step execution;
- coherent workspace/file controls during execution;
- student-facing unsupported-block handling with correction then immediate rerun;
- Open, Save As, Save and reopening of the modified project.

### W2 — 30-minute stability: PASS

The same low-end reference PC completed 30 minutes offline with repeated normal
run, step, Continue, reset, Open, Save As and Save cycles. Simulation, Blockly
interaction and the Runtime remained usable without progressive memory,
responsiveness or connection degradation. Exact artifact/run provenance and
machine/browser/Webots facts remain on issue #81.

W1/W2 therefore establish the current Chrome low-end baseline; they do not
implicitly prove final Firefox/Edge parity or every future artifact.

### Product findings discovered during W2

The three functional findings discovered during W2 were subsequently closed by
small integrated product slices and remain useful historical acceptance evidence:

1. the missing-`atterrir` generic technical error was replaced by a
   student-correctable preflight diagnostic in #129;
2. voluntary interruption of an active simulation flight was added in #150 with
   neutral `USER_STOPPED` handling;
3. purely visual Blockly moves no longer trigger the false
   `Programme modifié : Réinitialisez la simulation avant de relancer` warning
   after #144.

Do not duplicate these slices without new contradictory evidence. Their discovery
does not invalidate the W2 stability PASS.

The discriminating weak-PC benchmark recorded in #80 has also settled the
interface architecture: **option A, standard Webots GUI + automatically opened
Robot Window, is the retained classroom path; option B must not be prototyped
without new contradictory evidence**. Chrome was observed fluid on the reference
low-end Windows PC, the Robot Window opened without window hunting, and offline
relaunch worked after preparation/cache.

Chrome remains the reference browser for the current product-development phase.
Known Edge and Firefox gaps do not block Chrome-based product slices; Firefox
final same-file semantics remain tracked by #87.

The current-main F1 inventory on #79 found no remaining student-visible English
surface: the local official French Blockly messages, Runtime/project/debug UI,
activity wording and displayed sensor directions are French while internal
AST/backend identifiers remain unchanged. #79 is therefore a validated baseline;
no localization slice remains active without new contradictory evidence.

## Preserved #70 physical-research baseline

#70 has moved beyond source-only characterization. Props-off measurements on the
real Crazyflie falsified both stock UKF gate extremes:

- gate 100 followed the 20 cm raised surface in estimated Z;
- gate 20 rejected ToF but lost a strong Z reference and suspended Flow fusion,
  producing severe estimator drift.

A minimal local-surface-range Flow split then kept fresh local range available
through rejection, but stock barometer authority did not hold world Z and a
stronger barometer weighting diverged.

The next Lab candidate is therefore the pre-registered scalar `surfaceOffset`
discontinuity classifier with mandatory true-vertical-motion negative controls,
not more gate/barometer tuning. Bitcraze stable firmware 2026.08 retains the
same relevant UKF ToF/Flow semantics, so the prototype must be reconstructed and
revalidated on that current source before new physical evidence is requested.

## Near-term graph

### W3 — final Windows browser/deployment closure

- parent: #81
- depends: W1 PASS and W2 PASS (satisfied) plus the later browser boundary
  selected by current product priorities
- proof: #81 acceptance criteria can be closed without pretending unsupported
  browser behavior is proven
- note: do not expand this node while higher-value Chrome/product work remains.

### C1a — minimum functional pedagogical capability baseline established

- parent: #157
- evidence: the integrated capability matrix plus #163 establish the smallest
  simulation-usable baseline needed for the representative #66 progression,
  including observable Multi-ranger `front/left/right` through the existing
  generic `range(direction)` path and fail-closed unsupported directions
- exit consequence: #66 is no longer blocked by C1a and may commit the
  representative progression against this baseline
- boundary: this is **not** exhaustive hardware coverage and does not claim a
  proven physical backend; movement breadth, downward ranging, Color LED and
  other useful capability gaps continue under C1b unless a concrete #66 activity
  demonstrates that one is indispensable.

### B1 — declarative activity model and compact progression established

- parent: #66
- evidence: integrated #181 on `main@8eab31ca448a966063e53f039f340238ecfec833`
  plus the earlier field-option, variables/memory and open-strategy slices
- established result: eight ordered substantial `progression-*` profiles/starter
  files now form the representative simulation progression, with distinct precise
  movement, repetition, first measure/compare/decide, repeated reaction, combined
  decisions, memory and open-strategy objectives
- proof: one shared declarative activity/profile model preserves generic blocks
  and `activity/profile -> Blockly -> AST -> preflight -> interpreter -> backend`;
  starter filenames map one-to-one to activity IDs and cumulative constraints are
  contract-tested without student progress state or a graphical activity studio
- boundary: the product target is approximately 8–12 substantial activities, not
  an obligation to manufacture filler micro-exercises; add or split activities
  only for a demonstrated pedagogical need
- finality: the teacher-authorized final real-flight activity remains separately
  gated under #72 by physical backend/capability proof and any #70 result required
  by the chosen mission; B1 establishment does not claim real-flight readiness
- note: broader C1b capability work remains parallel and does not reopen B1 unless
  concrete evidence shows the representative progression is distorted by a
  missing capability

### C1b — broaden reference Crazyflie/deck capability coverage

- parent: #157
- depends: C1a; thereafter may proceed incrementally alongside #66
- target hardware: Crazyflie 2.1 + Flow Deck V2 + Multi-ranger +
  bottom-mounted Color LED Deck
- action: continue closing useful capability gaps from the integrated matrix,
  reusing existing generic semantics first and adding new student-facing
  primitives only when a demonstrated pedagogical need requires them
- proof: the capability matrix records Blockly/AST, Webots and physical-backend
  support or an explicit justified exclusion for each relevant capability
- simulation direction: where relevant, student-facing capabilities have an
  observable Webots equivalent; Color LED coverage may use a simple,
  reasonably recognizable bottom-deck model with a visible controllable light
  surface rather than detailed electronics simulation
- scheduling: broader coverage must not block #66 once C1a is satisfied.

### X3 — reconstruct and validate the minimal surface-offset Lab prototype

- parent: #70
- depends: preserved S1/S2 physical evidence and current Bitcraze stable source
- action: reconstruct the isolated S3 `surfaceOffset` candidate against
  `crazyflie-firmware` 2026.08, preserving the proven local-range Flow split
  and the pre-registered terrain/true-vertical-motion controls
- proof: fail-closed patch/applicator or equivalent isolated artifact against an
  exact upstream SHA, with static/build evidence and logs exposing local range,
  offset/classifier state, ToF/Flow diagnostics and the independent vertical
  cues required by S3-A/S3-B/S3-C
- safety boundary: do not modify product Runtime v2, tune ToF/barometer against
  outcomes, or perform motorized real flight as an agent
- real-world boundary: only after the reconstructed candidate is deterministically
  executable can a supported human-checkpoint profile be added for a new
  physical trace; until such preparation exists, the profile must fail closed.

## Later gates kept intentionally coarse

### P — physical backend capability and safety

- parents: physical-backend product work and #70 evidence
- depends: demonstrated Crazyradio/deck capability path and backend-neutral AST
- proof direction: capability contract, preflight, arming/abort/failsafe and
  simulation/physical AST continuity without granting authority to student code
- expand only when this becomes near-term work.

### FF — Firefox same-file project semantics

- parent: #87
- depends: preserved native-bridge/browser evidence
- proof direction: causal diagnosis first, implementation only after a viable
  same-file path is proven
- keep deferred while higher-value work remains executable.

### R — final real-flight activity

- parent: #72
- depends: coherent progression + relevant #157 capability coverage + proven
  physical backend + any #70 capability required by the chosen final mission
- proof direction: exact simulation-validated student program, explicit teacher
  authorization, independent preflight/failsafe and representative safe real
  execution
- do not decompose the detailed final course before these gates converge.

## Roadmap maintenance rule

When evidence changes a product prerequisite, update the smallest affected
roadmap fragment before relying on the old dependency. Completed nodes may be
condensed into the validated baseline because GitHub history preserves their
evidence.

Do not add manual READY/BLOCKED/DONE states, agent ownership, WIP counters,
session handoffs or execution queues to this file.
