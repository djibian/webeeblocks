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
justified student-facing generic capability. Integrated #193/#196 establish the
machine-readable read-only capability evidence path and exact Crazyflie 2.1
identity; #238/#241/#243/#244 establish intent-dependent exact-AST preflight,
canonical AST binding, fresh connected-descriptor acquisition on each preflight
and reconnect invalidation through an opaque connection epoch; #246 provides the
concrete host-side non-authority live Crazyradio session that owns that epoch,
invalidates it on disconnect and rebuilds capability descriptors from the current
connection; and #249 wires the production physical submission path to that live
session, binding the exact current activity profile and semantic workspace AST and
re-asserting both together with the connection epoch immediately before any later
separately authorized effect. All of this remains non-authority with
`executionAuthority:false`. The underlying cflib SyncCrazyflie close path still
emits its documented safety-zero commander setpoint, so this is not a claim that
the transport emits no command packet. The substantive remaining product boundary
now starts after that validated pre-effect assertion: a separately authorized
physical effect consumer plus explicit teacher authorization before any
flight-capable command/effect, firmware-independent arming semantics, an
independent emergency-stop watchdog/liveness guard, controlled normal
land/disarm behavior and proof of safe real execution continuity. Stock brushed
Crazyflie 2.1 auto-arms when pre-flight checks pass, so teacher authorization
must not be modeled as merely approving a host arming packet. Do not invent
additional simulation vocabulary
merely to keep #157 active. A new simulation slice needs a concrete pedagogical
need or contradictory evidence.

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

The reconstructed scalar `surfaceOffset` S3 classifier remains physically
refuted as a terrain solution, but the causal boundary is now narrower. Exact
props-off discriminator checkpoint #236 passed its diagnostic purpose: three
valid S3-A terrain repetitions emitted the split VZ, BARO and BOTH veto reasons
without any terrain commit. VZ was not reproducibly dominant (one terrain run
reached BARO veto without VZ/BOTH), while the barometer branch participated in
all three terrain repetitions. In contrast, the pre-registered S3-B fast and
S3-C slow true-vertical controls stayed below the stock ToF rejection gate, never
entered SUSPECT and never committed a false terrain offset.

That evidence shows the current late VZ/barometer veto is not a reliable
terrain/vertical discriminator: both cues can participate in rejecting a true
terrain transition, while the valid S3-B/S3-C controls are separated earlier by
the existing UKF ToF gate and never exercise the late commit veto. This does not
prove that simply deleting the late veto is safe for every true-vertical case.
Do not retune ToF/barometer or S3 thresholds/persistence against this result and
do not proceed to motorized testing.

The next causal step is therefore a bounded **classifier-evidence/temporal
redesign**. Preserve the proven local-range Flow split and existing safety
boundaries, and change only the evidence or timing used to distinguish a terrain
step from true vertical motion after ToF rejection. Any experimental candidate
must state its discriminating hypothesis before testing and include a control
that actually exercises the revised late-decision path; repeating S3-B/S3-C
alone is insufficient if they remain below the ToF rejection gate and never
enter SUSPECT. No `rangeUp`, z/f/r extension, threshold sweep or
Runtime/controller change is justified by #236 alone.

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
- established physical capability/API boundary: integrated #193/#196 provide
  the fail-closed read-only descriptor/probe and exact Crazyflie 2.1 identity
  path; #238 derives requirements from the exact submitted AST with optional
  deck capabilities intent-dependent; #241 binds a successful preflight to that
  canonical AST; #243 re-reads the connected descriptor on every invocation;
  #244 binds the result to an adapter-provided connection epoch so a reconnect
  during or after preflight invalidates it; #246 provides the concrete host-side
  `ReadOnlyCapabilitySession` that opens one explicit Crazyradio link, creates/
  rotates that epoch around live connections, invalidates it on cflib disconnect
  and reconstructs descriptors from current connected evidence; and #249 binds
  the production physical submission path to that live session, preserving the
  exact current activity profile and semantic workspace AST across preflight and
  re-asserting them with the same connection epoch immediately before any later
  separately authorized effect. These slices preserve `executionAuthority:false`
  and expose no WebeeBlocks motor/arming command API
- real-device checkpoint #226 was authoritatively closed `NOT_NEEDED` after the
  live-preflight product decision superseded the fixed all-reference-decks gate.
  Its bounded partial observation still established exact Crazyflie 2.1
  identity, Flow Deck V2 and Multi-ranger presence plus successful self-test on
  the available device, while truthfully observing the Color LED Deck absent;
  this is historical capability evidence, not a reusable execution preflight
- the normal cflib close path still emits its safety-zero commander setpoint, so
  transport-level packet emission is not claimed read-only
- remaining boundary: the validated pre-effect assertion is integrated; a
  separately authorized physical effect consumer remains unproven. On stock
  brushed Crazyflie 2.1, auto-arming is enabled, so explicit teacher
  authorization must gate every flight-capable command/effect rather than merely
  a host arming request. The physical path must also establish an independent
  emergency-stop watchdog/liveness guard plus controlled normal land/disarm
  behavior before real student execution continuity can be claimed
- reopen simulation vocabulary only for a demonstrated pedagogical need or new
  contradictory evidence.

### X3 — redesign S3 evidence after the terrain-veto discriminator

- parent: #70
- established technical result: the isolated S3 `surfaceOffset` applicator and
  deterministic build oracle remain pinned to `crazyflie-firmware` 2026.08 and
  preserve the proven local-range Flow split plus pre-registered terrain and
  true-vertical controls
- established physical result: #180 refuted the original terrain candidate; the
  exact follow-up discriminator checkpoint #236 then PASSed its causal purpose.
  Terrain S3-A can trigger VZ, BARO or BOTH vetoes, whereas the valid S3-B/S3-C
  true-vertical controls remain below the ToF rejection gate, never enter
  SUSPECT and never falsely commit terrain
- causal consequence: the current VZ/barometer cues are not sufficiently
  independent/discriminating after a terrain discontinuity; the available
  S3-B/S3-C controls do not prove the late veto unnecessary because they do not
  exercise that decision path
- next proof: redesign the classifier evidence and/or temporal alignment so a
  terrain-induced estimator response cannot masquerade as independent true
  vertical-motion evidence; pre-register a bounded candidate and include at
  least one true-vertical control that reaches the revised late-decision path
  before relying on the result
- acceptance boundary: a later candidate must both permit coherent terrain
  commit/recovery and reject true vertical motion on the decision path it
  changes; controls that never enter that path cannot establish the latter
- safety boundary: do not modify product Runtime v2, tune ToF/barometer or S3
  thresholds/persistence against the outcome, add `rangeUp` fusion/full `z/f/r`,
  or perform motorized real flight as an agent
- consequence: no stronger world-altitude capability claim is justified until
  a separately proven mechanism replaces the refuted S3 boundary.

## Later gates kept intentionally coarse

### P — physical backend capability and safety

- parents: physical-backend product work and #70 evidence
- established prerequisite: #193/#196 plus #238/#241/#243/#244 provide the
  non-authority Crazyradio/deck evidence path, exact-airframe proof, exact-AST
  capability derivation/binding, fresh descriptor acquisition and reconnect
  invalidation; #246 supplies the concrete host-side live session that owns the
  reconnect-sensitive epoch and current descriptor reads; and #249 integrates
  the production physical submission bridge that binds and immediately re-asserts
  the current profile/semantic AST with that live epoch. The surface remains
  non-authority with `executionAuthority:false`; the cflib close path retains its
  safety-zero transport setpoint
- bounded real-device evidence from superseded checkpoint #226 confirms the
  available Crazyflie 2.1 + Flow Deck V2 + Multi-ranger observation, but it is
  not a reusable live execution preflight and does not prove an absent Color LED
  capability or any command path
- depends: separately authorized physical effect consumption gated by explicit
  teacher authorization before any flight-capable command/effect, plus an
  independent emergency-stop watchdog/liveness guard, controlled normal
  land/disarm behavior and proof of physical execution continuity. Do not assume
  a host arming packet is the teacher gate: stock brushed Crazyflie 2.1
  auto-arms when pre-flight checks pass
- proof direction: preserve backend-neutral AST continuity and use direct cflib
  `HighLevelCommander` as the primitive effect substrate rather than the
  `MotionCommander` / `PositionHlCommander` helpers: rotate body-relative
  horizontal intent into world-frame deltas from an accepted current yaw, use
  relative world-Z/yaw as appropriate, and bound command completion by observed
  supervisor/high-level trajectory state plus timeout/locked/crashed checks.
  Add only the minimum teacher-authorized physical execution authority after the
  live capability and safety gates are independently established. Keep immediate
  emergency stop and high-level commander stop exceptional because both can cut
  motors in flight; normal completion/voluntary abort needs a controlled
  high-level land then disarm path
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
