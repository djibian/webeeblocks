# WebeeBlocks V5-0 — Formal properties

These are the claims the reviewer should try to falsify.

All strong claims are conditioned on the normal guarantee envelope
(`guaranteeActive = TRUE`) and on the concrete GitHub refinement assumptions
listed in `REVIEW.md`.

The TLA+ module exposes:

- `SafetySpec = Init /\ [][Next]_vars` for invariant model checking;
- `Spec = SafetySpec /\ WF_vars(PublisherStep)` for the additional liveness
  assumption.

The finite TLC domains check safety only. They do **not** prove the liveness
assumption, semantic adequacy of `Applies`, or the GitHub refinement.

## P1 — Exact-head, current-base integration

A protocol merge linearizes against the exact current PR head. Concrete
refinement target: GitHub `expected_head_sha`.

Strict-base freshness is part of candidate admissibility:

- a successful merge makes every remaining open PR base-stale atomically in the
  abstraction;
- refreshing a stale PR creates a distinct `Head`;
- neither `RefreshBase` nor ordinary `HeadChange` may select an exact Head
  that has already been integrated.

Thus two PRs that initially share one exact Head cannot both integrate against
the same abstract base generation.

## P2 — No guard gap

During normal cut-over or rollback:

```text
v4Guard OR requiredEpochs != {}
```

V4 is the known operational fallback, not an assurance-equivalent substitute
for V5.

## P3 — Rejection write-ahead durability

Every authoritative rejection linearization was PREPAREd first:

```text
linearized ⊆ prepared
```

Every rejection COMMIT follows linearization:

```text
committed ⊆ linearized
```

PREPARE contains the durable evidence needed to reconstruct a crash after Gate
FAILURE but before COMMIT.

## P4 — Duplicate poison is durable authority

Duplicate recovery has its own append-only authority lifecycle:

```text
poisonPrepared
    -> poisoned          // Gate FAILURE linearization
    -> poisonCommitted
```

The safety relations are:

```text
poisoned ⊆ poisonPrepared
poisonCommitted ⊆ poisoned
```

A mutable or eventually-retained-out Check Run is an enforcement projection,
not the permanent source of poison history.

## P5 — Rejected or poisoned HEAD is globally terminal

Once an authoritative rejection has linearized for H, or duplicate poison has
linearized for H, that exact Git commit is terminal across every
GovernanceEpoch:

```text
HeadTerminal(H)
=> no UniqueFreshSuccess(E,H) for any E
```

Repair requires a distinct Head.

## P6 — Durable negative input is fail-closed for new positive publication

A trusted blocking-negative proposal already visible in durable state prevents
new `PublishSuccess` / `SUCCESS_REVALIDATE` for its Head even before
PREPARE.

After PREPARE, the **pending rejection itself** continues to block its exact
`RejectionHead`, independently of whether any finding currently satisfies
`Applies(f,H)`:

```text
PendingRejectionsForHead(H) != {}
=> not PositiveEligible(E,H)
```

`Applies` governs semantic inheritance to other candidate Heads; it never
weakens the prepared head-level NO_GO barrier.

PREPARE does **not** retroactively revoke an already-linearized fresh SUCCESS.
Until Gate FAILURE linearizes, a concurrent merge may win. That boundary is
deliberate; P22 defines the required consequence if the refutation linearizes
after the merge.

## P7 — Cross-epoch authority memory

Governance succession does not erase authority history:

- terminal Heads survive epoch changes;
- authoritative findings survive epoch changes;
- GO proposals are bound to their proposal epoch;
- an unapplied disposition proposal may be applied only while its
  `ProposalEpoch` is the active, required epoch;
- a disposition already authoritatively applied in its epoch remains durable
  history;
- the active epoch cannot advance while its rejection/poison authority work is
  unprepared, pending or uncommitted;
- leaving E1 permanently puts E1 in `retiredEpochs`;
- a retired epoch can never become required or active again.

## P8 — Trusted proposal provenance

Only the configured trusted cognitive principal (`djibian` initially) may feed
V5 authority transitions. External valid-looking comments/reviews remain
evidence only.

## P9 — Exact Protocol App Gate source

Only the dedicated Protocol App may satisfy the required V5 Protocol Gate.
Homonymous GitHub Actions or other-App checks do not count.

This is a refinement obligation; the abstract model assumes it.

## P10 — Duplicate physical state and reconciliation are distinct

A physical duplicate is:

```text
gateCount[(E,H)] > 1
```

Physical duplicates may remain forever. V5 does **not** require Check Run
deletion or count normalization.

A duplicate becomes governance-reconciled only after durable poison COMMIT:

```text
UnreconciledDuplicatePairs
= DuplicatePairs \ poisonCommitted
```

Rollback requires no unreconciled duplicate and no incomplete poison lifecycle.

A pending ordinary NO_GO on an already-poisoned pair may still linearize and
COMMIT without requiring the physical Gate count to return to one.

## P11 — Positive authority is published last

Immediately before positive publication/revalidation:

- E is active and required;
- legacy V4 authority import is complete;
- governance is currently observable and matches its manifest;
- H is not terminal;
- no unprepared trusted blocking-negative proposal exists for H;
- no pending rejection targets H;
- no unresolved applicable durable/pending finding remains;
- required human checkpoint evidence permits H;
- no corrupted/blocking review projection applies.

## P12 — SUCCESS_REVALIDATE is full re-derivation

A stale SUCCESS becomes fresh only after recomputing the entire positive
eligibility predicate. There is no timestamp-only refresh.

## P13 — Review mutation cannot erase authority

REQUEST_CHANGES is only a PR-level projection of already durable negative
authority. Editing/dismissing the review cannot erase Ledger findings,
terminal-head memory, poison authority or trunk-health state.

Blocking review semantics are modeled as shared across open PRs that point to
the exact same Head; this remains a GitHub refinement obligation.

## P14 — V4 -> V5 semantic upgrade

V4 guard cannot be removed until:

- all legacy findings are imported;
- all legacy rejected-head memory is imported;
- at least one V5 epoch is required and currently operational;
- every required epoch is currently observable and manifest-matching.

No V5 positive authority may be published before legacy import is complete.

## P15 — V5 -> V4 semantic downgrade

V5 requirements cannot be removed until:

- V4 guard is restored and verified;
- every trusted blocking-negative proposal is PREPAREd;
- every rejection PREPARE is linearized and COMMITted;
- every poison PREPARE is linearized and COMMITted;
- every physical duplicate is reconciled by committed poison authority;
- V5 active/corrupted review projections are cleared;
- every authoritative V5 finding is projected into V4-compatible durable state;
- every V5 terminal Head is projected into V4-compatible durable state;
- every live checkpoint is projected into V4-compatible durable state;
- any V5 trunk-health block is projected into V4-compatible state.

`RemoveV5Requirements` then marks `v5Retired = TRUE`. The same V5 protocol
instance cannot be required again.

This is an intentional assurance downgrade to the known V4 operational
baseline.

## P16 — Publisher reconstruction to quiescence

Under a stable environment and finite protocol work, Publisher transitions are
intended to be finite and progress-making. Reconciliation reconstructs durable
state after each effect until quiescence.

Duplicate poison does not wait for physical duplicate deletion; its finite
progress target is durable poison COMMIT.

`WF_vars(PublisherStep)` remains an explicit abstract liveness assumption.
Finite safety TLC domains do not prove it. Reviewers should still search for
self-reenabling/oscillating Publisher transitions or starvation between
reconciliation classes.

## P17 — Human root boundary

A deliberate root-admin override leaves the guarantee envelope. V5 verifies
normal human-rooted governance transitions; it cannot physically prevent the
repository owner from overriding their order.

## P18 — Human checkpoint negative monotonicity

`HUMAN_FAIL` follows rejection PREPARE -> Gate FAILURE -> COMMIT.

Same-head positive checkpoint application cannot overwrite an authoritative
FAIL. Positive HUMAN_PASS / HUMAN_NA application is allowed only while the
checkpoint is pending.

After downgrade V4 enforces only checkpoint Heads explicitly projected into
V4-compatible state.

## P19 — Governance health is current, not sticky

If a required epoch is unobservable or manifest-mismatched,
`RequiredGatesOK` is false.

Observability loss or governance drift removes the epoch from
`operationalEpochs`.

`AdvanceEpoch` and V4 guard removal require required epochs to be currently:

```text
operational
AND observable
AND manifest-matching
```

A transient observability loss may be re-verified only while the manifest still
matches. Observed drift cannot be repaired in place.

## P20 — Bounded safety model checking is reproducible

`run_tlc.sh` verifies a pinned TLA+ 1.7.4 `tla2tools.jar` SHA-256, parses the
modules with SANY, and model-checks nine focused finite safety domains:

- `Ordering` — trusted GO/NO_GO ordering and new-head repair;
- `EpochTerminal` — no same-head resurrection across epochs;
- `EpochRepair` — inherited finding repair plus old-epoch disposition attack;
- `Duplicate` — physical duplicate + trusted NO_GO + poison reconciliation;
- `PendingHead` — PREPARE remains head-blocking with `Applies = {}`;
- `SharedHead` — two PRs sharing one Head cannot both merge on one base;
- `LateRefutation` — merge-wins race produces trunk-health block;
- `Checkpoint` — human PASS/FAIL negative monotonicity;
- `Migration` — V4/V5 authority projection and rollback.

Passing them means only that no invariant counterexample exists in those finite
domains.

During authoring a temporary branch-only Actions workflow may invoke the runner.
It is not part of V5 and must be removed before freezing a V4-governed review
candidate.

## P21 — Authority finding history is independently monotone

`authorityFindingHistory` is append-only state populated at negative
linearization.

The model requires:

```text
AuthorityFindings = authorityFindingHistory
```

Unlike the previous tautological invariant, the two sides are maintained by
different state representation: one is derived from linearized rejections and
one is cumulative authority history.

## P22 — Late refutation has a formal trunk consequence

The deliberate race boundary remains:

```text
merge linearizes first
-> later Gate FAILURE is a late refutation
```

But a late refutation is not inert.

If rejection FAILURE or duplicate poison linearizes for an already integrated
Head:

```text
trunkBlocked := TRUE
```

While V5 is required, ordinary V5 merge eligibility is then false for every PR.

If V5 is rolled back while the trunk is blocked, the block must first be
projected to `v4ProjectedTrunkBlocked`, where V4 merge eligibility remains
fail-closed.

Repair/revert/fix-forward and explicit clearing of a known-bad trunk are
intentionally outside V5-0 autonomous authority and remain a V4/human-rooted
recovery obligation.

## P23 — Previously integrated exact Heads are not fresh candidates

After a successful merge, the exact integrated Head belongs to `MergedHeads`.
Ordinary `HeadChange` and `RefreshBase` cannot select a `MergedHead` as a
new current-base candidate.

This is a refinement restriction: replaying an old integrated commit while
claiming current-base freshness is not a normal strict-protection path.

## Required TLC invariants

Every finite safety configuration checks at least:

```text
TypeOK
Inv_NoGuardGap
Inv_LinearizedWasPrepared
Inv_CommittedWasLinearized
Inv_PoisonLinearizedWasPrepared
Inv_PoisonCommittedWasLinearized
Inv_NoPositiveAfterTerminalFailure
Inv_MergeNeverUsesTerminalHead
Inv_MergeHasNoUnresolvedDurableFinding
Inv_MergeRequiresCheckpoint
Inv_V4ProjectedCheckpointBlocksMerge
Inv_MergeHasNoCorruptedProjection
Inv_MergeRequiresObservableManifest
Inv_V4RemovalRequiresImportedAuthority
Inv_V5RemovalRequiresV4Fallback
Inv_V4ProjectionPreservesTerminalHeads
Inv_NoPendingAfterV5Removal
Inv_EpochChangeDoesNotEraseFindings
Inv_OperationalEpochsAreCurrentlyHealthy
Inv_PendingRejectionBlocksPositiveEligibility
Inv_LateRefutationBlocksV5Merge
Inv_V4ProjectedTrunkBlockBlocksMerge
Inv_NoTwoMergedPRsShareExactHead
Inv_ActiveEpochNeverRetired
```

## High-value traces to search

1. durable GO(H) + NO_GO(H) before Publisher processing;
2. PREPARE(H) with `Applies = {}`, then attempt new SUCCESS(H);
3. existing SUCCESS(H) -> NO_GO -> PREPARE -> merge versus Gate FAILURE;
4. crash after rejection PREPARE, FAILURE and before/after COMMIT;
5. duplicate check count remains >1 permanently through poison COMMIT + rollback;
6. trusted NO_GO PREPARE plus duplicate poison on the same (E,H);
7. restart/retention loss of Check Runs followed by poison reconstruction;
8. FAILURE(E1,H) -> E2 -> attempt SUCCESS(E2,H);
9. E1 disposition proposal left unapplied until after E2 activation;
10. E1 -> E2 -> E1 reactivation attempt;
11. governance drift after Verify but before AdvanceEpoch;
12. governance drift after Verify but before RemoveV4Guard;
13. two open PRs sharing H, then sequential merge attempts;
14. merge H, late NO_GO(H), then attempt an unrelated later merge;
15. merge H, then RefreshBase/HeadChange attempt back to H;
16. PASS -> SUCCESS -> HUMAN_FAIL on one Head;
17. downgrade with future-applicability finding memory;
18. V5 rollback while trunkBlocked;
19. proposal/review mutation around authority transitions;
20. aggregate Publisher fairness with several reconciliation classes enabled;
21. root-human governance override during cut-over.
