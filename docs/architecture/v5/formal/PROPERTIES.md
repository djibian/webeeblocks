# WebeeBlocks V5-0 — Formal properties

These properties are the claims the reviewer should try to falsify. They are conditioned on the normal guarantee envelope (`guaranteeActive = TRUE`) and on the GitHub refinement assumptions documented in `REVIEW.md`.

## P1 — Exact-head integration

A protocol merge linearizes against the exact PR head observed at merge time. Concrete refinement target: GitHub `expected_head_sha`.

## P2 — No guard gap

During a normal migration or rollback, at least one operational guard remains active:

```text
v4Guard OR requiredEpochs != {}
```

V4 is only a known operational fallback, not an assurance-equivalent substitute for V5.

## P3 — Negative write-ahead durability

Every linearized rejection was prepared first:

```text
linearized ⊆ prepared
```

`PREPARE` contains the complete findings needed to reconstruct a crash after `Gate -> FAILURE`.

## P4 — Commit follows linearization

```text
committed ⊆ linearized
```

A `COMMIT` may not invent a rejection that never became authoritative.

## P5 — Terminal negative authority

For every `(Epoch, Head)`, once the pair is terminally failed or poisoned, no normal transition may make it protocol-positive again.

## P6 — Pending negative is fail-closed for new positive authority

An unresolved durable `PREPARE` prevents `PublishSuccess` and `SUCCESS_REVALIDATE` for any candidate to which its findings still apply.

## P7 — Cross-epoch finding memory

Changing the active/required epoch does not delete authoritative findings. A later epoch may authorize a candidate only after every inherited applicable finding has an explicit disposition.

## P8 — Trusted proposal provenance

Only proposals authored by the configured trusted cognitive principal (`djibian` in the initial deployment) may enter authority transitions. Valid-looking external proposals remain evidence only.

## P9 — Exact App Gate source

Only the dedicated Protocol App contributes to `Protocol Gate`. Homonymous checks from GitHub Actions or another App must not satisfy the V5 Gate.

## P10 — Duplicate poison

Detection of multiple Protocol-App Gate runs for the same `(Epoch, Head)` poisons the pair and eventually drives the observed authoritative projections to failure. The normal safety envelope still assumes credential isolation prevents an undetected second writer.

## P11 — Positive publication last

`PublishSuccess` requires all of the following to have been reconstructed immediately beforehand:

- governance observable and matching the epoch manifest;
- no terminal failure;
- no unresolved durable finding;
- no unresolved pending negative PREPARE;
- required human checkpoint satisfied;
- no active/corrupted blocker applicable to the candidate.

## P12 — Full SUCCESS_REVALIDATE

A stale SUCCESS can become fresh only after the complete positive derivation is repeated. There is no timestamp-only refresh transition.

## P13 — Review mutation cannot erase authority

Editing/dismissing a PR review changes only the PR-level projection. Durable negative memory remains in the Authority Ledger model.

## P14 — V4 -> V5 semantic upgrade

V4 guard cannot be removed until all still-live V4 authority has been imported and the V5 epoch guard is operational.

## P15 — V5 -> V4 semantic downgrade

V5 required guards cannot be removed until V4 is restored and verified, every durable negative `PREPARE` has drained through negative linearization, and all unresolved V5 findings/checkpoints have a V4-compatible representation. Once no V5 epoch is required, the model must not admit a new V5-only `PREPARE`.

## P16 — Publisher reconstruction to quiescence

Under a stable environment and finite protocol work, every enabled `PublisherStep` disjunct must make strict protocol progress. With that condition, a weakly-fair repeated `PublisherStep` is intended to drain all deterministic protocol transitions. This is a liveness assumption to challenge, not a GitHub theorem; an idempotently enabled publisher action is a counterexample because it can mask starvation of unrelated work.

## P17 — Human root boundary

A deliberate root-admin governance override leaves the guarantee envelope. The protocol verifies normal governance transitions but does not physically prevent the human root from overriding their ordering.

## P18 — Assurance downgrade is explicit

`V5 -> V4` restores the known V4 operational baseline and intentionally lowers assurance. The model must never imply equivalence between V4 and V5 trust guarantees.

## Required TLC invariants

At minimum the reviewer should model-check:

```text
TypeOK
Inv_NoGuardGap
Inv_LinearizedWasPrepared
Inv_CommittedWasLinearized
Inv_NoPositiveAfterTerminalFailure
Inv_NoSuccessWithUnresolvedDurableFinding
Inv_NoFreshSuccessWithPendingNegative
Inv_NoSuccessWithBlockingCheckpoint
Inv_NoSuccessWithCorruptedProjection
Inv_RequiredSuccessRequiresObservableManifest
Inv_V4RemovalRequiresImportedAuthority
Inv_V5RemovalRequiresV4Fallback
Inv_NoPendingAfterV5Removal
Inv_EpochChangeDoesNotEraseFindings
```

## High-value traces to search

1. `GO -> SUCCESS -> PREPARE(NO_GO) -> merge -> FAILURE`
2. `GO -> SUCCESS -> PREPARE -> FAILURE -> crash -> reconcile`
3. `FAILURE(E1,H) -> E2 -> SUCCESS(E2,H)` with unresolved inherited finding
4. two PRs sharing the same head, with one blocking review
5. duplicate Protocol-App Gate before and after SUCCESS
6. freshness expiry while new negative evidence appears
7. V4 -> V4+V5 -> V5 with unresolved V4 authority
8. V5 -> V5+V4 -> V4 with an unresolved PREPARE, proving requirements cannot be removed before it linearizes and is projected
9. proposal edited after PREPARE
10. review projection edited after COMMIT
11. governance observability lost after SUCCESS but before merge
12. human-root override during cut-over
13. duplicate Gate -> poison once while unrelated publisher work remains pending; prove poisoning cannot stutter forever and mask reconciliation