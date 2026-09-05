# WebeeBlocks V5-0 — Adversarial review contract

## Objective

This branch is intentionally a **falsification target**. Do not optimize the model, implement V5, or approve it by default. Try to break it.

The useful reviewer outcomes are:

1. an abstract counterexample in the TLA+ state machine;
2. a missing state/transition that invalidates a claimed invariant;
3. a GitHub behavior that does not refine an abstract atomic action;
4. a liveness assumption that cannot be implemented reliably;
5. a migration/rollback trace that loses live decision authority.

## Canonical inputs

- `WebeeBlocksV5.tla` — abstract state machine;
- `PROPERTIES.md` — claims to prove or falsify;
- this file — refinement boundary and review protocol.

Always review the **exact current HEAD SHA of this Draft PR**. State that SHA in the verdict.

## Scope represented by the model

The model includes:

- multiple PRs, including PRs sharing the same Git head;
- trusted versus external cognitive proposals;
- proposal mutation/corruption;
- Authority Ledger PREPARE / negative Gate linearization / COMMIT;
- durable findings and candidate-specific dispositions;
- REQUEST_CHANGES projections and review corruption;
- Protocol Gate SUCCESS / FAILURE / freshness / revalidation;
- duplicate Protocol-App Gate fault injection;
- human checkpoints;
- dual epoch guards and epoch succession;
- V4 authority import;
- V5 authority downgrade projection;
- V4 known operational fallback;
- strict-base state;
- exact-head merge;
- HumanGovernanceOverride;
- weakly-fair publisher reconciliation.

## Deliberate abstraction / refinement boundaries

### R1 — Authority Ledger append

Abstract monotone set growth represents an append to a protected Git branch. Concrete V5 must prove that the Protocol App may append but cannot bypass deletion/non-fast-forward protection of the ledger history.

### R2 — Protocol Gate

One abstract Gate mutation represents one GitHub Check Run create/update by the exact dedicated Protocol App. The real ruleset must bind the required check to that App source.

### R3 — Review projection

One abstract review action represents one `REQUEST_CHANGES` creation/dismissal. Review edits are modeled as projection corruption; they must never rewrite durable authority.

### R4 — Merge

`MergePR` abstracts strict current base plus `expected_head_sha = current prHead`. A deliberate root-human merge outside the protocol is outside the normal guarantee envelope.

### R5 — Governance

Ruleset, environment and App changes remain human-rooted. V5 verifies observed normal transitions; it does not possess administration authority to force their ordering.

### R6 — Content identity

Canonical serialization, hashes, Git commit identity and collision resistance are abstracted to stable identifiers. They require implementation/conformance tests.

## Strong trust assumptions to challenge

- Protocol App credential is uncompromised.
- Only the serialized Publisher can use that credential.
- exact App source isolation is correctly configured.
- the Protocol App cannot rewrite/delete Authority Ledger history.
- every GovernanceManifest component claimed by V5 is observable with read-only/minimal permissions.
- periodic reconciliation justifies the weak-fairness assumption.
- GitHub exact-head merge/ref CAS behavior continues to match the experimentally established substrate contract.

## Critical design choices intentionally left attackable

### A — PREPARE is not yet authoritative NO_GO

`PREPARE` makes negative evidence durable and blocks **new positive publication**, but negative authority linearizes only at `Gate -> FAILURE`. Therefore a merge that linearizes before Gate failure is classified as a late refutation rather than a protocol violation.

Rollback has an additional fail-closed rule: V5 requirements cannot be removed while any PREPARE remains unlinearized, and a new PREPARE is not admitted after all V5 requirements have been removed. This is intended to preserve write-ahead evidence across V5 -> V4 without redefining PREPARE itself as the NO_GO linearization point.

Try to decide whether this boundary is acceptable or whether PREPARE itself must close merge eligibility.

### B — Duplicate Protocol-App writer

The model can inject a duplicate and poison it after detection. It does **not** claim GitHub atomically blocks a buggy/compromised second Protocol-App writer before detection. Normal safety depends on credential isolation + one serialized Publisher.

If this assumption is too strong, reject the architecture or require a split trust root.

### C — Positive authority is not write-ahead durable

Negative authority has durable write-ahead memory. Positive authority is deliberately revalidatable/ephemeral. Challenge whether positive decisions also require a durable PREPARE/COMMIT trail.

### D — Applicability relation

`Applies(finding, head)` is abstract. Challenge whether changes to applicability semantics across epochs must themselves be explicit authority events.

## Reviewer questions

1. Can an unresolved PREPARE coexist with an already fresh SUCCESS in a way that still permits merge?
2. Can an epoch transition make a stale/old SUCCESS usable under a new manifest?
3. Does review blocking across two PRs sharing the same head match GitHub closely enough?
4. Can rollback project only currently visible blockers and accidentally lose a finding applicable to a future candidate?
5. After requiring each publisher disjunct to make strict progress when enabled, does aggregate `WF_vars(PublisherStep)` still overstate real liveness or permit starvation among reconciliation classes?
6. Can `LoseObservability` after SUCCESS leave a protocol-compliant merge path that should have been blocked?
7. Is the V4 upgrade abstraction too strong because `LegacyFindings` are globally known before import?
8. Does a second NO_GO on an already failed head need a different linearization rule?
9. Should the Authority Ledger use a separate App to reduce Protocol App `contents:write` blast radius?
10. Can a root-admin governance change occur without being detected quickly enough while the model still claims `guaranteeActive = TRUE`?

## Required reviewer output

For every finding, use:

```text
Severity: BLOCKING | MAJOR | MINOR
Layer: ABSTRACT_MODEL | REFINEMENT | LIVENESS | GOVERNANCE
Invariant/assumption:
Exact reviewed SHA:
Counterexample trace:
Why the trace is permitted:
Impact:
Smallest correction:
Reopen V5-0? YES/NO
```

End with exactly one overall verdict:

```text
FORMAL_REVIEW: GO <sha>
FORMAL_REVIEW: NO_GO <sha>
FORMAL_REVIEW: UNPROVEN <sha>
```

`GO` means no blocking counterexample was found in the stated scope; it does **not** mean V5 is implemented or substrate-accepted.

## Where to publish findings

Publish the review directly on this Draft PR. Because the reviewer connection uses the same GitHub identity (`djibian`) as the PR author, GitHub cannot accept `REQUEST_CHANGES` on this PR. Use a PR comment or a `COMMENTED` review and encode authority in the exact textual verdict bound to the reviewed SHA. Do not modify the branch unless explicitly asked; the author/controller will produce the next candidate HEAD.