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

### R2 — PREPARE boundary and immutable negative observation

A raw mutable GitHub proposal is evidence until the protocol observes and
canonicalizes it. The abstract `proposalPresent` transition represents that
protocol-visible capture boundary.

After capture, a trusted blocking-negative is monotone authority input:
`EditProposal` may corrupt the mutable projection but cannot silently withdraw
the captured negative. Explicit resolution/withdrawal requires a separate
authoritative operation.

PREPARE remains durable before Gate FAILURE. After PREPARE the exact rejection
Head is blocked independently of `Applies`.

PREPARE does not itself revoke an already-fresh SUCCESS. While V5 is required,
however, the eventual merge effect is serialized by the same Publisher as the
negative linearization, eliminating an independent Controller merge request
that could linearize after a prior trunk block.

### R3 — Protocol Gate

`UniqueFreshSuccess` abstracts one fresh required Check Run from the exact
dedicated Protocol App.

The real ruleset must reject same-name checks from GitHub Actions or any other
App.

### R4 — Duplicate and retention recovery

Physical duplicate Check Runs may remain forever.

A detected duplicate becomes protocol knowledge as soon as durable poison
PREPARE exists. The affected Head remains fail-closed across epochs until
poison COMMIT.

Recovery is intentionally conservative:

```text
duplicate observed
-> poison PREPARE
-> Checks may disappear
-> Publisher may reassert FAILURE from PREPARE
-> poison COMMIT
```

The current physical `gateCount > 1` is required to create PREPARE, but is no
longer required to complete the poison linearization after PREPARE. Challenge
whether the Protocol App can always recreate/reassert the blocking Gate with
the intended minimal permissions.

### R5 — Merge serialization / base freshness

While any V5 epoch is required, normal merges refine `PublisherMergePR`, not
an independent Controller environment step.

Concrete requirements:

- only the normal V5 Publisher path may issue the automated merge effect;
- it reconstructs current global authority/trunk state immediately before the
  merge effect;
- the merge request supplies the exact current PR SHA;
- GitHub `expected_head_sha`/merge `sha` protects exact-head linearization;
- successful merge stales every remaining PR in the abstraction;
- concrete base refresh creates a distinct SHA incorporating the current base;
- `HeadChange` / `RefreshBase` cannot replay a Head already present in
  authority/proposal/merged history.

When no V5 epoch is required, `V4MergePR` models the restored V4 path.

Attack both the GitHub permission/isolation story and the claim that an old
unmerged SHA cannot be relabeled as a fresh current-base candidate.

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

All normal V5 merge effects and negative Gate linearizations are ordered inside
the Publisher Authority Plane.

If negative linearization wins first, `trunkBlocked` is visible before any
later Publisher merge and ordinary integration stops.

If merge wins first, the later refutation is a genuine late refutation and sets
`trunkBlocked = TRUE`.

The concrete refinement must therefore eliminate independent automated
Controller merge requests while V5 is required. A root-owner manual merge is
still possible but leaves the guarantee envelope as
`HumanGovernanceOverride`.

Rollback must project a live trunk block into V4 before the last V5 guard is
removed.

### R8 — V4/V5 semantic boundary

The model covers authority preservation through cut-over and downgrade, not
ordinary future V4 decision execution after V5 has retired.

Before V5 removal, V4-compatible durable state must contain:

- every authoritative V5 finding;
- every terminal Head;
- every live checkpoint;
- any trunk-health block.

After `v5Retired = TRUE`, `PublisherStep` is closed and new V5 proposal
publication is disabled. A late human PASS/FAIL that should affect V4 must be
represented as V4 authority, not processed by the retired V5 Publisher.

Finding downgrade remains conservative: candidate-specific dispositions do not
globally retire findings that may apply to future Heads.

### R9 — Content identity

Canonical serialization, hashes, exact Git commit identity and collision
resistance are abstracted to identifiers and remain conformance obligations.

## Trust assumptions to challenge

- Protocol App credential isolation is real;
- only the serialized Publisher can use it;
- while V5 is required, Controllers have no independent normal merge-effect
  credential/path; owner-root manual override is outside the guarantee envelope;
- the Publisher can perform exact-head PR merge with its intended permissions;
- required-check source is the exact Protocol App;
- Authority Ledger history is append-only for the App;
- poison events survive Check Run mutation/retention loss;
- all GovernanceManifest dimensions are observable with minimal permissions;
- trusted negative proposal observation/canonical ingestion is durable enough
  that later GitHub edits cannot erase the captured payload;
- poison PREPARE remains sufficient to reassert FAILURE after Check retention
  loss;
- events can be treated as wake-up hints because periodic reconciliation exists;
- exact-head merge and conditional-ref substrate behavior remain as empirically
  established;
- V4 really interprets the downgrade projections used here;
- the strict-base abstraction matches actual GitHub semantics for shared Heads.

## Critical design choices intentionally attackable

### A — PREPARE does not itself revoke an already-fresh SUCCESS

PREPARE blocks new positive publication but does not mutate an already-fresh
SUCCESS.

The important change is that, while V5 is required, **merge and negative
linearization are both Publisher effects**. There is no normal independent
Controller merge request in flight.

Thus the model still permits either Publisher ordering:

```text
merge first -> later refutation -> trunkBlocked

negative FAILURE first -> trunkBlocked -> later merge disabled
```

Challenge whether this serialized boundary is implementable with actual GitHub
permissions/rulesets and whether the human-root exception is correctly scoped.

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
14. after a trusted NO_GO is protocol-visible, can EditProposal make SUCCESS
    eligible again before PREPARE?
15. can E1 advance/remove after a duplicate is observed but before poison
    PREPARE?
16. after poison PREPARE, can Check retention loss prevent FAILURE reassertion
    and COMMIT?
17. can an old authority-seen unmerged Head be reused by HeadChange/RefreshBase
    after a base advance?
18. after a late negative linearizes, is there any normal non-Publisher merge
    path that can still reach GitHub?
19. after v5Retired, can any V5 Publisher/checkpoint transition still change
    restored V4 eligibility?

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
