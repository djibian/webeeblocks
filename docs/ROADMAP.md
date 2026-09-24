# WebeeBlocks — product roadmap

This file is a compact, versioned projection of product intent, dependencies and
exit criteria. It is not a workflow-state database.

Authority order:

`PRODUCT_VISION.md -> product issues -> ROADMAP.md -> Controller execution`

GitHub commits, PRs, checks, reviews, issues and evidence describe live execution
state. Do not duplicate agent/session state, WIP counters, ownership or queues
here.

## Product priority

1. **#487 — executable pedagogical scenarios and cumulative learning progression**
2. **#157 — broader useful reference-capability coverage**

#66 established the declarative activity/profile architecture and compact-
progression structure, but new product evidence in #487 supersedes interpreting
that result as proof that the current activity scenarios are pedagogically
complete. #81 (Windows classroom deployment), #80 (one-click unified classroom
interface) and #79 (fully French student interface) remain validated baselines,
not active priority nodes.

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
non-authority accepted-yaw observer for the #256 horizontal transform: it streams
firmware `stateEstimate.yaw`, binds the stream to that same reconnect-sensitive
epoch, rejects cached/duplicate/stale/non-finite samples and converts a strictly
later post-call sample from degrees to radians exactly once. Integrated #264 adds
the non-authority controlled-landing completion observer, binding one fresh
pre-land high-level-flight baseline to one later same-epoch finished, non-flying,
high-level-inactive #257 result. Integrated #262 adds the independent host-side
emergency-watchdog liveness safety primitive: it consumes an external powered-
session authority, causally fences activation through #257, immediately
re-anchors the keepalive deadline, maintains liveness continuously and makes
ambiguity or lost lifecycle certainty terminal until separately proven reset.
The browser-facing capability surface remains non-authority with
`executionAuthority:false`; #262 is host safety infrastructure and exposes no
student/browser flight authority. The underlying cflib SyncCrazyflie close path
still emits its documented safety-zero commander setpoint, so this is not a claim
that the transport emits no command packet. Integrated #266 supplies the concrete
trusted powered-session/reset implementation consumed by #262, and integrated
#267 supplies the host-only exact-run teacher-authorization binding. Integrated
#283/#280 establishes the trusted physical-host composition root: the one live
Crazyflie/session and #278 bridge/responder stay inside that host while the
ordinary caller/UI sends only bounded non-authority run-context requests.
Integrated #276 supplies the ordinary co-located one-shot SETPOINT_HL effect
consumer for exact teacher-bound horizontal move/yaw effects, #295/#305/#308
extend that same host-owned sequence through exact terminal controlled landing
and fresh non-flying completion, #316 admits exact bounded teacher-bound waits as
host-monotonic no-effect sequence steps, #322/#320 consumes exact `set_speed` as
per-run no-effect state for later horizontal timing, #333 consumes exact
teacher-bound vertical up/down effects with eager cumulative 0.2–1.5 m nominal-
altitude validation and terminal landing descent derived from the completed final
nominal altitude, and #341 consumes exact teacher-bound bottom Color LED effects
through one-shot PARAM writes with same-epoch freshness and exact readback.
Integrated #348/#351/#353/#355/#356/#362 now extend that same deterministic
trusted-host envelope through student physical Multi-ranger consumption without
creating a second Runtime semantics: exact `range(front/back/left/right/up)`
demand comes only from the teacher-bound shared `interpreter.js`, each accepted
sample is fresh and same-epoch under the shared reset/effect observation exclusion,
`<8000 mm` is converted to metres exactly once while unavailable values fail
closed, and the finite result remains non-authority data. Variables, expressions,
short-circuiting, branches and repeats remain interpreter-owned; every selected
later effect still re-establishes its independent current-program, teacher,
powered-session, watchdog, SafeLink, acknowledgement and completion chain.
The supported deterministic physical envelope therefore covers both the exact
flat sequence and shared-interpreter dynamic control flow from one causal takeoff
through supported movement/vertical/bottom-light effects and bounded no-effect
wait/set-speed state to terminal controlled landing from host-owned runtime
altitude. This is deterministic fake/injected-hardware integration evidence, not
real-flight or real-device range/light qualification. The substantive remaining
#157 physical boundary is representative real-device qualification of that
integrated envelope, not additional generic student vocabulary.
The existing browser-held capability/preflight bearer remains non-authority: the
#267 teacher decision belongs to a distinct trusted host-side control path that
the student/browser runtime cannot mint or invoke, and effect methods must not be
added under that read-only bearer merely for reuse. Stock brushed Crazyflie 2.1
auto-arms when pre-flight checks pass and can return to ReadyToFly after a normal
landing/reset cycle, so post-landing disarm is not a persistent safety gate and
teacher authorization must not be modeled as merely approving a host arming
packet. Do not invent additional simulation vocabulary merely to keep #157
active. A new simulation slice needs a concrete pedagogical need or contradictory
evidence.

Research / later work:

- **#70 — world altitude over surface discontinuities**
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
implicitly prove Edge parity or every future artifact. Issue #81 is closed as
completed on that explicit supported boundary; later materially changed releases
may require bounded revalidation without reopening unsupported-browser claims.

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
Direct `.wbb` Firefox parity is now established on Linux and on the supported
Windows classroom path by the owner-authoritative #481 PASS; #87 is closed.

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

The later #70 architecture review supersedes the earlier plan to repair this
scalar S3 decision by changing its late evidence or timing. Preserve the proven
local-range Flow split and existing safety boundaries, but first test whether
vehicle vertical displacement can be estimated independently from IMU/barometer
evidence that excludes suspect ToF, so surface-height change can be separated
from true or mixed vertical motion. Reanalyse the existing #180/#236/#251
archives before collecting new physical data; missing indispensable raw inputs
or an independent metric reference makes that question UNPROVEN rather than a
reason to tune S3 around the observations. No `rangeUp`, full z/f/r extension,
threshold/persistence sweep, Runtime/controller change or motorized test is
justified by the current evidence.

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

### B1 — declarative activity model established; pedagogical acceptance reopened

- parent: #66
- evidence: integrated #181 on `main@8eab31ca448a966063e53f039f340238ecfec833`
  plus the earlier field-option, variables/memory and open-strategy slices
- established structural result: eight ordered substantial `progression-*`
  profiles/starter files, one shared declarative activity/profile model, generic
  blocks and `activity/profile -> Blockly -> AST -> preflight -> interpreter ->
  backend`; starter filenames map one-to-one to activity IDs and cumulative
  constraints are contract-tested without student progress state or a graphical
  activity studio
- classroom access: integrated #435 closes #434 by shipping the canonical ordered
  starter `.wbb` files in the Windows classroom release and exposing a distinct
  `Démarrer une activité` template path through the existing declarative
  project/profile loader. Starting a packaged activity clears the current save
  target so student work requires an explicit Save As; no second activity
  catalogue, unlock/progress state or new Runtime semantics is introduced
- superseding evidence: #487 establishes that structural progression and named
  objectives do **not** prove pedagogically complete activity scenarios. The
  current activities must be re-evaluated against explicit student missions,
  worlds that make the new concept genuinely useful/necessary, cumulative reuse
  of prior concepts and executable mission outcomes
- finality: the teacher-authorized final real-flight activity remains separately
  gated under #72 by physical backend/capability proof and any #70 result required
  by the chosen mission; B1 establishment does not claim real-flight readiness.

### B2 — executable pedagogical scenarios and cumulative progression

- parent: #487
- target: approximately 8–12 substantial problem situations, where quality and
  cumulative learning take precedence over activity count
- activity contract: every retained activity has a complete student-facing
  scenario/mission distinct from its internal pedagogical objective; its world,
  geometry, events, sensor availability or other constraints create the need for
  the target concept; prior concepts are naturally reused; success/failure is
  evaluated from observable mission state rather than expected Blockly/AST shape
- student feedback: provide simple mission achieved / not achieved / interrupted
  feedback without automatic diagnosis, hints, strategy suggestions or persistent
  attempt/progress history
- variable capability: standard Blockly `variables_set` / `variables_get` /
  `math_change` already lower through the backend-neutral variable assignment and
  arithmetic path and are covered by Runtime/project round-trip tests. Do not add
  task-specific increment/decrement primitives merely to satisfy #487
- acceptance: re-evaluate the existing representative activities one by one;
  retain those meeting the contract, redesign weak scenarios/worlds and replace
  those that cannot be made pedagogically coherent. For each activity be able to
  state `new concept -> world property that makes it necessary -> student mission
  -> prior concepts reused -> executable success criteria`
- non-goals: no accounts, automatic unlocks, mastery database, grading system,
  leaderboard, intelligent tutor, solution-shape oracle or world proliferation
  for its own sake.

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
  and reconstructs descriptors from current connected evidence; #249 binds the
  production physical submission path to that live session, preserving the exact
  current activity profile and semantic workspace AST across preflight; and
  integrated #278 adds a fresh host-initiated one-shot profile/AST/epoch
  re-assertion channel from the production browser path. Integrated #283/#280
  establishes the production composition root around that channel: the trusted
  physical-host process owns the exact live session plus #278 bridge/responder,
  browser responder bootstrap remains a distinct trusted channel, and the
  ordinary caller/UI remains outside on bounded non-authority run-context IPC.
  Integrated #276 is co-located inside that trusted host TCB and performs fresh
  #278/#249 current-program assertion internally before each supported ordinary
  effect; no public/importable mint, binder or client turns caller-selected
  bridge, session, socket or token state into effect provenance. Integrated #256
  codifies the physical body-relative horizontal -> world-frame transform plus
  relative world-Z/yaw as a pure semantic adapter, without importing cflib or
  emitting any command.
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
  continuous host-gap enforcement and an abstract externally supplied powered-
  session authority that cannot be minted by reconnect or process reconstruction.
  The browser-facing slices preserve `executionAuthority:false`; #262 exposes no
  WebeeBlocks motor/arming or student/browser command API
- real-device checkpoint #226 was authoritatively closed `NOT_NEEDED` after the
  live-preflight product decision superseded the fixed all-reference-decks gate.
  Its bounded partial observation still established exact Crazyflie 2.1
  identity, Flow Deck V2 and Multi-ranger presence plus successful self-test on
  the available device, while truthfully observing the Color LED Deck absent;
  this is historical capability evidence, not a reusable execution preflight
- the normal cflib close path still emits its safety-zero commander setpoint, so
  transport-level packet emission is not claimed read-only
- established deterministic physical envelope: #266/#267/#268/#271/#272/#273/
  #278/#279/#283 plus #257/#260/#262/#264 are integrated safety, authority,
  observation and effect-lifecycle prerequisites. #295 binds the exact supported
  physical program sequence. #276 consumes the exact next teacher-bound
  horizontal move or yaw turn through one plain no-retry SETPOINT_HL effect after
  causal takeoff; #305/#308 consume the exact terminal land through command 10
  only after all prior exact motions complete, reconstruct current-program
  provenance after blocking pre-land reads and require fresh #264 same-epoch
  finished/non-flying/high-level-inactive completion before the shared execution
  domain becomes inactive. #316 adds exact bounded host-monotonic waits as no-
  effect sequence steps; #322/#320 adds exact per-run no-effect `set_speed` state
  for subsequent horizontal timing; #333 adds exact relative-world-Z vertical
  effects with complete nominal-altitude path validation before flight and final
  landing descent derived from the completed nominal altitude; and #341 adds the
  exact next teacher-bound bottom Color LED effect through a one-shot PARAM write,
  a unique absent-id receive freshness fence, exact write echo and same-epoch
  exact-value readback before restoring `FLYING`. Unknown acknowledgement/effect/
  completion outcome remains fail-closed and cannot authorize retry or reset.
  Integrated #348/#351/#353/#355/#356/#362 additionally establish the dynamic
  Multi-ranger path: exact teacher-bound shared-interpreter demand selects only
  `front/back/left/right/up`, obtains one fresh same-epoch observation under the
  shared exclusion as non-authority data, keeps variables/expressions/control
  flow inside the existing Runtime interpreter, validates all reachable physical
  paths before takeoff, and routes every selected later effect through the same
  independent authority/acknowledgement/completion consumers. Post-takeoff
  interpreter/observer/protocol uncertainty enters the existing terminal
  powered-session/watchdog recovery path rather than permitting continuation
- checkpoint #433 closed owner-authoritative `FAIL` before `PREPARE`: the exact
  qualification package verified, but its world fell back from pinned R2025a
  PROTO URLs to system project paths absent from the supported Ubuntu package.
  No teacher approval, motor action or deck/flight qualification occurred, so the
  trusted physical semantics are not refuted by this result
- qualification-world repair: integrated #441 closes the deterministic asset
  dependency exposed by #433. The packaged qualification world/PROTO/assets and
  matching Robot Window perspective are self-contained and verified without
  fallback to absent system R2025a project paths. This repairs machine packaging
  only and does not convert #433 into physical qualification evidence
- current checkpoint boundary: representative real-device qualification remains
  `UNPROVEN` pending a fresh exact-SHA `physical-capabilities-representative`
  checkpoint. The generic one-open-human-test rule currently prevents a second
  request while #519 (`windows-low-end`, target
  `c932c410e8793e2ff9687c1dc7c16c386fd1c98f`) remains unresolved. After #519 is
  durably resolved, reconstruct current main, qualification support/cache evidence
  and the global `TEST_REQUIRED` set before deciding whether a fresh request is
  eligible; never reuse an earlier failed/stale qualification artifact
- remaining boundary: representative real-device qualification beyond the
  currently integrated deterministic flat + dynamic envelope, including
  Multi-ranger observation and bottom Color LED behavior when required by the
  selected activity. No additional generic student capability is currently
  justified. The #262/#266 powered-session identity remains distinct from the
  Crazyradio connection epoch: ambiguous activation/maintenance, a missed
  keepalive deadline, epoch loss or otherwise lost lifecycle certainty is
  terminal across ordinary reconnect. Reuse requires #266 trusted STM+deck
  reset/postcondition establishment, then a new connection epoch and complete
  capability/preflight/safety re-observation before fresh #262 authority can
  exist. On stock auto-arming firmware, post-landing disarm is not a persistent
  lockout; every later physical run still requires a new #267 teacher
  authorization. The deterministic envelope is not a real-flight qualification
  and authorizes no motorized checkpoint
- reopen simulation vocabulary only for a demonstrated pedagogical need or new
  contradictory evidence.

### X3 — simplified independent characterization before terrain redesign

- parent: #70
- owner direction: `X3 VIABLE WITH SIMPLIFICATION` supersedes the earlier plan
  to prove tight deterministic bounds for every sensor/timing sub-link before
  collecting new physical information. The frozen predictor remains a conditional
  confirmation tool; characterization cannot retroactively validate its stronger
  bound flags
- established preparation: the reviewed pre-registration/support definition fixes
  the unchanged #251 props-off firmware/configuration, calibration-versus-
  confirmation split, stationary/terrain/true-vertical/mixed cases, all-trial
  retention and the 5 cm / 1 s falsification quantities. Integrated #426 adds the
  concrete measured-guide + independent-clock witness, explicit uncertainty and
  affine-clock fail-closed mapping into the exact characterization bundle
- trusted checkpoint path: integrated #428 enables checkpoint-only
  `x3-independent-props-off` backed by `WebeeBlocks-X3-Characterization`. Exact
  requested-SHA checkout, pinned cflib/#251 support, locked offline runtime,
  bundle verification, Runtime/Webots evidence, digest/provenance and the generic
  one-open-human-test rule remain mandatory; packaging itself remains request-
  neutral and grants no execution or motorized authority
- next indispensable evidence: one complete props-off human characterization
  bundle against the independent metric/time reference, retaining all validly
  started raw trials across stationary, terrain, true-vertical and mixed cases.
  Calibration-only processing/envelopes are then frozen before untouched
  confirmation and the separate scientific decision. An uncertainty interval
  crossing a predeclared target is `UNPROVEN`, never PASS
- checkpoint gating: #433 is closed `FAIL` before `PREPARE` and no longer blocks
  another checkpoint merely by occupying the one-open-human-test slot. This does
  not create a queue or make X3 automatically next: any X3 request still requires
  an exact trusted checkpoint decision from reconstructed current dependencies,
  and the generic one-open-human-test rule remains mandatory
- safety boundary: empirical characterization is tested-domain evidence, not a
  universal deterministic guarantee. Do not revive dominated interrupt/timing
  provenance investigations merely because they remain `UNPROVEN`, retune
  ToF/barometer/S3 thresholds, modify product Runtime/controller behavior, add
  `rangeUp`/full z-f-r by default, or infer/authorize motorized flight
- consequence: #70 remains Lab-only until the characterization/confirmation
  evidence supports an explicit scientific decision.

## Later gates kept intentionally coarse

### P — physical backend capability and safety

- parents: physical-backend product work and #70 evidence
- established prerequisite and deterministic subset: #193/#196 plus
  #238/#241/#243/#244/#246/#249 establish exact-airframe, live capability,
  exact-AST binding and reconnect-sensitive current-program provenance; #256,
  #257 and #260 establish the pure movement transform and fresh supervisor/yaw
  observations; #262/#264/#266/#267/#268/#271/#272/#273/#278/#279/#283 provide
  the trusted powered-session, teacher, watchdog, SafeLink, acknowledgement,
  reset/effect-exclusion, current-program and completion domains. #295 binds the
  exact supported program sequence; #276 supplies one-shot horizontal move/yaw
  effects after causal takeoff; #316 adds bounded no-effect waits; #322/#320 adds
  exact per-run no-effect horizontal-speed state; #333 adds bounded relative-
  world-Z vertical effects with trusted nominal-altitude progression; #341 adds
  exact bottom Color LED effects through one-shot PARAM write plus same-epoch
  freshness/readback; #305/#308 compose exact terminal controlled landing from
  the final trusted altitude plus fresh non-flying completion; and
  #348/#351/#353/#355/#356/#362 compose exact teacher-bound shared-interpreter
  `range(front/back/left/right/up)` consumption with fresh same-epoch observation,
  conservative all-path pre-takeoff validation, independent downstream effect
  authority and terminal fail-closed recovery. The browser-facing surface remains
  non-authority with `executionAuthority:false`, and the cflib close path retains
  its safety-zero transport setpoint. This established subset is deterministic
  fake/injected-hardware integration evidence, not real-flight qualification
- bounded real-device evidence from superseded checkpoint #226 confirms the
  available Crazyflie 2.1 + Flow Deck V2 + Multi-ranger observation, but it is
  not a reusable live execution preflight and does not prove an absent Color LED
  capability or any command path
- depends: integrated #441 already closes the #433 qualification-world asset
  defect. The remaining gate is a fresh exact-artifact representative real-device
  qualification of the integrated physical envelope; opening that checkpoint is
  subject to the generic one-open-human-test rule, currently occupied by #519.
  The trusted host already owns the live session, #278 responder, exact #267
  teacher binding, #262/#266 powered-session/watchdog lifecycle, #276/#308/#341
  effect substrate and #362 dynamic Multi-ranger composition; new physical
  capability slices must consume those boundaries rather than expose caller-held
  provenance or add effect methods to the read-only browser capability bearer.
  Multi-ranger and bottom Color LED now have deterministic trusted-host
  integration but remain real-device unqualified. Stock auto-arming can return
  the vehicle to ReadyToFly after the landing/reset cycle, so a host disarm
  request is not a durable post-mission lockout. The pinned watchdog has no
  disable/reset command after first activation, so its trusted keepalive lifecycle
  spans the reusable powered physical session; simply stopping keepalives after a
  normal land would eventually enter the latching emergency-stop/locked state and
  require reboot. Powered-session watchdog certainty survives guard replacement
  and Crazyradio reconnect: reconnect/new epoch invalidates connection evidence
  but does not reset firmware watchdog state. After ambiguous activation/
  maintenance, a missed keepalive deadline, locked state or other lifecycle
  uncertainty, ordinary authority stays fail-closed until explicit STM+deck reset
  is separately proven, followed by a new connection epoch and complete
  re-preflight. That reset is a motor-cut recovery boundary, not a normal abort
  action, and must never be triggered opportunistically while physical flight may
  still be active
- proof direction: preserve backend-neutral AST continuity and qualify the
  integrated trusted-host envelope on representative real hardware before the
  final #72 activity relies on it. Reuse #256/#268 semantics/timing and one fresh
  same-epoch #260 yaw sample where applicable; use #257 as the exclusive
  authoritative supervisor GET_STATE issuer, #271 for application
  acknowledgement and #279 for accepted-effect completion. Timeout/malformed/
  disconnect or otherwise unknown effect outcome remains ambiguous and must not
  trigger automatic command resend. Keep immediate emergency stop and high-level
  commander stop exceptional because both can cut motors in flight; normal
  completion remains the integrated controlled high-level land through #308 while
  #262 stays live across the reusable powered session. Every later flight-capable
  run still requires fresh #267 teacher authorization even if stock auto-arming
  returns ReadyToFly. A representative motorized qualification is a later
  explicit checkpoint, not an implication of deterministic host composition
- expand only when this becomes near-term work.

### FF — Firefox same-file project semantics established

- parent: #87 (closed)
- integrated product result: the native Qt/WWI broker preserves direct `.wbb`
  Open / Save As / same-file Save, neutral cancellation, fail-closed invalid or
  incompatible Open and no numbered-download fallback while Chromium keeps its
  File System Access path
- Linux evidence: canonical real Webots R2025a + Firefox acceptance established
  the native dialog/file contract without restarting the historical C8–C26 Qt
  research
- Windows evidence: after the startup and native-dialog foreground repair chain,
  owner-authoritative checkpoint #481 recorded `PASS` on exact integrated target
  `2a3a4629cd1e1d0f254bf63a24c5184a496d67eb`. On the reference Windows 11 +
  Webots R2025a + Firefox path, WebeeBlocks reached `PRÊT`; native Save As and Open
  appeared spontaneously in the foreground; cancellations stayed neutral; Save
  rewrote the exact same `.wbb` without a new dialog or numbered duplicate; and
  reopening restored the saved project
- boundary: #87 is complete. The separate Chrome/offline mapped-profile defect is
  tracked by #476 and must not be folded back into Firefox broker semantics.

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
