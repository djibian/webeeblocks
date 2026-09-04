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
2. **#80 — one-click unified classroom interface**
3. **#79 — fully French student interface**
4. **#66 — progressive pedagogical activity model**

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

These remain durable product work and do not invalidate W2 stability:

1. a program without `atterrir` currently produces a generic technical error
   instead of a student-correctable diagnostic;
2. there is no user command to voluntarily interrupt an active flight;
3. a purely visual movement of the Blockly program can trigger a false
   `Programme modifié : Réinitialisez la simulation avant de relancer` warning
   although program logic did not change.

Controllers should turn these findings into the smallest useful product slices
according to current #81/#80 priority and existing GitHub work.

The discriminating weak-PC benchmark recorded in #80 has also settled the
interface architecture: **option A, standard Webots GUI + automatically opened
Robot Window, is the retained classroom path; option B must not be prototyped
without new contradictory evidence**. Chrome was observed fluid on the reference
low-end Windows PC, the Robot Window opened without window hunting, and offline
relaunch worked after preparation/cache.

Chrome remains the reference browser for the current product-development phase.
Known Edge and Firefox gaps do not block Chrome-based product slices; Firefox
final same-file semantics remain tracked by #87.

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

### F1 — inventory remaining visible non-French student surfaces

- parent: #79
- depends: current Runtime v2 UI
- action: bounded audit of remaining student-visible strings/surfaces, separated
  from internal identifiers and machine diagnostics
- proof: precise inventory with no AST/backend translation
- boundary: implementation becomes normal small product PRs under current
  `AGENTS.md`.

### B1 — formalize the declarative activity model and compact progression

- parent: #66
- depends: PRODUCT_VISION.md
- action: bounded design/research of the smallest versionable activity/profile
  schema and representative 8–12 activity progression
- proof: a coherent model preserving generic blocks and
  `activity/profile -> Blockly -> AST -> preflight -> interpreter -> backend`
  without student progress state or a graphical activity studio
- note: mass activity production may rely on the settled option A presentation
  direction but still follows current product priority.

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
- depends: coherent progression + proven physical backend + any #70 capability
  required by the chosen final mission
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
