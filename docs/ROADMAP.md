# WebeeBlocks — execution roadmap

This file is the rolling operational projection of the product work. It is not
a second source of product truth and it is not a status database.

Authority order:

`PRODUCT_VISION.md -> product issues -> ROADMAP.md -> Controller execution`

GitHub PR/check/review facts describe the live state. Product issues define the
outcomes and acceptance boundaries. This roadmap only decomposes enough of the
near-term path to let the Controller choose useful work and expose real
dependencies.

## Scheduling principles

1. Protect the current integration critical path.
2. Use unavoidable CI or human-test waits for one independent reserve atom.
3. Keep one active integration PR plus at most one preparatory context.
4. Never invent work merely to keep a Controller session active.
5. Reconcile the affected local subgraph when new evidence changes a dependency.
6. Expand distant work only when it becomes relevant to scheduling.

## Product priority

1. **#81 — Windows classroom deployment**
2. **#80 — one-click unified classroom interface**
3. **#79 — fully French student interface**
4. **#66 — progressive pedagogical activity model**

Reserve / research when higher-priority work is externally waiting:

- **#70 — world altitude over surface discontinuities**
- **#87 — Firefox direct `.wbb` parity**, deferred behind more valuable reserve
  work unless new evidence changes that order.

Convergence later:

- **#72 — teacher-authorized final real-flight activity**, gated by the
  pedagogical progression and proven physical backend/capabilities.

## Current baseline

Recent #81 work has established the real low-end Windows classroom Chrome path:
one-action launch, Robot Window `PRÊT`, offline operation, execution/debug,
project files and usable performance. PR #128 addressed execution-state/UI
coherence and PR #129 addressed student-facing invalid-program handling. The
remaining #81 acceptance is therefore primarily real human revalidation and the
formal stability gate, not another speculative packaging redesign.

The discriminating weak-PC benchmark recorded in #80 has also settled the
interface architecture: **option A, standard Webots GUI + automatically opened
Robot Window, is the retained classroom path; option B must not be prototyped
without new contradictory evidence**. Chrome was observed fluid on the reference
low-end Windows PC, the Robot Window opened without window hunting, and offline
relaunch worked after preparation/cache. Remaining cache, browser and packaging
revalidation belongs to #81 rather than a heavier #80 architecture.

Chrome remains the reference browser for the current product-development phase.
Known Edge and Firefox gaps do not block the next Chrome-based product slices;
Firefox final same-file semantics remain tracked by #87.

## Near-term graph

### W1 — real Chrome coherence retest

- parent: #81
- depends: integrated execution-state and invalid-program corrections
- action: human/manual test on the lowest-spec classroom Windows PC with the
  current exact release artifact
- proof: one-action offline startup to `PRÊT`; normal and step execution;
  coherent workspace/file controls during execution; student-facing invalid
  program behavior; Open/Save/Save As; no regression of the previously proven
  Chrome path
- scheduling: human gate. A pending W1 must not globally idle the Controller;
  notify once, then use an independent reserve atom when available.

### W2 — formal 30-minute low-end Windows stability acceptance

- parent: #81
- depends: W1 passes
- action: human/manual stability run on the same lowest-spec classroom PC
- proof: 30 minutes offline with repeated run/reset/open/save cycles, usable
  real-time simulation, fluid Blockly interaction and no progressive memory,
  responsiveness or connection degradation; record the machine/browser/Webots
  facts required by #81

### W3 — final Windows browser/deployment closure

- parent: #81
- depends: W2 and the later browser boundary selected by current product
  priorities
- proof: #81 acceptance criteria can be closed without pretending unsupported
  browser behavior is proven
- note: do not expand this node while Chrome-based product work remains the
  validated development path.

### F1 — inventory remaining visible non-French student surfaces

- parent: #79
- depends: current Runtime v2 UI
- action: bounded audit only while another integration PR owns the lane
- proof: precise remaining student-visible strings/surfaces, separated from
  internal identifiers and machine diagnostics, with no AST/backend translation
- note: implementation becomes a normal vertical PR only when the integration
  lane is free and after checking whether the retained option A presentation
  surface changes the inventory.

### B1 — formalize the declarative activity model and compact progression

- parent: #66
- depends: PRODUCT_VISION.md
- action: bounded design/research of the smallest versionable activity/profile
  schema and representative 8-12 activity progression
- proof: a coherent model that preserves generic blocks and the
  `activity/profile -> Blockly -> AST -> preflight -> interpreter -> backend`
  pipeline without student progress state or a graphical activity studio
- note: mass activity production may rely on the now-settled option A
  presentation direction, but still waits for higher-priority product work.

### X1 — reconstruct the current Crazyflie altitude causal path

- parent: #70
- depends: current Bitcraze primary documentation/code and preserved #70 evidence
- action: independent firmware/source research covering EKF, UKF, downward ToF,
  optical-flow height scaling and the autonomous setpoint/controller path
- proof: evidence-classified causal model sufficient to design the smallest
  non-motorized discriminating experiment required by #70
- independence: preferred deep reserve work when current Runtime/UI work is
  externally waiting; do not modify Runtime v2 or perform motorized flight.

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
- keep deferred while higher-value critical/reserve work remains executable.

### R — final real-flight activity

- parent: #72
- depends: coherent progression + proven physical backend + any #70 capability
  required by the chosen final mission
- proof direction: exact simulation-validated student program, explicit teacher
  authorization, independent preflight/failsafe and representative safe real
  execution
- do not decompose the detailed final course before these gates converge.

## Roadmap maintenance rule

A proof or experiment that changes a prerequisite changes this file before the
old prerequisite is used to schedule later work. Keep the edit local: remove or
rewrite the affected dependency, or add a newly demonstrated gate. Completed
near-term atoms may be condensed into the baseline instead of accumulating
manual status fields.
