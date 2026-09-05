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

While at least one V5 epoch is required, the **merge effect itself belongs to
the serialized Publisher Authority Plane**. Controllers may make cognitive
integration proposals, but they do not independently issue the GitHub merge
effect. Consequently a Gate FAILURE/trunk block that linearizes first is
observed before any later normal V5 merge effect.

Strict-base freshness is part of candidate admissibility:

- a successful merge makes every remaining open PR base-stale atomically in the
  abstraction;
- a concrete base refresh must create a distinct SHA incorporating the current
  protected base;
- ordinary `HeadChange` / `RefreshBase` cannot select an exact Head already
  present in proposal/terminal/merged authority history
  (`AuthoritySeenHeads`);
- the concrete implementation must verify that the refreshed SHA is the newly
  current-base candidate, not merely an old unmerged SHA.

Thus previously authorized evidence cannot be recycled after the base advances.

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
    -> poisoned          // Gate FAILURE linearization / reassertion
    -> poisonCommitted
```

The safety relations remain:

```text
poisoned ⊆ poisonPrepared
poisonCommitted ⊆ poisoned
```

Once a physical duplicate is observed, its PREPARE is durable knowledge.
`KnownDuplicatePairs` therefore contains both currently visible duplicates and
durably PREPAREd duplicate faults. Until poison COMMIT, the affected exact Head
is fail-closed for positive authority in every epoch.

After PREPARE, the Publisher may conservatively reassert Gate FAILURE even when
the original Check Runs are no longer observable because of retention loss.
The durable PREPARE, not the mutable Check surface, is the recovery basis.

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

`proposalPresent` represents the protocol-visible canonical proposal identity
and payload. A raw mutable GitHub comment before protocol observation is not yet
Authority Plane state; concrete implementation must durably ingest/canonicalize
the proposal at this boundary.

For a captured proposal whose actor is the configured trusted cognitive
principal and whose kind is blocking-negative, later mutation/corruption of the
mutable GitHub projection **does not withdraw the negative authority input**.
V5-0 has no implicit withdrawal-by-edit operation.

Therefore:

- observed trusted negative -> blocks new SUCCESS even before PREPARE;
- PREPARE -> continues to block its exact rejection Head independently of
  `Applies`;
- withdrawal/no-longer-applicable must be a separate explicit authoritative
  operation, not an edit of the source projection.

PREPARE still does not retroactively erase an already-linearized fresh SUCCESS.
The merge/failure ordering is instead serialized by the Publisher while V5 is
required; P22 defines the late-refutation consequence when merge linearizes
first.

## P7 — Cross-epoch authority memory

Governance succession does not erase authority history:

- terminal Heads survive epoch changes;
- authoritative findings survive epoch changes;
- GO proposals are bound to their proposal epoch;
- an unapplied disposition proposal may be applied only while its
  `ProposalEpoch` is the active, required epoch;
- a disposition already authoritatively applied in its epoch remains durable
  history;
- the active epoch cannot advance while trusted negative authority is
  unprepared/pending/uncommitted;
- the active epoch cannot advance while a detected duplicate has not at least
  entered durable poison PREPARE, nor while poison is pending/uncommitted;
- an unreconciled duplicate Head is blocked from positive authority across
  epochs;
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
- every known duplicate is reconciled by committed poison authority;
- V5 active/corrupted review projections are cleared;
- every authoritative V5 finding is projected into V4-compatible durable state;
- every V5 terminal Head is projected into V4-compatible durable state;
- every live checkpoint is projected into V4-compatible durable state;
- any V5 trunk-health block is projected into V4-compatible state.

`RemoveV5Requirements` then marks `v5Retired = TRUE`.

After retirement:

- `PublisherStep` is disabled;
- no new V5 proposal can be published into the modeled authority protocol;
- V5 checkpoint evidence cannot mutate restored V4 eligibility;
- ordinary future human/checkpoint decisions belong to V4 or to a later
  governance epoch outside this retired V5 instance.

This is an intentional assurance downgrade to the known V4 operational
baseline.

## P16 — Publisher reconstruction to quiescence

Under a stable environment and finite protocol work, Publisher transitions are
intended to be finite and progress-making. Reconciliation reconstructs durable
state after each effect until quiescence.

While V5 is required, the Publisher also owns the normal **merge effect**.
Merge is not task scheduling: Controllers still discover and perform product
work; the Publisher only serializes the irreversible authority/integration
effect together with Gate publication, negative linearization and poison.

When no V5 epoch is required, merge belongs to the V4 environment again.

Duplicate poison does not wait for physical duplicate deletion; its finite
progress target is durable poison COMMIT.

`WF_vars(PublisherStep)` remains an explicit abstract liveness assumption.
Finite safety TLC domains do not prove it.

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
- `Duplicate` — two-epoch physical duplicate + trusted NO_GO + poison
  reconciliation, including unprepared-poison succession attacks and Check
  projection loss;
- `PendingHead` — PREPARE remains head-blocking with `Applies = {}`;
- `SharedHead` — two PRs sharing one Head cannot both merge on one base;
- `LateRefutation` — merge-wins race produces trunk-health block;
- `Checkpoint` — human PASS/FAIL negative monotonicity;
- `Migration` — V4/V5 authority projection and rollback, including a live
  projected checkpoint and attempted post-retirement V5 evidence.

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

## P22 — Late refutation has a formal trunk consequence and ordered merge boundary

The merge/failure boundary is now an Authority Plane ordering boundary.

While V5 is required:

```text
Publisher negative linearization first
-> trunkBlocked visible
-> no later normal Publisher merge

Publisher merge first
-> later negative linearization is a late refutation
-> trunkBlocked := TRUE
```

The old refinement hole in which a Controller could already have an unrelated
GitHub merge request in flight after the negative linearized is outside the
normal V5 path: Controllers do not own that merge effect.

A deliberate human-root merge outside the serialized path remains
`HumanGovernanceOverride`.

If V5 is rolled back while the trunk is blocked, the block must first be
projected to `v4ProjectedTrunkBlocked`, where V4 eligibility remains
fail-closed.

## P23 — Previously authority-seen exact Heads are not fresh candidates

`AuthoritySeenHeads` includes exact Heads that have entered proposal history,
terminal authority history, or merged history.

Ordinary `HeadChange` and `RefreshBase` cannot select such a Head as a new
candidate. In particular, a stale PR cannot become base-fresh by pointing at an
old unmerged SHA that already carries GO/Gate evidence.

Concrete base refresh must yield a distinct SHA incorporating the current base.
The abstraction intentionally forbids authority replay even more strongly than
the GitHub SHA check alone.

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
Inv_ObservedTrustedNegativeBlocksPositiveEligibility
Inv_UnreconciledDuplicateBlocksPositiveEligibility
Inv_LateRefutationBlocksV5Merge
Inv_V4ProjectedTrunkBlockBlocksMerge
Inv_NoTwoMergedPRsShareExactHead
Inv_ActiveEpochNeverRetired
Inv_V5RetiredClosesPublisher
Inv_V5RetiredClosesProposalPublication
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
21. mutate a trusted NO_GO after publication but before PREPARE; it must remain
    fail-closed until explicit authority resolves it;
22. inject a duplicate in E1 and attempt E1 -> E2 before poison PREPARE;
23. PREPARE poison, lose all Check projection evidence, then reconstruct
    FAILURE -> COMMIT from PREPARE alone;
24. pre-authorize H2, advance base, then attempt RefreshBase back to H2;
25. linearize a late NO_GO(H1) before an unrelated H2 Publisher merge;
26. retire V5 with a projected pending checkpoint, then attempt late V5 PASS;
27. root-human governance override during cut-over.
