# WebeeBlocks V5-0 — Formal properties

These are the claims the reviewer should try to falsify.

All strong claims are conditioned on the normal guarantee envelope
(`guaranteeActive = TRUE`) and on the concrete GitHub refinement assumptions
listed in `REVIEW.md`.

The TLA+ module exposes:

- `SafetySpec = Init /\ [][Next]_vars` for invariant model checking;
- `Spec = SafetySpec /\ WF_vars(PublisherStep) /\
  WF_vars(RemoteMergeExecutionStep)` for the explicit Publisher and remote
  execution liveness assumptions.

The finite TLC domains check safety only. They do **not** prove the liveness
assumption, semantic adequacy of `Applies`, or the GitHub refinement.

## P1 — Exact-head, current-base integration

While at least one V5 epoch is required, normal integration is a recoverable
Publisher transaction around GitHub's asynchronous `direct_merge` primitive.
Controllers may propose integration, but they do not issue the merge effect.

V5-0 deliberately keeps that transaction **single-PR**. A candidate may
enter `mergePrepared` only while it targets `main` and is not a member of a
GitHub stack. Target-base and stack membership are modeled as mutable repository
state, not frozen constants. A retarget or stack mutation after PREPARE/SUBMIT
therefore remains an admissible environment race; it invalidates
`MergeIntentStillEligible` and prevents modeled remote SUCCESS. Future V5
governance must prohibit normal Controller stack creation/restructuring while
V5 merge authority is active, and the concrete substrate must detect target/
stack mutation at the execution boundary. Owner-root manual mutation remains
outside the normal guarantee envelope. This is a deliberate compression choice:
V5-0 does not model multi-PR atomic stack authority.

The lifecycle is:

```text
PREPARE exact (PR, Head, Epoch) intent
-> submit async direct_merge with exact sha
-> durably bind/recover GitHub operation UUID
-> GitHub remotely linearizes SUCCESS or FAILURE under current rules
-> Publisher observes the terminal UUID result
-> COMMIT semantic outcome
```

Submission is not merge linearization. `RemoteMergeLinearizeSuccess`
re-derives `MergeIntentStillEligible` at the modeled remote execution point.
A governance/Gate/base change after SUBMIT can therefore force remote FAILURE
rather than being silently bypassed.

The world state may contain the remote result before Publisher observation.
The outstanding barrier remains until observation and COMMIT, so later
Publisher negative authority cannot overtake an unresolved operation.

FAILURE/CANCEL writes immutable semantic history, increments the durable
terminal-attempt generation for that PR, clears current lifecycle state and
leaves the PR in durable `mergeRetryBlocked` history. Automatic retry is
disabled. A later retry requires a fresh owner-authored durable retry token
bound to the exact PR, current Head, active Epoch **and current failure
generation**. That unique token is consumed atomically by the next PREPARE and
cannot authorize another attempt. If another FAILURE/CANCEL occurs, every
unconsumed token from an earlier generation is stale and cannot authorize the
new attempt.

Strict-base freshness and exact-head replay prevention remain unchanged.

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
- human checkpoint authority is bound to `(GovernanceEpoch, Head)`; successor
  epochs require their own PASS/NA evidence when that Head requires a checkpoint;
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
evidence only: they cannot mint authority and cannot reserve a candidate Head
through `AuthoritySeenHeads`.

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

V4 authority is modeled as **live state during migration**, not as a single
startup snapshot. The cut-over protocol is:

```text
V4 producers active
-> freeze creation of new decision-relevant V4 authority work
-> drain already-started V4 checkpoint/negative workflows
-> resolve every outstanding V4 TEST_REQUIRED
-> import the final frozen V4 findings + rejected-head memory
-> require/verify healthy V5 epoch(s)
-> remove the V4 guard
```

Accordingly, V4 guard removal requires all of the following:

- V4 authority producers are frozen;
- no V4 checkpoint workflow or negative-authority workflow remains in flight;
- no unresolved decision-relevant V4 TEST_REQUIRED remains;
- the imported findings equal the final frozen V4 findings;
- the imported rejected-head memory equals the final frozen V4 rejected-head
  memory;
- at least one V5 epoch is required and currently operational;
- every required epoch is currently observable and manifest-matching.

V5-0 intentionally does not translate an already-open V4 TEST_REQUIRED into a
new V5 checkpoint identity. It must finish under V4 as PASS, FAIL or
NOT_NEEDED before the final import can complete. The model explicitly permits
the race "not present before freeze -> V4 workflow starts -> producer freeze ->
workflow publishes/drains -> final import" and the race "checkpoint blocks
cut-over -> checkpoint resolves -> cut-over resumes".

`LegacyFindings`, `LegacyRejectedHeads` and `LegacyCheckpointHeads` are
initial reconstructed V4 inputs only. `v4Findings`, `v4RejectedHeads`,
`v4CheckpointHeads`, `v4CheckpointInFlight` and
`v4NegativeInFlight` carry the live migration state. `LegacyDataImported`
compares the imported V5 projection against the **final frozen live V4
authority**, not merely against startup constants.

## P15 — V5 -> V4 semantic downgrade

V5 requirements cannot be removed until:

- V4 guard is restored and verified;
- every trusted blocking-negative proposal is PREPAREd;
- every rejection PREPARE is linearized and COMMITted;
- every poison PREPARE is linearized and COMMITted;
- every known duplicate is reconciled by committed poison authority;
- V5 active/corrupted review projections are cleared; a rejected PR may first
  be closed/abandoned and its projection retired without resolving the finding;
- every authoritative V5 finding is projected into V4-compatible durable state;
- every V5 terminal Head is projected into V4-compatible durable state;
- every live checkpoint is projected into V4-compatible durable state;
- any V5 trunk-health block is projected into V4-compatible state.

`RemoveV5Requirements` then marks `v5Retired = TRUE`.

After retirement:

- `PublisherStep` is disabled;
- no new V5 proposal can be published into the modeled authority protocol;
- V5 checkpoint evidence cannot mutate restored V4 eligibility;
- V5-only `AuthoritySeenHeads` replay memory no longer blocks ordinary
  `HeadChange` / `RefreshBase`; V4's own rejected-head/checkpoint rules own
  eligibility after retirement;
- ordinary future human/checkpoint decisions belong to V4 or to a later
  governance epoch outside this retired V5 instance.

This is an intentional assurance downgrade to the known V4 operational
baseline.

## P16 — Publisher / remote transaction reconstruction to quiescence

Under a stable finite environment and finite requested protocol work,
reconciliation is intended to be finite and progress-making.

A submitted asynchronous merge has two distinct stages:

1. GitHub reaches terminal remote SUCCESS/FAILURE;
2. Publisher observes the UUID result and commits it.

`WF_vars(RemoteMergeExecutionStep)` abstracts eventual terminal execution.
`WF_vars(PublisherStep)` covers observation/commit once the result exists.

Concrete V5-0 mandates async `direct_merge` with exact SHA. The returned UUID
must be durably recorded. If the 202/UUID response is lost, automatic
resubmission for 409/UUID recovery is allowed only inside a durably recorded
recovery window that is strictly shorter than GitHub's 24-hour result-retention
horizon (with implementation safety margin). Once that bounded window may have
expired, the Publisher must never issue another automatic PUT for the unknown
transaction; it stays fail-closed for explicit human-root recovery. A 404 or
unknown result is never interpreted as FAILURE.

A completed FAILURE/CANCEL becomes quiescent behind durable failure history
and advances the PR's durable failure generation. A fresh retry is represented
by a unique owner-authored token carrying retry identity plus exact
PR/Head/Epoch/**failure-generation** provenance. One token is consumed by at
most one PREPARE. A second failure advances the generation, so an unused sibling
token issued for the prior failure is causally stale. Repeated same-head
failures therefore require distinct fresh tokens bound to the latest terminal
attempt rather than replaying a mutable authorization bit. Retry-token
publication is closed once V5 is retired.

Finite safety TLC domains do not prove either fairness assumption.

## P17 — Human root boundary

A deliberate root-admin override leaves the guarantee envelope. V5 verifies
normal human-rooted governance transitions; it cannot physically prevent the
repository owner from overriding their order.

## P18 — Human checkpoint negative monotonicity

Checkpoint state is keyed by `(GovernanceEpoch, Head)`.

`HUMAN_FAIL` follows rejection PREPARE -> Gate FAILURE -> COMMIT.

Same-epoch, same-head positive checkpoint application cannot overwrite an
authoritative FAIL. Positive HUMAN_PASS / HUMAN_NA application is allowed only
while that epoch/head checkpoint is pending. A PASS from E1 does not authorize
E2.

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
modules with SANY, and model-checks seventeen focused finite safety domains:

- `Ordering` — trusted GO/NO_GO ordering and new-head repair;
- `EpochTerminal` — no same-head resurrection across epochs;
- `EpochRepair` — inherited finding repair plus old-epoch disposition attack;
- `Duplicate` — two-epoch physical duplicate + trusted NO_GO + poison
  reconciliation, including unprepared-poison succession attacks and Check
  projection loss;
- `PendingHead` — PREPARE remains head-blocking with `Applies = {}`;
- `SharedHead` — two PRs sharing one Head cannot both merge on one base;
- `LateRefutation` — focused merge-wins race: bootstrap V5, authorize and
  remotely merge H1 through the recoverable Publisher transaction, linearize a
  late NO_GO(H1), refresh the second PR to H3, authorize H3 and challenge the
  subsequent merge barrier. Its scenario-specific `LateRefutationNext`
  excludes orthogonal governance/rollback/review/duplicate/checkpoint actions
  already covered by other domains; it does not constrain `trunkBlocked`,
  `MergeAllowed`, merged state or negative authority;
- `Checkpoint` — human PASS/FAIL negative monotonicity;
- `Migration` — V4/V5 authority projection and rollback;
- `MergeInFlight` — focused two-epoch submitted-merge execution. Its
  scenario-specific `MergeFlightNext` preserves E1 authorization -> SUBMIT ->
  require unsatisfied E2 -> attempted remote SUCCESS/FAILURE, plus post-SUBMIT
  E1 Gate expiry, governance drift/observability loss and arrival of an
  unrelated trusted NO_GO for P2. It excludes rollback/review/duplicate/
  checkpoint/arbitrary-PR transitions covered elsewhere and does not constrain
  `MergeAllowed`, required epochs, Gate state, manifest health or remote
  outcome;
- `MergeRetry` — FAILURE/CANCEL -> clean COMMIT -> durable unique retry token
  -> one consumed PREPARE -> fresh attempt on the same PR;
- `StackExclusion` — even a fully authorized stacked PR cannot enter the
  normal V5 Publisher merge transaction;
- `LegacyCheckpointCutover` — an unresolved V4 TEST_REQUIRED keeps
  `LegacyImportComplete` false, blocks V5 positive authority and blocks V4
  guard removal;
- `RetiredReplay` — after `v5Retired`, a non-terminal Head seen only by V5
  positive/proposal history can again be selected under restored V4 semantics;
- `Abandon` — rejected work may close while durable finding authority remains;
- `CheckpointEpoch` — E1 human evidence cannot authorize E2;
- `ExternalEvidence` — external evidence cannot reserve a future candidate
  Head.

Passing them means only that no invariant counterexample exists in those finite
domains.

To prevent irrelevant cross-product explosion after the V4/topology/retry state
dimensions were made explicit, six historical domains (`Ordering`,
`EpochRepair`, `Duplicate`, `Checkpoint`, `Migration`,
`CheckpointEpoch`) use `LegacyFocusConstraint`. The constraint fixes only
the new orthogonal dimensions to their reconstructed historical projection:
target = `main`, initial stack membership, frozen legacy authority sets and no
V4 workflow in flight; it also keeps V5 merge PREPARE absent in these
non-merge-focused domains. It does **not** remove their invariants or constrain
their own epoch/checkpoint/duplicate/migration transitions. The new races are
instead exercised in dedicated domains: `StackExclusion` for mutable
target/stack topology, `LegacyCheckpointCutover` for live V4 freeze/drain
migration, and `MergeRetry` for causal retry generations. Reviewers must
inspect this decomposition and reject it if any relevant attack is lost between
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

## P22 — Late refutation has a formal trunk consequence and recoverable merge boundary

The merge/failure boundary is an Authority Plane ordering boundary even though
the remote GitHub merge effect is not locally atomic.

While V5 is required:

```text
merge PREPARE
-> submit exact-head request
-> resolve remote outcome before unrelated Publisher work

remote success
-> merge is authoritative
-> later negative linearization is a late refutation
-> trunkBlocked := TRUE

remote failure/cancel
-> merge transaction closes
-> later negative FAILURE may linearize
-> trunkBlocked visible
-> no later normal V5 merge
```

The older refinement hole in which a request could remain remotely in flight
while a later trunk block linearized is excluded by the outstanding-transaction
barrier, not by pretending the HTTP call is atomic.

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
Inv_SingleOutstandingMerge
Inv_SubmittedMergeWasPrepared
Inv_RemoteMergeOutcomeWasSubmitted
Inv_ObservedMergeOutcomeWasRemote
Inv_MergeCommitHasResolution
Inv_RemoteSuccessSatisfiedExecutionGates
Inv_IdleMergeLifecycleClean
Inv_RetryBlockDerivedFromHistory
Inv_BlockedRetryNeedsFreshToken
Inv_ConsumedRetryIsTrusted
Inv_V5PrepareExcludesStacks
Inv_V5MergeExcludesStacks
Inv_LegacyCheckpointBlocksCutover
Inv_RetiredV5DoesNotReserveCandidateMove
Inv_NoV5RetirementWithOutstandingMerge
Inv_RemoteSuccessUsesPreparedIntent
Inv_PositiveSuccessRequiresEpochCheckpoint
Inv_ExternalEvidenceDoesNotReserveCandidate
Inv_ExternalEvidencePreservesCandidateActions   // ExternalEvidence domain
Inv_V5RetirementClearsReviewProjections
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
27. root-human governance override during cut-over;
28. merge PREPARE -> submit -> lost response, then attempt unrelated negative
    linearization before authoritative remote resolution;
29. reject -> review projection -> close PR -> retire projection -> rollback
    without resolving the finding;
30. HUMAN_PASS(E1,H) -> E2 -> attempt GO/SUCCESS(E2,H) without E2 checkpoint;
31. external proposal for future H2 -> attempt legitimate RefreshBase to H2;
32. verify that no auto-merge/merge-queue/alternate credential path escapes the
    single outstanding merge transaction;
33. E1 submit -> configure/bootstrap/require E2 without E2 SUCCESS -> attempt
    remote merge linearization;
34. remote FAILURE -> observe -> COMMIT -> explicit retry authorization ->
    prepare/submit a fresh attempt on the same PR;
35. remote SUCCESS linearizes, governance changes before Publisher observation:
    preserve actual execution ordering;
36. async UUID response loss -> retry/409 recovery; never turn unknown into
    FAILURE; retention loss remains fail-closed.
