# WebeeBlocks development contract — V5

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
- An unknown critical precondition forbids the effect. An unknown outcome never
  proves failure or non-occurrence and permits neither a blind retry nor
  dependent cleanup. Preserve consequential uncertainty in the relevant existing
  GitHub artifact when possible; do not turn it into a global lock. Independent
  work may continue under the existing trunk-health rule.

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
- Short-lived branches are transient project references. A branch may be deleted
  when reconstruction establishes that its work is integrated, or durable
  applicable project evidence under the existing provenance and authority rules
  establishes that its remaining work is abandoned, obsolete or superseded; no
  open PR or other still-applicable work depends on it; and no unique useful
  work still requires durable preservation. Any unique useful work that remains
  relevant must be integrated or otherwise preserved by an appropriate durable
  reference before deletion.
- Branch deletion must be an atomic conditional ref deletion against the exact
  reconstructed branch tip and must fail closed if that ref has changed. A
  separate observation followed by an unconditional deletion does not satisfy
  this invariant.

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
- Immediately before a normal merge, reconstruct current main, PR HEAD/Ready
  state, target repository/branch, CI/review/findings/checkpoints and applicable
  main protections. The PR must target this repository's main, with observed
  base SHA equal to observed main; this equality does not prove strict-base
  freshness. Use the native conditional squash merge without intervening work;
  do not switch implicitly to async, stack or queue integration. After a known
  interruption, reconstruct again before acting.
- After every merge attempt, including an ambiguous transport failure,
  reconstruct PR and main. Before claiming the exact candidate integrated,
  establish the merged PR's association with that source HEAD and the merge
  commit's presence in current main history. `merged=true` alone is insufficient.
  A non-merged observation after timeout does not prove the request failed.
  These observations are not a multi-object CAS: concurrent retarget, late
  refutation or a suspended old process can still race. A crash before durable
  observation can lose the fact that a request may have been sent.
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
- A future merge queue may optimize contention but V5 does not depend on one.

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

**Pull the smallest useful complete result.** Reduce useful engaged work when
that is a strong next result, but do not give it automatic precedence over other
strong independent results. A bounded result may mean validating, integrating,
repairing, completing, closing or abandoning existing work, or completing new
independent work. Do not continue work merely because effort has already been
invested when current evidence makes it dominated, obsolete, unsafe or no longer
useful. Abandoning work never abandons a product goal or priority unless durable
product authority changes that goal or priority.

**Disperse strong useful parallel work.** Reconstruct bounded useful eligible
results from current durable project state and reason about remaining marginal
work, never presumed Controller presence, ownership, reservation or expected
continuation. The strong useful candidate set is deliberately selective: a
result does not enter it merely because it is useful or eligible. A candidate
belongs to the strong useful candidate set only when current evidence does not
make it materially weaker than the strongest currently available alternatives.
Dispersion must not promote materially weaker work merely to increase
parallelism. Candidates are bounded results, not broad issues, roadmap nodes,
subsystems or project domains. Product value, unblocking, completion value,
information gain, remaining marginal work, useful independent parallelism and
material interference may inform the set, but do not form a numerical utility
function or deterministic tie-breaking chain. Interference describes concrete coupling in the mutation or validation surface of bounded results, such as files, contracts, mutable oracles, worlds, CI machinery or interfaces whose mutation or validation would materially couple those results. When current durable project state exposes such overlap, treat it as a negative strength signal when constructing the strong useful candidate set, never as evidence of unseen Controller presence, ownership or reservation. Lesser interference is not a deterministic tie-breaker and overlap does not by itself exclude a candidate: materially stronger results and work needed to complete or repair useful existing work may still overlap, and comparable strong candidates that remain are dispersed using the execution-local dispersion key. Clear domination
requires a material reason why selecting another strong candidate now would
produce substantially less useful progress, defer an important obligation or
unblock opportunity, or perform known-unnecessary work; roadmap order, age,
recency, prior investment, branch/PR existence and small subjective value
differences do not establish it by themselves. When several strong bounded
results remain and none materially dominates, order them using stable bounded
work identifiers and an execution-local non-durable dispersion key that contains
execution-local entropy and is not deterministically derived solely from durable
project state. Generate the dispersion key once per Controller execution and
reuse that same key for the lifetime of that execution; never persist it beyond
the execution. The key carries no authority. Selection creates no affinity:
after every durable transition, reconstruct the decision from current
authoritative state without preferring later work merely because this execution
previously selected, mutated or completed related work.

**Persist knowledge, not planning scaffolding.** Materialize durable evidence,
constraints, discoveries and conclusions that can affect future decisions.
Transient paths, decompositions, controller-local rankings and internal planning
representations need no durable representation unless their conclusions can
affect a later decision.

## Controller loop

At launch, load the complete current-main contract, product vision and roadmap.
Within the same execution, already loaded complete Git content may be reused
only after its exact blob identity is revalidated against newly resolved main.
Missing content, lost context or uncertain identity requires a fresh read.
Relevant mutable GitHub facts must still be reconstructed; conversation memory
does not establish current project state.

At launch and after every durable transition:
1. resolve exact main, load or revalidate this contract/product vision/roadmap
   under the rule above and rebuild relevant PRs, exact HEADs, CI, reviews,
   issues and evidence;
2. if main is known unhealthy, contribute to restoration first unless a credible
   repair path is durably engaged and another independent action is more useful;
3. enumerate bounded useful eligible results, including validating/integrating a
   Ready PR this execution did not mutate, repairing/completing existing useful
   work, closing/abandoning dominated or obsolete work, and starting independent
   new work; remove results already covered, genuinely blocked, redundant without
   marginal value, obsolete, superseded or clearly dominated;
4. build the deliberately selective strong useful candidate set under Adaptive
   planning. If one result materially and clearly dominates the other strong
   candidates, select it; otherwise order the strong candidates using the
   execution-local dispersion key and their stable bounded work identifiers;
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

Branch cleanup may be a useful eligible action when it materially reduces
repository ambiguity or completes the abandonment of an already-engaged path.
The mere existence of a deletable branch does not create work, require
repository-wide housekeeping, or prevent Controller termination.

While carrying out or resuming an action selected by this loop whose useful
effect is independent of branch deletion, normally attempt safe retirement of a
directly associated transient branch ref as local completion when reconstruction
establishes the deletion conditions in §2. This execution-local preference
creates no standalone cleanup eligibility or durable cleanup obligation and
cannot by itself justify a retry under the existing no-blind-retry and
unknown-outcome rules.

Pending CI is not a reason to notify or globally idle. Use its latency for
independent useful work when available.

## CI and evidence

- Evaluate candidates under the contract currently integrated on main. Proposed
  authority changes do not authorize themselves. The existing independent review
  examines changes to `AGENTS.md`, `.github/workflows/**` (including additions,
  deletions, renames and both `.yml`/`.yaml`), `.github/actions/**`,
  `tools/ci/select_ci.py`, `tools/ci/check_ci_gate.py`,
  `tools/ci/test_controller_contract.py` and `tools/ci/test_workflow_contract.py`
  against the existing obligations. Changes to other scripts, tests,
  configuration or dependencies producing the evidence require the same scrutiny
  of their affected obligations; this list is not an exhaustive trust boundary.
- Technical changes preserving the authorized obligations may use the existing
  independent review without a new human approval. Changes to obligations,
  permissions, trust or human boundaries require applicable governance
  authorization; an explicit owner instruction may already provide it.
- Required CI evidence identifies the canonical `.github/workflows/ci.yml`
  pull_request workflow in the expected repository, its association with the PR,
  exact candidate HEAD, newest relevant run and effective current attempt.
  Select the newest relevant run before examining its conclusion: an older
  success cannot replace a newer pending, failed, cancelled or ambiguous run.
  Require a completed successful run and its successful final `CI Gate` job;
  a homonymous check or `CI Gate (Draft)` is not sufficient evidence. If identity,
  completeness or rerun provenance is unknown, do not infer a positive result.
  See docs/DEVELOPMENT.md for the native GitHub observations.
- CI proves only the automated properties its oracles exercise.
- A red result should strongly refute an automated property; a green result
  should strongly establish that scoped property, not full product acceptance.
- Unsupported required evidence is never fabricated into a pass.
- Missing or malformed CI selection never exempts a suite. An unselected suite
  requires explicit `"false"` selection and an observed `skipped` result.
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
