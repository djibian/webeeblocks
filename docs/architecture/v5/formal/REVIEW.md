# WebeeBlocks V5-0 — Adversarial review contract

## Objective

This Draft PR is intentionally a **falsification target**.

Do not optimize or implement V5. Try to break the exact frozen formal candidate.

Useful outcomes include:

1. an abstract counterexample;
2. a false/insufficient invariant;
3. a missing transition or state dimension;
4. a GitHub behavior that cannot refine an abstract atomic action;
5. a liveness/starvation trace;
6. a migration/rollback trace that loses decision authority;
7. a durable-history claim that cannot survive restart or retention limits.

Always reconstruct Draft PR #191 first and record its exact HEAD. A changed HEAD
is a new candidate and invalidates any prior positive verdict.

## Canonical inputs

Read completely:

- `WebeeBlocksV5.tla`;
- `PROPERTIES.md`;
- `REVIEW.md`.

Inspect the full finite harness:

- `WebeeBlocksV5_MC.tla`;
- `WebeeBlocksV5_Ordering.cfg`;
- `WebeeBlocksV5_EpochTerminal.cfg`;
- `WebeeBlocksV5_EpochRepair.cfg`;
- `WebeeBlocksV5_Duplicate.cfg`;
- `WebeeBlocksV5_PendingHead.cfg`;
- `WebeeBlocksV5_SharedHead.cfg`;
- `WebeeBlocksV5_LateRefutation.cfg`;
- `WebeeBlocksV5_Checkpoint.cfg`;
- `WebeeBlocksV5_Migration.cfg`;
- `run_tlc.sh`.

The runner pins TLA+ 1.7.4 by SHA-256, parses with SANY and executes all nine
finite safety domains.

A green bounded run is evidence only, never proof of liveness or GitHub
refinement.

## Safety versus liveness

`SafetySpec`:

```text
Init /\ [][Next]_vars
```

is what the finite configs model-check.

`Spec` additionally assumes:

```text
WF_vars(PublisherStep)
```

Review this fairness assumption independently. In a stable finite environment,
all Publisher reconciliation classes are intended to be finite/progress-making;
look for any transition that can self-reenable, oscillate or starve unrelated
work.

## Refinement boundaries

### R1 — Authority Ledger

Abstract monotone sets for rejection and poison authority refine append-only
durable Git history.

Normal rejection lifecycle:

```text
PREPARE rejection
-> Protocol Gate FAILURE
-> COMMIT rejection
```

Duplicate poison lifecycle:

```text
PREPARE poison
-> Protocol Gate FAILURE / poison linearization
-> COMMIT poison
```

Concrete V5 must allow the Protocol App to append required Ledger events while
denying deletion/non-fast-forward rewrite of protected authority history.

Check Runs and reviews are mutable enforcement/projection surfaces, not the
permanent authority store.

### R2 — PREPARE boundary

A durable trusted negative proposal blocks new positive publication before
PREPARE.

After PREPARE the rejection blocks its exact `RejectionHead` independently of
finding applicability. `Applies` only controls whether findings constrain
other candidate Heads.

PREPARE does not revoke an already-linearized SUCCESS. Until Gate FAILURE
linearizes, a merge may still win.

That is a deliberate boundary. If merge wins, the subsequent authoritative
refutation must trigger the trunk-health consequence in R7.

### R3 — Protocol Gate

`UniqueFreshSuccess` abstracts one fresh required Check Run from the exact
dedicated Protocol App.

The real ruleset must reject same-name checks from GitHub Actions or any other
App.

### R4 — Duplicate

Physical duplicate Check Runs may remain forever. The model never requires
their deletion or `gateCount` normalization.

A duplicate is considered reconciled only after append-only poison COMMIT.
A pending ordinary rejection on an already-poisoned pair may still linearize
and COMMIT.

Challenge whether this durable poison lifecycle can be implemented with the
intended minimal App permissions and reconstructed after GitHub Check retention.

### R5 — Merge / base freshness

`MergePR` abstracts:

- exact current `prHead`;
- current protected base;
- `expected_head_sha = current prHead`.

Successful merge atomically makes every remaining open PR base-stale in the
abstraction.

A stale PR becomes fresh only via `RefreshBase` with a distinct non-integrated
Head. Ordinary `HeadChange` also cannot select an already integrated exact
Head while preserving normal strict-base refinement.

Attack this abstraction against actual GitHub merge/update semantics, including
two PRs that initially share one Head.

### R6 — GovernanceEpoch

Epoch identity is stable and opaque.

- GO is epoch-bound.
- Unapplied disposition proposals are epoch-bound.
- Applied dispositions remain durable decision history.
- leaving E1 retires it permanently;
- retired epochs cannot be re-required/reactivated;
- observability loss or drift removes the epoch from `operationalEpochs`;
- AdvanceEpoch and V4 guard removal require current observable/matching
  governance;
- observed drift cannot be repaired in place.

Governance is human-rooted and protocol-verified, not protocol-admin-enforced.

### R7 — Late refutation / trunk health

If Gate FAILURE or duplicate poison linearizes after its exact Head has already
merged, `trunkBlocked` becomes TRUE.

Normal V5 integration then stops.

V5 rollback must project the block into `v4ProjectedTrunkBlocked` before the
last V5 guard is removed. V4 merge eligibility remains fail-closed at the
modeled downgrade boundary.

V5-0 deliberately does not model autonomous clearing of this state.
Revert/fix-forward/adjudication of a known-bad trunk remains a V4/human-rooted
recovery obligation.

Try hard to show that this consequence is still insufficient or cannot refine
the existing V4 Healthy Trunk contract.

### R8 — V4/V5 semantic boundary

The model covers authority preservation through cut-over and downgrade, not
ordinary future V4 decision execution after V5 has retired.

Before V5 removal, V4-compatible durable state must contain:

- every authoritative V5 finding;
- every terminal Head;
- every live checkpoint;
- any trunk-health block.

Finding downgrade is conservative: candidate-specific dispositions do not
globally retire findings that may apply to future Heads.

### R9 — Content identity

Canonical serialization, hashes, exact Git commit identity and collision
resistance are abstracted to identifiers and remain conformance obligations.

## Trust assumptions to challenge

- Protocol App credential isolation is real;
- only the serialized Publisher can use it;
- required-check source is the exact Protocol App;
- Authority Ledger history is append-only for the App;
- poison events survive Check Run mutation/retention loss;
- all GovernanceManifest dimensions are observable with minimal permissions;
- events can be treated as wake-up hints because periodic reconciliation exists;
- exact-head merge and conditional-ref substrate behavior remain as empirically
  established;
- V4 really interprets the downgrade projections used here;
- the strict-base abstraction matches actual GitHub semantics for shared Heads.

## Critical design choices intentionally attackable

### A — Merge may beat PREPAREd refutation

PREPARE blocks **new** positive publication, but does not invalidate an already
fresh SUCCESS.

Until Gate FAILURE:

```text
merge may linearize first
```

If it does, the later FAILURE must set `trunkBlocked`.

Challenge whether a transient interval with merge eligibility is acceptable
even with that recovery consequence. If not, PREPARE must become merge-blocking
and the architecture changes.

### B — Physical duplicates are not deleted

The durable end-state is committed poison, not `gateCount = 1`.

Challenge whether every same-App homonymous Check Run can actually be forced to
a blocking conclusion and whether the ruleset can remain fail-closed when
multiple physical runs persist.

### C — Positive authority has no Ledger PREPARE

SUCCESS itself is the positive linearization and can be revalidated.

Challenge whether forensic reconstruction or governance succession needs a
durable positive audit event stronger than `positiveAudit`.

### D — Applicability remains semantic

`Applies(f,H)` is abstract. The protocol does not pretend to mechanically know
future semantic applicability.

Downgrade therefore preserves every authoritative finding that has not been
globally retired by a separately modeled authority mechanism (none exists in
V5-0).

### E — Exact rejected/poisoned Head is permanently terminal

Governance changes cannot rehabilitate the identical commit SHA. Repair requires
a distinct Head.

Challenge whether any legitimate governance succession requires same-SHA
rehabilitation.

### F — Trunk block clearing is outside V5-0

The formal model can enter a known-bad-trunk state but cannot autonomously leave
it. This is deliberately conservative.

Challenge whether rollback to V4 with a durable block is sufficient to claim
reversibility, or whether a complete V5 formal model must include repair and
explicit unblock semantics.

## Mandatory reviewer attacks

Re-run the prior NO_GO findings against the new exact SHA, including:

1. PREPARE with `Applies = {}`: can new SUCCESS still appear?
2. physical duplicate count remains >1 after poison: can rollback still finish?
3. trusted NO_GO pending on an already-poisoned pair: can it reach COMMIT?
4. restart after Check retention loss: can poison/terminality be reconstructed
   from the Ledger rather than mutable checks?
5. two PRs sharing one Head: can both merge against one base generation?
6. merge-wins late refutation: does the later FAILURE block subsequent ordinary
   integration and survive V5->V4 downgrade?
7. governance drift after Verify but before AdvanceEpoch/RemoveV4Guard;
8. an E1 disposition proposal left unapplied until E2: can it still be promoted?
9. can authority finding history shrink across epoch transitions while its
   invariant still passes?
10. can HeadChange/RefreshBase replay a previously integrated exact Head while
    preserving base freshness?
11. can any poison/review/publisher transition oscillate forever under stable
    finite work and satisfy aggregate weak fairness while starving another?
12. can a future-applicability finding be lost at downgrade?
13. can a root-admin governance mutation occur before the Publisher observes it
    while the model still claims normal guarantees?

Also search outside these known traces. A reviewer that only checks the listed
fixes has not completed an adversarial review.

## Required procedure

1. Reconstruct Draft PR #191 and record exact current HEAD.
2. If HEAD differs from the supplied candidate SHA, stop: it is a new candidate.
3. Read all three canonical design files completely.
4. Inspect all nine finite configs, MC module and `run_tlc.sh`.
5. If possible execute:
   `bash docs/architecture/v5/formal/run_tlc.sh`
   on the exact reviewed SHA.
6. A green run is bounded evidence only.
7. Re-evaluate all prior authoritative findings against the complete model.
8. Try new abstract, liveness, governance and GitHub-refinement traces.
9. Publish findings directly on PR #191.
10. Do not modify the PR branch.

## Required output

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

End with exactly one:

```text
FORMAL_REVIEW: GO <sha>
FORMAL_REVIEW: NO_GO <sha>
FORMAL_REVIEW: UNPROVEN <sha>
```

The reviewer connection uses the same GitHub identity (`djibian`) as the PR
author, so use a PR comment or COMMENTED review rather than REQUEST_CHANGES.

GO means only that no blocking counterexample was found in the reviewed formal
and refinement scope. It does not mean V5 is implemented or substrate-accepted.
