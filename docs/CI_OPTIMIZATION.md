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
progression shard jobs successful. Results report **elapsed minutes** and the
**sum of occupied job minutes**; they are *not* GitHub billing and do not show
that all affected oracles were selected correctly. Older unsharded runs and
partial/skipped runs are listed separately but **not pooled** into optimized
medians. Each observation includes its run id / SHA and reports its exact
conclusion. Failed or canceled runs never become PASS, nor trigger blind reruns.

The report identifies (1) recurring >12-minute jobs along the candidate
critical path, (2) the measured cost of jobs with historical labels for **manual
active-dependency review**, (3) repeated explicit Docker image acquisition
sites, and (4) failures to investigate *causally*. A candidate is a **hypothesis,
not permission to skip a check**. Historic Blockly and native scenarios may
still protect supported runtime behavior: naming or low cost cannot establish
that they are obsolete. Full-product semantic coverage cannot be inferred from
job counts or GitHub's `success` alone (as proved by the CI selector finding
behind #669 and #672).

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
