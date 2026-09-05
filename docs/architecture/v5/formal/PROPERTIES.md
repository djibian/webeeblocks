# WebeeBlocks V5-0 — Formal properties

These are the claims the reviewer should try to falsify.

All strong claims are conditioned on the normal guarantee envelope
(`guaranteeActive = TRUE`) and on the concrete GitHub refinement assumptions
listed in `REVIEW.md`.

The TLA+ module exposes two specifications:

- `SafetySpec = Init /\ [][Next]_vars` for invariant model checking;
- `Spec = SafetySpec /\ WF_vars(PublisherStep)` for the additional liveness
  assumption.

The finite CI models check safety only. They do **not** prove the liveness
assumption or the GitHub refinement.

## P1 — Exact-head integration

A protocol merge linearizes against the exact PR head observed at merge time.
Concrete refinement target: GitHub `expected_head_sha`.

A protected-base refresh creates a new `Head` identity. Positive evidence for
the old head is not reusable after that refresh.

## P2 — No guard gap

During a normal migration or rollback, at least one operational guard remains:

```text
v4Guard OR requiredEpochs != {}
```

V4 is the known operational fallback, not an assurance-equivalent substitute
for V5.

## P3 — Negative write-ahead durability

Every linearized rejection was prepared first:

```text
linearized ⊆ prepared
```

`PREPARE` contains the complete findings needed to reconstruct a crash after
`Gate -> FAILURE`.

## P4 — COMMIT follows negative linearization

```text
committed ⊆ linearized
```

A Ledger `COMMIT` cannot invent a rejection that never became authoritative.

## P5 — A rejected HEAD is globally terminal

Once any authoritative rejection has linearized for `H`, or a duplicate
Protocol-App Gate has poisoned `H`, that exact Git commit is terminal across
all GovernanceEpochs:

```text
HeadTerminal(H)
=> no UniqueFreshSuccess(E,H) for any E
```

Repair requires a distinct head `H2 != H`. An epoch change cannot resurrect
the rejected commit.

## P6 — Durable negative input is fail-closed for new positive publication

A trusted blocking-negative proposal already visible in durable GitHub state
prevents a new `PublishSuccess` or `SUCCESS_REVALIDATE` for its head even
before `PREPARE).

After `PREPARE`, unresolved pending findings continue to prevent new positive
publication.

This does **not** retroactively revoke an already-linearized SUCCESS. Until
`Gate -> FAILURE` linearizes the negative, a concurrent merge may win and is
classified as a late refutation. This boundary is deliberate and must be
challenged by the reviewer.

## P7 — Cross-epoch authority memory

Governance succession does not erase decision history:

- findings survive epoch changes;
- terminal heads survive epoch changes;
- GO proposals are bound to their proposal epoch;
- positive Gate publication is allowed only for the active, required epoch;
- the active epoch cannot advance while its negative authority work is
  unprepared, pending or uncommitted.

A temporary loss of governance observability may be restored only if the
manifest still matches. An observed governance drift cannot be repaired in
place; it requires a new epoch.

## P8 — Trusted proposal provenance

Only proposals authored by the configured trusted cognitive principal
(`djibian` in the initial deployment) may enter V5 authority transitions.
Valid-looking external proposals remain evidence only.

## P9 — Exact Protocol App Gate source

Only the dedicated Protocol App contributes to the V5 required `Protocol Gate`.
Homonymous checks from GitHub Actions or another App do not count.

This is a refinement obligation; the abstract model assumes it.

## P10 — Duplicate Protocol Gate poison

Detection of more than one Protocol-App Gate run for the same `(Epoch, Head)`
poisons the head.

Before V5 can be retired:

- every duplicate pair must have been drained/poisoned;
- no new duplicate injection is admitted after `v5Retired`.

The normal trust envelope still assumes credential isolation prevents an
undetected second Protocol-App writer.

## P11 — Positive authority is published last

`PublishSuccess(E,H)` and `SUCCESS_REVALIDATE(E,H)` require, immediately
before publication:

- `E` is the active and required epoch;
- V4 legacy authority import is complete;
- governance for `E` is observable and matches its manifest;
- `H` is not terminal;
- there is no unprepared trusted blocking-negative proposal for `H`;
- there is no unresolved durable or pending finding applicable to `H`;
- any required human checkpoint permits `H`;
- no corrupted/blocking V5 review projection prevents authority.

## P12 — SUCCESS_REVALIDATE is a full derivation

A stale SUCCESS may become fresh only after the complete positive eligibility
predicate is recomputed. There is no timestamp-only refresh.

## P13 — Review mutation cannot erase durable authority

A `REQUEST_CHANGES` review is only the PR-level projection of negative
authority. Editing/dismissing it does not remove the Authority Ledger finding or
the global terminality of its rejected head.

The model deliberately makes blocking review semantics head-shared across open
PRs that point to the exact same commit, matching the GitHub behavior that must
be rechecked in refinement.

## P14 — V4 -> V5 semantic upgrade

V4 guard cannot be removed until:

- all legacy findings have been imported;
- all legacy rejected-head memory has been imported;
- at least one V5 epoch is required and operational.

No V5 positive authority may be published before that legacy import is
complete.

## P15 — V5 -> V4 semantic downgrade

V5 requirements cannot be removed until all of the following hold:

- V4 guard is restored and verified;
- every trusted V5 blocking-negative proposal has been prepared;
- every PREPARE has linearized;
- every linearized rejection has COMMITted;
- every duplicate Gate fault has been drained;
- V5 active/corrupted review projections are cleared;
- every authoritative V5 finding is projected into V4-compatible durable state;
- every V5 terminal head is projected into V4-compatible durable state;
- every live human checkpoint is projected into V4-compatible durable state.

`RemoveV5Requirements` then marks `v5Retired = TRUE`. The same V5 protocol
instance cannot be required again.

This is an intentional assurance downgrade to the known V4 operational
baseline.

## P16 — Publisher reconstruction to quiescence

Under a stable environment and finite protocol work, every enabled
`PublisherStep` class is intended to make finite progress, with reconstruction
after each durable effect until protocol quiescence.

`WF_vars(PublisherStep)` is only an abstract liveness assumption. The finite CI
models do not prove it. A reviewer should reject it if aggregate weak fairness
still admits starvation or if the concrete GitHub wake/reconciliation mechanism
cannot implement it.

## P17 — Human root boundary

A deliberate root-admin governance override leaves the guarantee envelope.
V5 verifies normal human-rooted governance transitions; it does not physically
prevent the repository owner from overriding their ordering.

## P18 — Human checkpoint negative monotonicity

`HUMAN_FAIL` is a blocking negative proposal. It follows the negative
PREPARE -> Gate FAILURE -> COMMIT path.

A same-head PASS cannot overwrite an authoritative FAIL. Positive
`HUMAN_PASS` / `HUMAN_NA` application is only allowed while the checkpoint
is still pending.

## P19 — Governance observability is fail-closed

If a required epoch is not observable, or its manifest no longer matches,
`RequiredGatesOK` is false and merge is blocked.

A transient observability loss can be restored only while `manifestMatches`
remains true. Once `DriftGovernance(E)` makes the manifest mismatch explicit,
the epoch cannot be reconfigured in place.

## P20 — Safety model checking is bounded and reproducible

`run_tlc.sh` is the canonical reproducible harness. It verifies a pinned
TLA+ 1.7.4 `tla2tools.jar` SHA-256, parses the modules with SANY, then
model-checks the focused finite safety scenarios.

During authoring, a **temporary branch-only Actions workflow** may call this
runner against the exact PR HEAD to obtain reproducible execution evidence.
That workflow is not part of the V5 design and must not survive into the final
V4-governed review candidate, because the active V4 workflow contract forbids
additional workflows.

The focused scenarios cover:

- trusted GO/NO_GO ordering and new-head repair;
- GovernanceEpoch succession;
- duplicate Protocol Gate poisoning;
- human checkpoint authority;
- V4/V5 semantic migration and rollback.

Passing these finite models means only that no counterexample was found in those
finite domains for the listed invariants.

## Required TLC invariants

The finite safety configurations must check at least:

```text
TypeOK
Inv_NoGuardGap
Inv_LinearizedWasPrepared
Inv_CommittedWasLinearized
Inv_NoPositiveAfterTerminalFailure
Inv_MergeNeverUsesTerminalHead
Inv_MergeHasNoUnresolvedDurableFinding
Inv_MergeRequiresCheckpoint
Inv_MergeHasNoCorruptedProjection
Inv_MergeRequiresObservableManifest
Inv_V4RemovalRequiresImportedAuthority
Inv_V5RemovalRequiresV4Fallback
Inv_V4ProjectionPreservesTerminalHeads
Inv_NoPendingAfterV5Removal
Inv_EpochChangeDoesNotEraseFindings
```

## High-value traces to search

1. durable `GO(H)` + durable `NO_GO(H)` before Publisher processing;
2. `SUCCESS(H) -> NO_GO proposal -> PREPARE -> merge vs Gate FAILURE`;
3. crash after `PREPARE`, after Gate FAILURE, and before/after COMMIT;
4. `FAILURE(E1,H) -> E2 -> attempt SUCCESS(E2,H)`;
5. old-epoch GO reused after `AdvanceEpoch`;
6. governance observability loss then recovery without drift;
7. governance drift then attempted in-place reconfiguration;
8. duplicate Gate before SUCCESS, after SUCCESS, and during rollback;
9. `PASS -> SUCCESS -> HUMAN_FAIL` on the exact same head;
10. V4 -> V4+V5 -> V5 with legacy rejected-head authority;
11. V5 -> V5+V4 -> V4 with unprepared/pending/uncommitted negative work;
12. V5 rollback with a finding that only becomes applicable to a future head;
13. V5 rollback with terminal head memory and later branch rollback to that SHA;
14. protected-base advance followed by refresh without a new head;
15. two open PRs pointing to the same head while one carries a blocking review;
16. proposal mutation before PREPARE and after authority publication;
17. review mutation before and after finding disposition;
18. aggregate Publisher fairness with multiple independent reconciliation classes;
19. human-root governance override during cut-over.
