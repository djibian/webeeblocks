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
- archived-input result: #292 made the retained #180/#236/#251 text accessible;
  the [input audit](../experiments/crazyflie-ukf-surface-range/evidence/analysis-2026-09-11/README.md)
  verifies all 94 retained files. No CSV contains continuous raw barometer or
  accelerometer/gyroscope samples; no independent metric vehicle-Z trajectory
  or measured mixed case is retained. Those archives therefore cannot establish
  the independent-displacement proof
- integrated support result: current `main` now contains the independent raw
  input capture, frozen pressure probe, conditional metric-reference path,
  frozen vertical predictor, durable evidence publication/provenance and
  checkpoint-support tooling. It also retains the diagnostic
  `stabilizer.intToOut`, exact BMP3 chip identity and the logging-only X3
  pre-LPF observer with coherent complete-group snapshots plus MCU read windows.
  Missing acquisition/calculation tooling is no longer the blocker
- timing/provenance boundary: the log-worker timestamp is not sensor producer
  time, and the X3 observer's `readBeg/readEnd` values bound CPU register reads,
  not sensor-internal production/filter time. #342 further establishes that the
  electrical source of `sensorData.interruptTimestamp` is UNPROVEN: the pinned
  firmware configures gyro DRDY on BMI088 INT3 while the published Crazyflie 2.1
  Rev.B schematic routes STM32 PC14 / `INT_GYR` to BMI088 INT2 and leaves INT3
  unconnected. Do not promote either timestamp into producer time
- remaining proof: justify deterministic provenance for every frozen-predictor
  uncertainty bound, especially specific-force/tilt/initial-velocity error,
  intersample acceleration, barometer displacement/filter uncertainty,
  `sensor_time_error_s` and delivery latency. Nominal ODR and manufacturer
  typical/RMS specifications are not deterministic bounds. The exact metric
  reference, synchronization and raw-publication procedure must also be frozen
  before any physical result can become authoritative
- next checkpoint boundary: request at most one bounded props-off information
  checkpoint only after the exact still-missing machine-unavailable information,
  instrumented artifact/profile and deterministic offline method are identified.
  That checkpoint should fill only those gaps and compare the same frozen
  calculation across stationary, terrain, true-vertical and mixed cases; do not
  repeat generic S3-A/B/C trials
- falsification boundary: the current #70 review uses at most 5 cm displacement
  error and at most 1 s after transition end as bounded experimental criteria,
  not classifier thresholds or flight acceptance. A valid counterexample
  refutes that candidate; missing or unjustified bounds/reference makes the
  result UNPROVEN rather than grounds for tuning around the evidence
- safety boundary: do not modify product Runtime v2, tune ToF/barometer or S3
  thresholds/persistence, delete the late veto to rescue S3, add `rangeUp` or a
  full `z/f/r` estimator by default, or perform motorized real flight as an agent
- consequence: no new terrain-classifier implementation or stronger world-altitude
  capability claim is justified until this independent-information proof
  converges; #70 remains Lab-only.

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
- depends: representative real-device qualification of the integrated physical
  envelope. The trusted host already owns the live session, #278 responder,
  exact #267 teacher binding, #262/#266 powered-session/watchdog lifecycle,
  #276/#308/#341 effect substrate and #362 dynamic Multi-ranger composition; new
  physical capability slices must consume those boundaries rather than expose
  caller-held provenance or add effect methods to the read-only browser
  capability bearer. Multi-ranger and bottom Color LED now have deterministic
  trusted-host integration but remain real-device unqualified. Stock auto-arming
  can return the vehicle to ReadyToFly after the landing/reset cycle, so a host
  disarm request is not a durable post-mission lockout. The pinned watchdog has
  no disable/reset command after first activation, so its trusted keepalive
  lifecycle spans the reusable powered physical session; simply stopping
  keepalives after a normal land would eventually enter the latching emergency-
  stop/locked state and require reboot. Powered-session watchdog certainty
  survives guard replacement and Crazyradio reconnect: reconnect/new epoch
  invalidates connection evidence but does not reset firmware watchdog state.
  After ambiguous activation/maintenance, a missed keepalive deadline, locked
  state or other lifecycle uncertainty, ordinary authority stays fail-closed
  until explicit STM+deck reset is separately proven, followed by a new connection
  epoch and complete re-preflight. That reset is a motor-cut recovery boundary,
  not a normal abort action, and must never be triggered opportunistically while
  physical flight may still be active
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

### FF — Firefox same-file project semantics

- parent: #87
- retained architecture: a native Qt file broker through the existing local
  Webots/WWI path, as selected by the bounded post-C26 decision on #87
- established causal result: C26 isolated executable COPY data interposition
  relative to GOT binding in the pinned minimal Qt closure; do not reopen C8–C26
- real-provider result: the single #301 qualification compiled the actual
  provider as PIC, verified no Qt COPY relocation, and observed official Webots
  launch, QApplication initialization, a displayed QFileDialog, real cancellation
  and provider return. The [retained result and raw evidence](https://github.com/djibian/webeeblocks/issues/87#issuecomment-5634037411)
  do not establish completion of the controller loop: its aggregate eight-step
  marker and controller exit status are absent, so continuation remains UNPROVEN
- continuity prerequisite established: the subsequent bounded #317 measurement
  repair on exact candidate `e8aecd14e7988a6772d780062f8cf83060657dff`
  received an [owner PASS](https://github.com/djibian/webeeblocks/issues/87#issuecomment-5643382930).
  Its controller-owned journal, observed before shutdown while Webots remained
  alive, proves eight successful steps, 0.256 s of progression, a local broker
  capabilities response and provider destruction after real dialog cancellation.
  The [complete retained evidence](https://github.com/djibian/webeeblocks/tree/44abcebfe0a399a488a77c4ddb5d418ce0920c2a/experiments/firefox-qt-provider/evidence/2026-09-12)
  preserves the original archive and all 30 raw files. #317 is closed without
  merge; this establishes dialog/controller coexistence, not a browser/WWI
  file-operation round trip. The older #301 result remains UNPROVEN for its own
  candidate
- next product boundary: implement the native broker and existing project-manager
  transport through local WWI, with browser-held opaque session references,
  validation before adopting an opened target, confirmed writes before adopting
  Save As, same-file Save and neutral cancellation/errors. The continuity
  prerequisite no longer blocks this implementation. Do not integrate the
  research harness or restart a causal discriminator chain
- product boundary: the native broker must preserve direct same-file Open,
  Save As and Save semantics; full Firefox parity and Windows qualification
  remain unproven. The supported Chromium path remains independent of #87
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