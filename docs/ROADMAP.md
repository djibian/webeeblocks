# WebeeBlocks — product roadmap

This file is a compact, versioned projection of product intent, dependencies and
exit criteria. It is not a workflow-state database.

Authority order:

`PRODUCT_VISION.md -> product issues -> ROADMAP.md -> Controller execution`

GitHub commits, PRs, checks, reviews, issues and evidence describe live execution
state. Do not duplicate agent/session state, WIP counters, ownership or queues
here.

## Product priority

1. **#157 — broader useful reference-capability coverage**

#81 (Windows classroom deployment), #66 (progressive pedagogical activity model),
#80 (one-click unified classroom interface) and #79 (fully French student
interface) are validated baseline, not active priority nodes.

The #157 simulation-side C1b boundary is now established for every currently
justified student-facing generic capability. Integrated #193/#196 now establish
the machine-readable physical capability/preflight evidence path and exact
Crazyflie 2.1 identity without granting WebeeBlocks execution authority. The
capability/API surface is read-only; the underlying cflib SyncCrazyflie close
path still emits its documented safety-zero commander setpoint, so this is not a
claim that the transport emits no command packet. The substantive remaining
product boundary is real-hardware observation plus safe physical execution
continuity; do not invent additional simulation vocabulary merely to keep #157
active. A new simulation slice needs a concrete pedagogical need or
contradictory evidence.

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
implicitly prove final Firefox/Edge parity or every future artifact. Issue #81 is
closed as completed on that explicit supported boundary; later materially changed
releases may require bounded revalidation without reopening unsupported-browser
claims.

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

The reconstructed scalar `surfaceOffset` S3 classifier has now also been
physically refuted under its pre-registered props-off checkpoint. S3-A exposed a
clear ~0.23 m floor/platform range step and formed a coherent ~+0.212 m terrain
candidate, but the candidate never committed because the detector predominantly
raised its vertical-motion veto; `surfaceOffset` stayed zero and estimated Z
remained surface-relative. The S3-B/S3-C true-vertical controls did not create a
false terrain commit.

Do not retune ToF/barometer or S3 thresholds/persistence against this result and
do not proceed to motorized testing. The next causal boundary is narrower: explain
why the existing independent vertical-veto evidence rejects the true terrain
transition despite a coherent range-step candidate. The slow-vertical controls
did not expose the pre-registered observability failure that would justify adding
`rangeUp` yet.

## Near-term graph

### C1a — minimum functional pedagogical capability baseline established

- parent: #157
- evidence: the integrated capability matrix plus #163 establish the smallest
  simulation-usable baseline needed for the representative #66 progression,
  including observable Multi-ranger `front/left/right` through the existing
  generic `range(direction)` path and fail-closed unsupported directions
- exit consequence: #66 is no longer blocked by C1a and may commit the
  representative progression against this baseline
- boundary: this does **not** claim a proven physical backend. Subsequent C1b
  work has since closed every currently justified simulation-side generic
  capability gap; physical continuity/proof remains separate.

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
- target hardware: Crazyflie 2.1 + Flow Deck V2 + Multi-ranger +
  bottom-mounted Color LED Deck
- established simulation result: integrated #183 and the capability matrix cover
  every currently justified student-facing generic Runtime capability in Webots:
  takeoff/land, four-way horizontal movement, vertical movement, yaw, wait,
  bounded speed selection, Multi-ranger front/back/left/right/up and the generic
  bottom Color LED intent
- explicit exclusion: Flow Deck downward ToF remains infrastructure-only at
  current evidence because no activity has a pupil-facing downward-clearance
  objective; do not add `range(down)` merely for hardware completeness
- established physical capability/API boundary: integrated #193 and #196
  provide a fail-closed capability probe that can verify exact Crazyflie 2.1
  identity plus reference-deck capability evidence while keeping
  `executionAuthority:false` and exposing no WebeeBlocks motor/arming command
  API; the normal cflib close path still emits its safety-zero commander
  setpoint, so transport-level packet emission is not claimed read-only
- deterministic checkpoint preparation: integrated #207 restores the
  checkpoint-only `physical-capabilities-readonly` profile using the exact
  cflib source boundary and the four-wheel Ubuntu 22.04 / CPython 3.10
  capability-probe runtime closure proven on #157; this preserves
  `executionAuthority:false` and the cflib safety-zero close-path qualification
- this is checkpoint support, not evidence that a particular classroom device
  has already been observed; human checkpoint publication remains serialized by
  the governance contract
- remaining boundary: real-hardware observation, then physical execution
  continuity/safety, remain unproven and belong behind the physical
  capability/safety gate
- reopen simulation vocabulary only for a demonstrated pedagogical need or new
  contradictory evidence.

### X3 — isolate the false terrain vertical-veto boundary

- parent: #70
- established technical result: the isolated S3 `surfaceOffset` applicator and
  deterministic build oracle remain pinned to `crazyflie-firmware` 2026.08 and
  preserve the proven local-range Flow split plus pre-registered terrain and
  true-vertical controls
- established physical result: exact checkpoint #180 is FAIL; S3-A forms the
  expected terrain magnitude but the vertical veto prevents commit, while S3-B
  and S3-C do not falsely commit terrain
- next proof: use the retained traces, or if indispensable one smaller
  pre-registered props-off discriminator, to isolate which existing veto/commit
  signal rejects the true terrain transition before changing estimator structure
  or adding a new independent cue
- safety boundary: do not modify product Runtime v2, tune ToF/barometer or S3
  thresholds/persistence against the outcome, add `rangeUp` fusion/full `z/f/r`,
  or perform motorized real flight as an agent
- consequence: no stronger world-altitude capability claim is justified until
  the refuted S3 terrain boundary is replaced by a separately proven mechanism.

## Later gates kept intentionally coarse

### P — physical backend capability and safety

- parents: physical-backend product work and #70 evidence
- established prerequisite: #193/#196 provide the non-authority
  Crazyradio/deck capability/API and exact-airframe evidence path; the
  WebeeBlocks surface remains read-only and `executionAuthority:false`, while
  the cflib close path retains its safety-zero transport setpoint and no
  completed real-device observation is claimed
- depends: backend-neutral AST continuity plus demonstrated real-hardware
  capability evidence before any execution authority is introduced
- proof direction: preflight, arming/abort/failsafe and simulation/physical AST
  continuity without granting authority to student code
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
