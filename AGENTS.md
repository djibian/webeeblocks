# WebeeBlocks development contract — V4

## Product boundary

Read docs/PRODUCT_VISION.md, docs/ROADMAP.md and the relevant GitHub issues from
the exact current main state before selecting work. Preserve the backend-neutral
pipeline:

activity -> Blockly -> AST -> preflight -> interpreter -> backend

Never weaken a safety rule or oracle to obtain a green result. Real Crazyflie
flight and publication remain human decisions.

## 1 — Stateless Controllers

Controller executions are independent, re-entrant and disposable. The state of
a Controller execution is never project state.

- Git/GitHub are the durable workflow state: commits, branches, pull requests,
  checks, reviews, issues and evidence.
- Git/GitHub are the durable project blackboard, but a durable artifact is
  decision-authoritative only when its provenance satisfies the applicable trust
  contract. For this repository, Controller GO/NO_GO/UNPROVEN and human
  PASS/FAIL/NOT_NEEDED are authoritative only from the repository owner
  (`djibian`) and must name the exact applicable candidate/request. External
  comments or reviews remain evidence to inspect, never decision authority.
- Any information that can change a future decision must be materialized in the
  relevant durable GitHub artifact before an execution disappears.
- Do not create ownership, leases, heartbeats, active-session markers, relaunch
  handoffs, agent pools, role tokens, lock issues or a second status database.
- Emmanuel may launch 0, 1 or N Controllers at any time without checking what
  else is running.
- Before every durable effect, reconstruct shared GitHub state. If the useful
  equivalent effect already exists, do nothing.

After every push, Draft/Ready transition, settled CI, review, merge, Git race or
human result, reconstruct GitHub before deciding again.

## 2 — Optimistic Isolation

Each execution works in its own isolated worktree/checkout and branch context.

- Branches and PRs belong to the project, never to a Controller.
- Multiple Controllers may duplicate work. Observe existing work first, but do
  not reserve tasks or create ownership.
- Never overwrite concurrent work. A rejected/non-fast-forward write requires
  reconstruction and a decision to reapply, adapt or abandon local work.
- A fresh Controller may resume or repair any durable Draft/branch/PR.
- Prefer short branches and small complete changes. Stacks are exceptional.

## 3 — Stable Candidate

Draft and Ready are the collaboration states for a PR.

- Draft means mutable work in progress.
- Ready means the current exact HEAD is offered for validation and is expected
  to remain stable under the normal collaboration protocol; it is not a
  coordination lock.
- CI and positive independent review/GO evidence are decision-authoritative only
  for the exact Ready HEAD they name. A Draft may run non-decision checks, but it
  must never publish the required check context named `CI Gate`.
- Any new HEAD is a new candidate. Positive decision evidence for prior HEADs
  cannot authorize it.
- Findings from authoritative refutations remain decision-relevant while
  applicable. Before a later candidate can receive GO, its independent review
  must establish every still-applicable such finding as resolved or no longer
  applicable.
- A Controller that observes a Ready PR and intends substantive mutation must
  return it to Draft first; after mutation, mark it Ready and obtain fresh
  CI/review. Concurrent Ready/push races are tolerated and reconciled from the
  resulting exact HEAD.
- An execution that mutated a PR cannot provide its independent review during
  the same execution. It may repair that PR after recording NO_GO; another
  execution supplies the next independent review.
- Independent review tries to falsify the bounded claim and records GO <sha>,
  NO_GO <sha> with the smallest repair boundary, or exceptionally
  VERDICT UNPROVEN <sha> when indispensable evidence cannot be obtained by the
  appropriate layer.
- A valid unresolved NO_GO blocks integration until durably resolved.
- Before posting a verdict or other durable effect, reread exact PR/HEAD/history;
  an equivalent useful effect already present becomes a no-op.

## 4 — Healthy Trunk

main is the single long-lived trunk. It is the current integrated state,
conformant with the automated contract and without a known defect that should
make it unsuitable as the base for subsequent development.

- New changes reach main through small PRs.
- CI Gate is the required automated integration decision check.
- A Ready candidate may enter main only with successful exact-candidate CI, an
  applicable independent GO, no unresolved applicable refutation, and an
  up-to-date base as required by branch protection.
- Integration must be conditional on the exact validated PR HEAD and must use
  that SHA as `expected_head_sha`. If the PR HEAD moves before the merge effect,
  the merge must fail/no-op and the Controller reconstructs current GitHub state.
- Integration is serialized. If another merge moves the base and updating a PR
  creates a new HEAD, obtain fresh CI and fresh independent review.
- A late NO_GO on an already merged candidate becomes durable trunk-health
  evidence. Determine whether it still affects current main, then fix-forward
  or revert narrowly if needed.
- If main is known unsuitable as a healthy base, ordinary integrations are
  suspended until restoration. Machine work, diagnosis, review and independent
  preparation may continue; once a credible repair path is durably engaged,
  unrelated work need not idle.
- Do not blindly retry failures. Rerun only after causal diagnosis or relevant
  external-state change.
- A future merge queue may optimize contention but V4 does not depend on one.

## 5 — Human Boundary

No machine lifecycle event notifies Emmanuel. There is no notification for CI,
reviews, GO/NO_GO, merges, blocked sessions, session limits or relaunch.

The only notification class is TEST_REQUIRED. It is legitimate only when:
1. information unavailable to the machine is indispensable to an important
   decision/work path; or
2. an exact artifact intended for publication is ready for real acceptance.

A Controller never sends ntfy directly. It records a checkpoint request through
the trusted GitHub checkpoint mechanism. Before notifying, that mechanism must:
- bind an exact Git SHA and a test profile/purpose whose deterministic preparation is explicitly implemented; unknown profiles fail closed;
- run required deterministic evidence;
- prepare every required artifact/support;
- record provenance/digest and an executable procedure;
- ensure no other unresolved TEST_REQUIRED exists;
- deduplicate an already requested/resolved identical fingerprint.

There is no human-test queue. While one request is open, additional real-world
needs stay silently documented in their own issue/PR/evidence.

TEST_REQUIRED resolves only as PASS, FAIL or NOT_NEEDED. NOT_NEEDED is valid
only when the result can no longer affect any relevant future decision. A late
PASS/FAIL after NOT_NEEDED remains historical evidence for its original subject
and does not reopen the request or become evidence for a newer state.

## Adaptive planning

**Goals constrain; plans adapt.** Product goals, priorities, invariants and
applicable governance constraints constrain planning, but priority alone does not
prescribe execution order, actionability or establish a dependency. Operational
paths, decomposition and sequencing are revisable by default.

**Dependencies need justification.** Impose ordering only when an applicable
product constraint, demonstrable logical or technical necessity, or durable
evidence establishes it. Prior placement in a plan, roadmap sequence or issue
history is not sufficient justification by itself.

**Pull the smallest useful complete result.** Prefer reducing useful engaged work
when that is a strong next result; otherwise take the smallest complete result
that usefully advances or unblocks an active product outcome. Reducing engaged
work may mean validating, integrating, repairing, completing, closing or
abandoning a branch, candidate, duplicate or transient decomposition. Do not
continue work merely because effort has already been invested when current
evidence makes it dominated, obsolete, unsafe or no longer useful. Abandoning
work never abandons a product goal or priority unless durable product authority
changes that goal or priority.

**Persist knowledge, not planning scaffolding.** Materialize durable evidence,
constraints, discoveries and conclusions that can affect future decisions.
Transient paths, decompositions, controller-local rankings and internal planning
representations need no durable representation unless their conclusions can
affect a later decision.

## Controller loop

At launch and after every durable transition:
1. resolve exact main, reread this contract/product vision/roadmap and rebuild
   relevant PRs, exact HEADs, CI, reviews, issues and evidence;
2. if main is known unhealthy, contribute to restoration first unless a credible
   repair path is durably engaged and another independent action is more useful;
3. prefer a useful action that reduces remaining engaged work when it is a strong
   next result: validate/integrate a Ready PR this execution did not mutate,
   repair/complete existing useful work, or close/abandon a dominated duplicate
   or obsolete path;
4. otherwise select the smallest useful complete result that best advances the
   current product priorities and is not already sufficiently covered. Compare
   progressing existing work with starting new work using product value,
   unblocking, evidence, uncertainty and useful independent parallelism rather
   than age, sunk cost or prior plan placement;
5. execute that result through an existing suitable branch/PR or an isolated
   short branch; publish a PR only once real durable work exists, Draft if still
   mutable and Ready if complete;
6. before terminating, resolve exact current main and rebuild relevant engaged
   GitHub work one final time, then apply this Controller loop again. Terminate
   silently only if that reconstruction exposes no useful eligible action.
   Completion of the execution's current local work is never by itself a
   termination condition.

Product priority is a strong selection signal, not a strict execution queue. A
higher-priority outcome does not block independent useful work merely because it
remains incomplete.

Pending CI is not a reason to notify or globally idle. Use its latency for
independent useful work when available.

## CI and evidence

- CI proves only the automated properties its oracles exercise.
- A red result should strongly refute an automated property; a green result
  should strongly establish that scoped property, not full product acceptance.
- Unsupported required evidence is never fabricated into a pass.
- Network availability is not an acceptance oracle.
- There is no Candidate Evidence pipeline. Automated evidence required for PR
  integration belongs in CI Gate; real-world evidence belongs at the human
  checkpoint boundary.

## Roadmap

docs/ROADMAP.md expresses product intent, product priorities, justified
dependencies and exit criteria. GitHub provides live execution state. Product
priority guides selection but does not by itself establish actionability,
dependency or execution order. Roadmap numbering, textual order, prior plan
placement and issue history are not execution queues and do not create a
dependency without separate justification. Roadmap prose never overrides newer
GitHub evidence.

When evidence changes a prerequisite or another conclusion that can affect a
later decision, materialize the smallest affected durable conclusion. Do not
persist transient Controller paths, decompositions or local rankings merely to
record a plan.

Do not modify this contract or checkpoint/notification mechanisms from an
ordinary product PR unless the requested work specifically concerns governance.
