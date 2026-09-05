# WebeeBlocks V5-0 — Adversarial review contract

## Objective

This Draft PR is intentionally a **falsification target**.

Do not optimize the model, implement V5, or approve it by default. Try to break
it.

Useful reviewer outcomes are:

1. an abstract counterexample in the TLA+ state machine;
2. a false or insufficient invariant;
3. a missing state/transition that invalidates a claimed property;
4. a GitHub behavior that cannot refine an abstract atomic action;
5. a liveness assumption that cannot be implemented reliably;
6. a migration/rollback trace that loses live decision authority.

Always reconstruct GitHub first and review the **exact current HEAD SHA of this
Draft PR**. State that SHA in every finding and in the final verdict.

A new HEAD is a new formal candidate. Do not reuse a GO from an older HEAD.

## Canonical inputs

The canonical model is:

- `WebeeBlocksV5.tla` — abstract authority state machine;
- `PROPERTIES.md` — claims to prove or falsify;
- this file — refinement boundary and review protocol.

The canonical finite TLC harness is:

- `WebeeBlocksV5_MC.tla`;
- `WebeeBlocksV5_Ordering.cfg`;
- `WebeeBlocksV5_EpochTerminal.cfg`;
- `WebeeBlocksV5_EpochRepair.cfg`;
- `WebeeBlocksV5_Duplicate.cfg`;
- `WebeeBlocksV5_Checkpoint.cfg`;
- `WebeeBlocksV5_Migration.cfg`;
- `run_tlc.sh`.

`run_tlc.sh` verifies a pinned TLA+ 1.7.4 `tla2tools.jar` SHA-256, parses
with SANY, and executes all six finite safety configurations.

During model authoring, a temporary branch-only Actions workflow may call this
runner against the exact PR HEAD. That workflow is experimental test
infrastructure only and must be removed before the candidate is frozen, because
the active V4 repository contract forbids additional workflows.

A successful finite TLC run is evidence, not a proof of the whole protocol.

## Scope represented by the model

The model includes:

- multiple PRs, including PRs sharing the same Git head;
- trusted versus external cognitive proposals;
- proposal mutation/corruption;
- proposal GovernanceEpoch provenance;
- Authority Ledger PREPARE / Gate FAILURE linearization / COMMIT;
- durable findings and candidate-specific dispositions;
- globally terminal rejected/poisoned heads;
- REQUEST_CHANGES projections and review corruption;
- Protocol Gate SUCCESS / FAILURE / freshness / revalidation;
- duplicate Protocol-App Gate fault injection and poisoning;
- human checkpoints;
- governance observability, drift and epoch succession;
- V4 findings and rejected-head authority import;
- V5 findings, terminal-head and checkpoint downgrade projection;
- explicit V5 retirement;
- V4 known operational fallback;
- strict-base state and base-refresh-as-new-head;
- exact-head merge;
- HumanGovernanceOverride;
- weakly-fair Publisher reconciliation.

It deliberately does **not** model product-task scheduling.

## Safety versus liveness

`SafetySpec` contains only:

```text
Init
/\ [][Next]_vars
```

The finite CI configurations model-check safety invariants over bounded domains.

`Spec` adds:

```text
WF_vars(PublisherStep)
```

That fairness clause is an explicit liveness assumption. The finite CI models do
not prove it. Review it independently.

## Deliberate abstraction / refinement boundaries

### R1 — Authority Ledger append

Abstract monotone set growth represents append-only durable authority history.

Concrete V5 must establish that the authority writer can append the required
Ledger event but cannot delete or non-fast-forward rewrite protected Ledger
history.

The Ledger is the durable anchor; mutable Check Runs and reviews are not the sole
history source.

### R2 — Negative linearization

`PREPARE` is durable write-ahead evidence.

Authoritative negative revocation linearizes at the Protocol Gate transition to
FAILURE. `COMMIT` records that the Gate linearization completed.

A crash after Gate FAILURE but before COMMIT must be reconstructible from
PREPARE.

### R3 — Protocol Gate

One abstract Gate create/update represents one GitHub Check Run written by the
exact dedicated Protocol App.

The real ruleset must bind the required check to that exact App source.
Same-name checks from GitHub Actions or another App must not satisfy V5.

### R4 — Review projection

A `REQUEST_CHANGES` review is a PR-level projection of already-durable negative
authority.

Review mutation/dismissal must never rewrite the Ledger or remove global
terminal-head memory.

The model treats a blocking review on one open PR as blocking other open PRs
that point to the exact same head. Challenge whether this matches the concrete
GitHub behavior closely enough.

### R5 — Merge

`MergePR` abstracts:

- protected base is current;
- the candidate is the current exact PR head;
- merge is attempted with `expected_head_sha = current prHead`.

A protected-base refresh creates a new `Head` identity.

A deliberate root-human merge outside the protocol is a
`HumanGovernanceOverride`, not a protocol transition.

### R6 — GovernanceEpoch

Epoch identity is abstracted as a stable opaque identifier.

GO proposals are epoch-bound. V5 positive authority can only be published for
the active, required epoch. Epoch succession is irreversible: leaving E1 adds
it to `retiredEpochs`; a retired epoch can never become active or required
again.

A temporary observability outage may be restored only if the same manifest still
matches.

Once `DriftGovernance(E)` records a manifest mismatch, that epoch cannot be
reconfigured in place; normal operation requires a successor epoch.

Governance changes remain human-rooted. The Publisher verifies them but does not
possess repository administration power to force their ordering.

### R7 — Content identity

Canonical serialization, hashes, Git commit identity and collision resistance
are abstracted to stable identifiers. They remain implementation/conformance
obligations.

### R8 — V4/V5 boundary

The state machine models the **semantic cut-over and downgrade boundary**, not
the full future execution semantics of V4 after V5 has retired.

The required property is preservation: every live V5 finding, terminal head and
checkpoint that must survive downgrade is materialized in V4-compatible durable
state before the last V5 guard is removed.

After that boundary, ordinary new V4 decisions are governed by the existing V4
contract, not by this V5 state machine.

## Strong trust assumptions to challenge

- the Protocol App credential is uncompromised;
- only the serialized Publisher can use that credential;
- exact App-source isolation is configured correctly;
- the Protocol App cannot rewrite/delete Authority Ledger history;
- every GovernanceManifest component claimed by V5 is observable with
  read-only/minimal permissions;
- a governance drift cannot be silently normalized back into the same epoch;
- periodic reconciliation justifies the Publisher fairness assumption;
- GitHub exact-head merge and conditional-ref behavior continue to match the
  experimentally established substrate contract;
- GitHub's required-check source selection distinguishes the dedicated Protocol
  App as assumed;
- V4 downgrade projections are actually interpretable by the restored V4
  machinery.

## Critical design choices intentionally left attackable

### A — PREPARE is not the NO_GO linearization point

A trusted blocking-negative proposal prevents **new** positive publication even
before PREPARE.

PREPARE then makes the negative evidence crash-durable.

But PREPARE does not retroactively erase an already-linearized fresh SUCCESS.
Until Gate FAILURE linearizes the negative, a concurrent merge may win.

That outcome is classified as:

```text
merge linearized first
-> later NO_GO is a late refutation
```

not as a protocol safety violation.

Try to refute this boundary. If PREPARE itself must atomically close merge
eligibility, the architecture must change.

### B — Duplicate Protocol-App writer

The model can inject a duplicate and poison it after detection.

It does **not** claim GitHub atomically prevents a buggy/compromised second
Protocol-App writer before detection. Normal safety depends on isolated
credentials and one serialized authority writer.

Before V5 retirement, all observed duplicate pairs must be drained.

If that assumption is too strong, reject the trust model or require a stronger
split trust root.

### C — Positive authority has no write-ahead Ledger PREPARE

Negative authority has write-ahead durability.

Positive authority is deliberately ephemeral/revalidatable. Its linearization is
the Gate SUCCESS itself.

Challenge whether a durable positive PREPARE/COMMIT audit trail is required for
reconstruction, governance succession or forensic correctness.

### D — Applicability is abstract

`Applies(finding, head)` is an abstract semantic relation.

Downgrade avoids relying on enumeration of future applicability by projecting
**every authoritative V5 finding**, not only currently unresolved/applicable
ones.

Challenge whether applicability changes themselves need authoritative events or
versioned semantics.

### E — Rejected HEAD is terminal globally

Once rejected/poisoned, the exact Git commit cannot be made positive again by a
new GovernanceEpoch.

Repair requires `H2 != H`.

Challenge whether there exists a legitimate governance transition that must be
able to rehabilitate the identical commit SHA. If so, the terminal-head policy
is too strong and must be redesigned explicitly rather than weakened
accidentally.

## Reviewer questions

1. Can durable GO and durable NO_GO both exist before Publisher processing and
   still allow GO to be published first?
2. Can an unprepared or pending trusted negative disappear across an epoch
   transition or V5 rollback?
3. Can an already-fresh SUCCESS plus later negative proposal create an
   unacceptable merge race before Gate FAILURE?
4. Can a rejected/poisoned head become positive in another epoch by any path?
5. Can an old-epoch GO mint or revalidate authority after `AdvanceEpoch`?
6. Can any trace realize `E1 -> E2 -> E1`, or re-require E1 after it enters
   `retiredEpochs`?
7. Can V5 publish any SUCCESS before V4 legacy findings/rejected-head memory is
   imported?
8. Can temporary loss of observability plus `ConfigureEpoch` resurrect old
   authority after a real governance drift?
9. Can a duplicate Gate appear before/during rollback and escape V4 terminal-head
   projection?
10. Can `HUMAN_FAIL` be overwritten by a same-head PASS or fail to revoke
    positive authority through the negative path?
11. Can a protected-base refresh become fresh again without creating a new head?
12. Can two PRs sharing one head diverge in blocking-review semantics in a way
    the abstraction misses?
13. Can a finding that is irrelevant now but applicable to a future head be lost
    during V5 -> V4 downgrade?
14. Can review/proposal mutation invalidate the reconstruction assumptions?
15. Does aggregate `WF_vars(PublisherStep)` still allow starvation between
    reconciliation classes even when individual actions make progress?
16. Can a root-admin governance change occur while the model still claims
    `guaranteeActive = TRUE` but before the Publisher can observe it?
17. Is the Authority Ledger permission model implementable without giving the
    Protocol App an unacceptable product-history rewrite capability?
18. Do the six finite TLC scenarios omit a small domain that can expose a
    qualitatively different counterexample?

## Required reviewer procedure

1. Reconstruct Draft PR #191 and record its exact current HEAD.
2. Read the three canonical design files completely.
3. Inspect the finite MC module/configurations and `run_tlc.sh`.
4. Execute `bash docs/architecture/v5/formal/run_tlc.sh` on the exact reviewed
   SHA if your environment permits it. If not, state that limitation explicitly.
5. You may inspect historical temporary `V5 Formal TLC` authoring runs as
   supporting evidence, but do not treat them as authority for a different SHA.
6. Do not infer proof from a green finite run.
7. Try explicit state-machine traces, TLA+/TLC variants, and GitHub refinement
   attacks.
8. Re-evaluate earlier findings against the **new** candidate rather than merely
   checking the diff that purported to fix them.
9. Publish findings directly on PR #191.
10. Do not modify the branch.

## Required reviewer output

For every finding:

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

`GO` means only that no blocking counterexample was found in the stated formal
and refinement scope. It does **not** mean V5 is implemented, substrate-accepted
or ready to replace V4.

## Where to publish findings

Publish the review directly on Draft PR #191.

The reviewer connection uses the same GitHub identity (`djibian`) as the PR
author, so GitHub cannot accept `REQUEST_CHANGES` on this PR. Use a PR comment
or a `COMMENTED` review and encode the verdict textually, bound to the exact
reviewed SHA.

Do not modify the branch. The author will create the next candidate HEAD if a
finding requires correction.
