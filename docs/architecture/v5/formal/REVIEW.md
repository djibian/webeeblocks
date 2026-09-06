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
- `WebeeBlocksV5_MergeInFlight.cfg`;
- `WebeeBlocksV5_MergeRetry.cfg`;
- `WebeeBlocksV5_StackExclusion.cfg`;
- `WebeeBlocksV5_LegacyCheckpointCutover.cfg`;
- `WebeeBlocksV5_RetiredReplay.cfg`;
- `WebeeBlocksV5_Abandon.cfg`;
- `WebeeBlocksV5_CheckpointEpoch.cfg`;
- `WebeeBlocksV5_ExternalEvidence.cfg`;
- `run_tlc.sh`.

The runner pins TLA+ 1.7.4 by SHA-256, parses with SANY and executes all
seventeen focused finite safety domains.

A green bounded run is evidence only, never proof of liveness or GitHub
refinement.

`LateRefutation` uses a scenario-specific `LateRefutationNext` transition
relation to avoid cross-product explosion from governance, rollback, review,
duplicate and checkpoint actions that are covered independently. Reviewers must
verify that this focus still contains the full merge-wins -> late-negative ->
trunk-block -> refreshed-next-candidate attack and does not encode any target
invariant as a constraint.

`MergeInFlight` likewise uses `MergeFlightNext`. It must preserve the exact
reviewer attack E1 authorized -> SUBMIT -> E2 becomes required without E2
SUCCESS -> attempted remote outcome, as well as post-SUBMIT E1 Gate expiry,
governance drift/observability loss and an unrelated trusted NO_GO arriving on
P2. The focus must not constrain `MergeAllowed`, required epochs, Gate state,
manifest health, remote outcome, or the invariants under test.

## Safety versus liveness

`SafetySpec`:

```text
Init /\ [][Next]_vars
```

is the default safety specification for the finite configs. `LateRefutation`
and `MergeInFlight` use the same `Init` and invariant sets with respectively
`LateRefutationNext` and `MergeFlightNext`, explicit subsets of `Next`
containing only transitions relevant to their dedicated adversarial attacks.

`Spec` additionally assumes:

```text
WF_vars(PublisherStep)
/\ WF_vars(RemoteMergeExecutionStep)
```

Review both fairness assumptions independently. In a stable finite environment,
all Publisher reconciliation classes are intended to be finite/progress-making;
look for any transition that can self-reenable, oscillate or starve unrelated
work. Once a merge request has crossed the GitHub trust boundary,
`RemoteMergeExecutionStep` represents eventual terminal GitHub execution/linearization. Publisher observation of that terminal result is modeled separately and the transaction remains outstanding until observation and COMMIT.

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

### R5 — Recoverable asynchronous merge transaction / base freshness

Normal V5 merges refine GitHub async `direct_merge`, not the synchronous
endpoint and not an independent Controller effect:

```text
PREPARE exact single-PR intent
-> merge-async exact sha + direct_merge
-> durably bind/recover UUID
-> GitHub terminal execution SUCCESS|FAILURE
-> poll/observe terminal UUID result
-> COMMIT
```

V5-0 deliberately excludes GitHub stacked pull requests from this normal path.
GitHub's async endpoint can atomically merge every lower PR in a stack, while
the V5 abstract transaction is intentionally single-PR. Therefore a PR with a
non-null stack membership must not enter `mergePrepared`. Normal future V5
Controller governance must also forbid creating/restructuring stacks while V5
merge authority is active; owner-root manual stack mutation is outside the
normal guarantee envelope. The future substrate suite must verify the concrete
stack-observation and path-isolation assumptions. If this cannot be enforced
reliably, stack support requires a later explicit multi-PR authority model.

SUBMIT is not linearization. GitHub rules are applied during background
execution, so `RemoteMergeLinearizeSuccess` rechecks current merge eligibility.
A newly-required unsatisfied epoch, governance drift, stale Gate/base or other
current blocker cannot be bypassed solely because SUBMIT happened earlier.

Only one current transaction exists. Current lifecycle state is cleared only
after terminal observation/COMMIT; durable semantic history is separate.
FAILURE/CANCEL adds durable failure history. A new attempt requires a distinct
owner-authored retry token bound to exact PR, Head and Epoch. The token is
consumed atomically by PREPARE; repeated failures require new token identities.

The concrete async UUID is the transaction identity. If the initial 202/UUID
response is lost, automatic PUT retry for 409/UUID recovery is permitted only
inside a durably recorded interval strictly shorter than GitHub's documented
24-hour async result-retention horizon, with implementation safety margin.
After that recovery window may have expired, an automatic PUT is forbidden:
the Publisher remains fail-closed for human-root recovery. Unknown/404 is never
coerced into FAILURE and never silently becomes a new merge attempt.

Attack stack membership, stack mutation, UUID recovery, execution-time rules,
exact-head semantics, retention, retry-token consumption and alternate merge
paths.

### R6 — GovernanceEpoch

Epoch identity is stable and opaque.

- GO is epoch-bound.
- Human checkpoint authority is keyed by `(GovernanceEpoch, Head)`; an E1 PASS
  does not silently authorize E2.
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

The model distinguishes Publisher SUBMIT, GitHub remote execution/linearization,
and later Publisher observation/COMMIT. Only remote execution determines
whether merge or negative Gate linearization wins.

An outstanding transaction blocks unrelated Publisher authority work. If
remote SUCCESS linearized first, a later negative is a genuine late refutation
and sets `trunkBlocked = TRUE`. If current governance becomes unsatisfied
before remote execution, SUCCESS is disabled and the remote operation may
terminate FAILURE.

Raw new evidence/governance observations may arrive while a transaction is
outstanding; they do not rewrite an already-real remote SUCCESS, but current
server-enforcement state is checked at the execution point.

### R8 — V4/V5 semantic boundary

V4 -> V5 cut-over preserves legacy findings and rejected-head memory, but V5-0
does not invent a translation for an already-open V4 TEST_REQUIRED request.
Instead reconstruction exposes `LegacyCheckpointHeads`, and cut-over remains
fail-closed until that set is empty. An unresolved V4 TEST_REQUIRED must resolve
under V4 as PASS, FAIL or NOT_NEEDED before V5 positive authority or V4 guard
removal can proceed.

Before V5 removal, V4-compatible durable state must contain:

- every authoritative V5 finding;
- every terminal Head;
- every live epoch-scoped checkpoint obligation;
- any trunk-health block.

A rejected PR may be deliberately closed/abandoned without semantically
resolving its findings. Once closed, its V5 review projection may be retired
while the finding and terminal Head remain durable and are still projected to
V4 before retirement.

After `v5Retired = TRUE`, `PublisherStep` is closed and new V5 proposal
publication is disabled. V5-only `AuthoritySeenHeads` positive/proposal replay
memory no longer controls generic `HeadChange` or `RefreshBase`; restored V4
rejected-head/checkpoint/trunk-health authority owns candidate eligibility. A
late human PASS/FAIL that should affect V4 must be represented as V4 authority,
not processed by the retired V5 Publisher.

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
- the Publisher uses GitHub asynchronous `direct_merge` with exact SHA only
  for a non-stacked PR in the normal V5 path;
- normal V5 Controller governance forbids stack creation/restructuring while
  V5 merge authority is active; owner-root stack mutation leaves the guarantee
  envelope;
- the async UUID is durably bound to PREPARE/SUBMIT; lost-response 409 recovery
  is attempted only inside a durable recovery interval shorter than the 24-hour
  result-retention horizon;
- once that bounded recovery interval may have expired, no automatic recovery
  PUT is issued; unknown/expired UUID state is never converted into FAILURE or
  a new attempt and instead causes fail-closed human-root recovery;
- each merge retry authorization is a durable unique owner-authored token bound
  to PR/Head/Epoch and consumed by at most one PREPARE;
- the Publisher can perform exact-head PR merge with its intended permissions;
- a dedicated main-update exclusivity rule/ruleset grants the Protocol App only
  the bypass needed to update `main`, while required Gate/review/base-safety
  rules remain non-bypassable by that App;
- Controllers cannot use a normal merge credential/path while V5 is required;
- auto-merge and merge queue are disabled for the V5-0 normal path unless their
  pending lifecycle is explicitly modeled;
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

Negative PREPARE blocks new positive publication but does not mutate an
already-fresh SUCCESS.

V5-0 therefore makes the merge race explicit rather than pretending the Check
surface is transactional. A merge first acquires a durable Publisher
`mergePrepared` intent. After submission, the Publisher is barred from
unrelated authority work until the remote outcome is authoritatively resolved.

Thus the meaningful order is:

```text
merge transaction resolves success
-> later refutation
-> trunkBlocked

or

merge transaction closes without success
-> negative FAILURE linearizes
-> trunkBlocked
-> later normal merge disabled
```

Challenge crash recovery after request submission, authoritative distinction
between remote failure and an unknown response, and whether every concrete
merge path is forced through this barrier.

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
20. after merge PREPARE/submission and a lost response, can a later negative
    linearize before the exact remote merge outcome is reconciled?
21. can a rejected PR be closed/abandoned, its review projection retired, and
    rollback finish without falsely resolving its durable finding?
22. can an E1 checkpoint PASS satisfy E2 without explicit E2 evidence?
23. can an external valid-looking proposal reserve a future Head or otherwise
    alter HeadChange/RefreshBase eligibility?
24. can the Protocol App bypass the main-update exclusivity rule without also
    bypassing Gate/review/base-safety rules?
25. is there any auto-merge, merge-queue or alternate credential path that can
    issue a normal V5 merge outside the outstanding-transaction barrier?
26. after E1 SUBMIT, can unsatisfied E2 become required and remote SUCCESS still
    linearize?
27. after remote FAILURE or pre-submit CANCEL, can the same still-open PR,
    after explicit retry authorization, complete a fresh attempt?
28. can Publisher observation lag remote SUCCESS while later governance changes
    occur without mis-ordering actual linearization?
29. can lost async response/UUID-retention expiry ever be mistaken for
    authoritative FAILURE or trigger an unauthorized second PUT?
30. can a stacked PR enter the V5 merge transaction, or can stack membership be
    created/restructured inside the normal guarantee envelope?
31. can an unresolved V4 TEST_REQUIRED disappear at V4 -> V5 cut-over?
32. after FAILURE/CANCEL, can a retry occur without a fresh durable token, can
    one token authorize two PREPAREs, or can crash reconstruction forget whether
    the token was consumed?
33. after `v5Retired`, can V5-only seen-head history still block ordinary V4
    HeadChange/RefreshBase?

Also search outside these known traces. A reviewer that only checks the listed
fixes has not completed an adversarial review.

## Required procedure

1. Reconstruct Draft PR #191 and record exact current HEAD.
2. If HEAD differs from the supplied candidate SHA, stop: it is a new candidate.
3. Read all three canonical design files completely.
4. Inspect all seventeen finite configs, MC module and `run_tlc.sh`.
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
