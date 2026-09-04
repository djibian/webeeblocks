# WebeeBlocks roadmap

PRODUCT_VISION -> product issues -> ROADMAP -> Controller execution

This file expresses product intent, dependencies, priority and exit criteria.
GitHub contains live branches, PRs, HEADs, CI, reviews and evidence and is
authoritative over stale prose here.

## Priority order

1. #81 — Windows classroom deployment
2. #80 — one-click unified classroom interface
3. #79 — fully French student interface
4. #66 — progressive pedagogical activity model

Research/later work:
- #70 — world altitude over surface discontinuities
- #87 — Firefox direct .wbb parity
- #72 — teacher-authorized final real-flight activity

## Validated Windows baseline

Reference path: Dell OptiPlex 3050, Windows 11, Chrome, Webots R2025a.

- W1 coherence: PASS — exact Windows artifact, offline one-action startup to
  PRÊT, normal/step execution, coherent execution-state controls,
  student-facing unsupported-block handling and Open/Save/Save As.
- W2 stability: PASS — 30 minutes offline with repeated run, step, Continue,
  reset, Open, Save As and Save cycles; simulation/Blockly/runtime remained
  fluid with no progressive degradation.

Exact W1/W2 evidence and artifact provenance are preserved on issue #81.

### Product findings discovered during W2

These are durable product work and do not invalidate W2 stability:
1. a program without atterrir currently produces a generic technical error
   instead of a student-correctable diagnostic;
2. there is no user command to voluntarily interrupt an active flight;
3. a purely visual movement of the Blockly program can trigger a false
   "Programme modifié : Réinitialisez la simulation avant de relancer" warning
   although program logic did not change.

Controllers should turn these into the smallest useful product slices according
to current #81/#80 priority and existing GitHub work.

Chrome remains the reference browser for current product development. Known Edge
and Firefox gaps do not block Chrome-based slices; Firefox same-file semantics
remain tracked by #87.

## Near-term nodes

### W3 — final Windows browser/deployment closure
- parent: #81
- depends: W1 PASS and W2 PASS (satisfied) plus the later browser boundary
- proof: close #81 acceptance without claiming unsupported browser behavior.

### F1 — remaining visible non-French student surfaces
- parent: #79
- proof: bounded inventory separating student-visible strings from internal
  identifiers/diagnostics.

### B1 — declarative activity model and compact progression
- parent: #66
- proof: smallest versionable activity/profile schema and representative 8–12
  activity progression preserving the backend-neutral pipeline.

### X3 — surface-offset Lab prototype
- parent: #70
- depends: preserved S1/S2 physical evidence and current Bitcraze stable source
- proof: isolated exact-upstream candidate with build/static diagnostics before
  any new physical trace is requested.

## Later gates

### P — physical backend capability and safety
Capability contract, preflight, arming/abort/failsafe and simulation/physical
AST continuity without granting authority to student code.

### FF — Firefox same-file semantics
Parent #87. Causal diagnosis first; implementation after a viable path is proven.

### R — final real-flight activity
Parent #72. Depends on coherent progression and proven physical backend; requires
explicit teacher authorization and representative safe real execution.

## Maintenance rule

When evidence changes a product dependency, update the smallest affected roadmap
fragment. Completed nodes may be condensed into the validated baseline. Do not
add manual workflow states, agent ownership, WIP counters or execution queues.
