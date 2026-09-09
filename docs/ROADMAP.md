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
separately authorized effect. Integrated #256 additionally establishes the pure
non-authority physical HighLevelCommander semantic adapter for the already-proven
Runtime v2 horizontal/body-to-world geometry, relative world-Z and signed relative
yaw; it imports no cflib command surface and emits no physical effect. Integrated
#257 further establishes a non-authority fresh supervisor-state observer bound to
the reconnect-sensitive connection epoch: reads are serialized across that epoch,
exact-framed, preserve the raw bitfield including deck fault, and poison ambiguous
freshness/transport until reconnect. Integrated #260 now also establishes the
non-authority accepted-yaw observer for the future #256 horizontal transform: it
streams firmware `stateEstimate.yaw`, binds the stream to that same reconnect-
sensitive epoch, rejects cached/duplicate/stale/non-finite samples and converts a
strictly later post-call sample from degrees to radians exactly once. Integrated
#264 adds the non-authority controlled-landing completion observer, binding one
fresh pre-land high-level-flight baseline to one later same-epoch finished,
non-flying, high-level-inactive #257 result. Integrated #262 adds the independent
host-side emergency-watchdog liveness safety primitive: it consumes an external
powered-session authority, causally fences activation through #257, immediately
re-anchors the keepalive deadline, maintains liveness continuously and makes
ambiguity or lost lifecycle certainty terminal until separately proven reset.
The browser-facing capability surface remains non-authority with
`executionAuthority:false`; #262 is host safety infrastructure and exposes no
student/browser flight authority. The underlying cflib SyncCrazyflie close path
still emits its documented safety-zero commander setpoint, so this is not a claim
that the transport emits no command packet. Integrated #266 now supplies the concrete trusted powered-session/reset
implementation consumed by #262, and integrated #267 supplies the host-only
exact-run teacher-authorization binding. The substantive remaining product
boundary therefore starts after those validated semantics, observations and
safety/authority prerequisites: the separately authorized physical effect
consumer and proof of safe real execution continuity. The existing browser-held
capability/preflight bearer remains non-authority: the #267 teacher decision
belongs to a distinct trusted host-side control path that the student/browser
runtime cannot mint or invoke, and effect methods must not be added under that
read-only bearer merely for reuse. Stock brushed
Crazyflie 2.1 auto-arms when pre-flight checks pass and
can return to ReadyToFly after a normal landing/reset cycle, so post-landing
disarm is not a persistent safety gate and teacher authorization must not be
modeled as merely approving a host arming packet. Do not invent
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
  separately authorized effect. Integrated #256 then codifies the physical
  body-relative horizontal -> world-frame transform plus relative world-Z/yaw as
  a pure semantic adapter, without importing cflib or emitting any command.
  Integrated #257 adds the fresh fail-closed supervisor-state observer: one
  reconnect-sensitive epoch serializes all reads, exact response framing and raw
  state including deck fault are preserved, and timeout/disconnect/malformed or
  otherwise ambiguous freshness poisons that epoch until reconnect. Integrated
  #260 adds the matching non-authority live-yaw observer for #256: a continuous
  `stateEstimate.yaw` stream is epoch-bound, its first sample is only a timestamp
  baseline, and each accepted reading requires a strictly later post-call sample,
  with duplicate/stale/malformed/non-finite values rejected and degrees converted
  to radians exactly once. Integrated #264 adds one-shot controlled-landing
  completion evidence from fresh #257 observations, rejecting forged/replayed
  baselines, blocking faults, epoch loss and late completion. Integrated #262
  adds the host-only emergency-watchdog liveness primitive with exact Crazyflie/
  epoch binding, same-port activation fence, immediate post-fence keepalive,
  continuous host-gap enforcement and an abstract externally supplied
  powered-session authority that cannot be minted by reconnect or process
  reconstruction. The browser-facing slices preserve `executionAuthority:false`;
  #262 exposes no WebeeBlocks motor/arming or student/browser command API
- real-device checkpoint #226 was authoritatively closed `NOT_NEEDED` after the
  live-preflight product decision superseded the fixed all-reference-decks gate.
  Its bounded partial observation still established exact Crazyflie 2.1
  identity, Flow Deck V2 and Multi-ranger presence plus successful self-test on
  the available device, while truthfully observing the Color LED Deck absent;
  this is historical capability evidence, not a reusable execution preflight
- the normal cflib close path still emits its safety-zero commander setpoint, so
  transport-level packet emission is not claimed read-only
- remaining boundary: the validated pre-effect assertion, fresh supervisor/yaw
  observations, watchdog safety primitive, controlled-completion observer,
  concrete trusted powered-session/reset authority (#266), exact-run host-only
  teacher authorization (#267), and pure HighLevel trajectory timing policy
  (#268) are integrated; the separately authorized physical effect consumer and
  safe real-execution proof remain unproven. The future effect layer must
  compose the exact-bound preflight with #257/#260/#256/#268, consume #266 to
  establish the powered session, keep #262 live across that reusable session,
  require the exact #267 run binding before every flight-capable effect, and use
  #264 around controlled landing/completion. The
  #262/#266 powered-session identity remains distinct from the Crazyradio
  connection epoch: ambiguous activation/maintenance, a missed keepalive
  deadline, epoch loss or otherwise lost lifecycle certainty is terminal across
  ordinary reconnect. Reuse requires the #266 trusted STM+deck reset/
  postcondition establishment, then a new connection epoch and complete
  capability/preflight/safety re-observation before a fresh external #262
  authority can exist. On stock auto-arming firmware, post-landing disarm is not
  a persistent lockout; a later physical run still requires a new #267 teacher
  authorization
- reopen simulation vocabulary only for a demonstrated pedagogical need or new
  contradictory evidence.

### X3 — establish independent vertical-motion evidence before terrain redesign

- parent: #70
- established physical result: #180 refuted the original terrain candidate and
  #236 showed that the late S3 VZ/barometer vetoes are not independent terrain
  discriminators; the valid S3-B/S3-C controls stay below the stock ToF rejection
  gate and therefore do not exercise the late decision path
- causal consequence: the scalar S3 `surfaceOffset` direction is not a sound
  architecture to repair by threshold or veto tuning. Preserve the proven
  local-range Flow split, but first separate vehicle vertical displacement from
  surface-height change instead of assuming `delta z = 0`
- current proof question: determine whether an independent vehicle displacement
  estimate from IMU/barometer evidence that excludes suspect ToF can bound
  `delta z` tightly enough that `delta h = delta z_ind - delta c` distinguishes
  terrain, true vertical motion and a mixed event
- next proof: reanalyse the existing #180/#236/#251 archives before collecting
  new physical data. Verify provenance/hashes and available columns, use the raw
  barometer plus IMU/attitude when present, quantify uncertainty/latency, and
  compare the same frozen calculation across stationary, terrain, vertical and
  mixed controls with an independent metric reference where one exists
- falsification boundary: the current #70 review uses at most 5 cm displacement
  error and at most 1 s after transition end as bounded experimental criteria,
  not classifier thresholds or flight acceptance. A valid counterexample
  refutes that candidate; missing raw inputs/reference makes the result UNPROVEN
  rather than grounds for tuning around the evidence
- if the archived evidence is insufficient, prepare only one bounded props-off
  checkpoint that fills the exact missing signal/reference and exercises the
  revised decision path; do not repeat generic S3-A/B/C trials
- safety boundary: do not modify product Runtime v2, tune ToF/barometer or S3
  thresholds/persistence, delete the late veto to rescue S3, add `rangeUp` or a
  full `z/f/r` estimator by default, or perform motorized real flight as an agent
- consequence: no new terrain-classifier implementation or stronger world-altitude
  capability claim is justified until this independent-information proof
  converges; #70 remains Lab-only.

## Later gates kept intentionally coarse

### P — physical backend capability and safety

- parents: physical-backend product work and #70 evidence
- established prerequisite: #193/#196 plus #238/#241/#243/#244 provide the
  non-authority Crazyradio/deck evidence path, exact-airframe proof, exact-AST
  capability derivation/binding, fresh descriptor acquisition and reconnect
  invalidation; #246 supplies the concrete host-side live session that owns the
  reconnect-sensitive epoch and current descriptor reads; and #249 integrates
  the production physical submission bridge that binds and immediately re-asserts
  the current profile/semantic AST with that live epoch; #256 establishes the
  pure no-effect body/world, world-Z and relative-yaw semantic adapter intended
  for later direct HighLevelCommander consumption; #257 establishes a fresh
  fail-closed raw supervisor observer bound to that reconnect-sensitive epoch,
  including deck-fault handling and epoch-wide ambiguity poisoning; #260
  establishes the non-authority fresh `stateEstimate.yaw` observer bound to the
  same epoch for later #256 horizontal-transform input; #264 establishes
  controlled normal-completion evidence from one fresh high-level-flight baseline
  to one later fresh finished/non-flying #257 state; and #262 establishes the
  independent host-side watchdog activation/liveness primitive with its external
  powered-session authority contract. The browser-facing surface remains
  non-authority with `executionAuthority:false`; the cflib close path retains
  its safety-zero transport setpoint
- bounded real-device evidence from superseded checkpoint #226 confirms the
  available Crazyflie 2.1 + Flow Deck V2 + Multi-ranger observation, but it is
  not a reusable live execution preflight and does not prove an absent Color LED
  capability or any command path
- depends: separately authorized physical effect consumption and proof of
  physical execution continuity. Integrated #266 now satisfies #262's concrete
  trusted powered-session/reset authority boundary, and integrated #267 now
  supplies the exact-run host-only teacher-authorization binding that every
  flight-capable effect must re-check. The existing browser-held capability/
  preflight bearer remains non-authority; the #267 teacher path is distinct and
  unavailable to the student/browser runtime, and the read-only capability
  bridge must not gain effect methods merely to reuse that bearer. Integrated
  #268 additionally supplies the pure horizontal/yaw HighLevel timing policy
  needed by the later serialized effect consumer. #262, #264, #266, #267 and
  #268 are safety/authority/semantic prerequisites; none alone establishes the
  physical effect consumer or real-flight proof. Stock
  auto-arming can return the vehicle to ReadyToFly after the landing/reset cycle,
  so a host disarm request is not a durable post-mission lockout. The pinned
  watchdog has no disable/reset command after first activation, so its trusted
  keepalive lifecycle must span the reusable powered physical session; simply
  stopping keepalives after a normal land would eventually enter the latching
  emergency-stop/locked state and require reboot. Its one-way keepalive command
  also has no application-level reply: the current bounded activation-proof
  direction is to enqueue the keepalive and then require a successful #257 fresh
  GET_STATE read on the same unchanged connection epoch/supervisor port, relying
  on the documented same-port ordering as a causal fence. Powered-session
  watchdog certainty must survive guard replacement and Crazyradio reconnect:
  reconnect/new epoch invalidates connection evidence but does not reset firmware
  watchdog state. After ambiguous activation/maintenance, a missed keepalive
  deadline, locked state or other lifecycle uncertainty, ordinary authority stays
  fail-closed until an explicit STM+deck power-cycle/reboot is separately proven,
  followed by reconnect/new epoch and complete re-preflight. That power-cycle is
  a motor-cut recovery boundary, not a normal abort action, and must never be
  triggered opportunistically while physical flight may still be active. The
  integrated #266 now supplies the concrete trusted powered-session/reset
  authority for this recovery boundary: explicit STM+deck reset establishment
  plus a new connection epoch and fresh capability/preflight/safety
  postconditions are required before #262 can receive fresh lifecycle authority.
  Do not assume a host arming packet is the teacher gate: stock brushed Crazyflie
  2.1 auto-arms when pre-flight checks pass
- proof direction: preserve backend-neutral AST continuity and consume the
  integrated #256 pure semantic adapter plus #268 timing from a later direct
  `HighLevelCommander` effect substrate rather than the `MotionCommander` /
  `PositionHlCommander` helpers. The accepted-yaw observation itself is now
  established by #260; a later authority layer must consume one fresh same-epoch
  #260 sample immediately before the #256 horizontal transform and preserve the
  exact preflight/session binding across that observation/transform. For the
  command transport, use the stock SETPOINT_HL firmware application reply as the
  acceptance result instead of treating cflib's immediate helper return as an
  acknowledgement; timeout/malformed/disconnect is an ambiguous effect outcome
  and must not trigger automatic command resend. After positive acknowledgement,
  consume the integrated #257 fresh supervisor observer to bound command
  completion by high-level trajectory state plus timeout/locked/crashed/deck-fault
  checks. That observer must be the exclusive authoritative issuer of supervisor
  GET_STATE requests on the connection epoch; do not invoke cflib `Supervisor`
  getters in parallel or as a second safety oracle because they bypass #257's
  epoch-wide serialization/ambiguity guard. Add only the minimum teacher-authorized physical
  execution authority after the live capability and safety gates are independently
  established, keeping that authority outside the existing browser capability
  credential/domain. Keep immediate emergency stop and high-level commander stop
  exceptional because both can cut motors in flight; normal completion/voluntary
  abort must issue a controlled high-level land and await integrated #264 while
  integrated #262 remains live through the reusable powered session. A later
  flight-capable effect still requires fresh teacher authorization even if stock
  auto-arming returns the vehicle to ReadyToFly
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
