# CI optimization: independent advisory loop

The weekly **CI Optimization (advisory)** workflow runs on Mondays at 04:37 UTC,
with an optional manual `workflow_dispatch`. It reads GitHub Actions metadata
using the job's **read-only** `actions:read` and `contents:read` token. It emits
an Actions step summary and `report.json` / `report.md` artifact retained for
90 days. It does **not** create commits, issues or PRs and cannot approve or
merge changes. The workflow has no `push` or `pull_request` trigger and is **not**
a required `CI Gate` check.

The analyzer uses a bounded 21-day sample (max 60 completed canonical `ci.yml`
runs, paginated GitHub job reads), only comparing runs with both suite job sets,
every job successful, the actual `CI Gate` successful, and all seven native
progression shard jobs successful. For **quantitative comparisons only**,
the newest eligible run anchors a cohort with the **same event type and exact
set of selected job names**: runs with extra or missing jobs cannot be pooled
into runner-minute or duration medians, even if all their own jobs passed. The
report records this cohort's reference run, event, job count, and how many runs
were eligible before filtering. Results report **actual CI Gate finish latency**
(run_started_at to completed canonical Gate job), the retained **legacy
updated_at span** (not Gate latency), and the **sum of occupied job minutes**; they are *not* GitHub billing and do not show
that all affected oracles were selected correctly. Older unsharded runs,
partial/skipped runs and differing job-set runs are listed separately but **not
pooled** into optimized medians. Each observation includes its run id / SHA and reports its exact
conclusion. Failed or canceled runs never become PASS, nor trigger blind reruns.

The report identifies (1) recurring >12-minute jobs as **long-job observations**
without a proven critical-path effect; (2) the measured cost of jobs with
historical labels for **manual active-dependency review**; (3) repeated Docker
image pull *sites* (inventory-only, never optimization candidates) without proven savings; and (4) failures to investigate
*causally*. A candidate is a **hypothesis, not permission to skip a check**. Historic Blockly and native scenarios may
still protect supported runtime behavior: naming or low cost cannot establish
that they are obsolete. Full-product semantic coverage cannot be inferred from
job counts or GitHub's `success` alone (as proved by the CI selector finding
behind #669 and #672).

## Evidence guardrails (V2)

The advisory report adds a four-field `qualification`: `verdict`, `evidence`,
`reason`, and `candidate`. `INSUFFICIENT_EVIDENCE` denotes fewer than two
distinct, complete same-trigger/job-set successful campaigns with valid Gate
and job timing. Two observations are a logical minimum for repetition, not a
statistical confidence or profitability threshold. `NO_ACTION` means that no
targeted investigation is justified **within the measured, narrow scope**,
not that no optimization exists. `EXPERIMENT_CANDIDATE` is currently reserved
for recurring failures in the same non-Gate job in at least two failed runs:
it proposes log-based investigation, not an automated A/B test or a causal
performance claim. Failed/cancelled runs remain visible outside the cohort.

Missing, malformed or reversed timing is unknown, never zero. The existing
`wall_minutes` / `wall_median_minutes` remain explicitly labelled legacy
`updated_at` spans; new `gate_elapsed_minutes` / `gate_median_minutes`
measure the real canonical Gate finish. Identical job names do not prove
identical underlying workloads, selected oracles, or causal improvement.

## Converting a suggestion into a code change

1. Establish exact `main`, current `AGENTS.md`, vision, roadmap, and affected
   native/provenance contracts. Show the existing scenario/negative/oracle list.
2. Record a reproducible baseline and suspected cause. Avoid artificial timeouts,
   warm-run-only comparisons, and self-assigned GO.
3. Propose a small independent **Draft** PR with an explicit old/new proof map,
   pinned environment identities and adverse tests for any CI selection change.
4. Keep every negative case, evidence artifact and authoritative outcome. New
   partitions must fail closed if any shard or manifest is absent or truncated.
5. Ready HEAD exact: full canonical CI, successful real `CI Gate`, **independent
   V5 GO** covering #637/#665 interactions, conditional squash merge only when
   all requirements pass. No automatic merge or alteration of scientific gates.
6. Compare several successful full-suite runs and runner-minute distributions
   with corresponding native completeness; record regressions or unresolved
   variability, preserving provenance in the PR.

Local deterministic tests: `python3 -m unittest discover -s tools/ci -p test_ci_optimization_report.py`.
To run the report in a checkout with a **read-only token**:
`GITHUB_TOKEN=... python3 tools/ci/ci_optimization_report.py --repository djibian/webeeblocks`.
