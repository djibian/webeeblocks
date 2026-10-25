# CI historical evidence and preparation audit — 2026-10-25

**Scope and authority:** read-only diagnosis against `main@629c347e0a8268bd8a034b2b38237840b6e7b367` (AGENTS V5, product vision and roadmap at this exact commit). No test, workflow, selector, image, oracle, threshold, artifact or security change is authorized by this report. PR #696 separately repairs Runtime selection; these measurements never establish correct oracle selection on their own. Trunk refutations #637 (collision/RESET), #665 (native Webots startup SIGSEGV), and the Grand Prix LAND/pedagogical findings remain open and are not reclassified.

## Experimental design and primary evidence

GitHub Actions API `GET /repos/djibian/webeeblocks/actions/runs/{id}/jobs?per_page=100`, plus canonical `ci.yml` run metadata, was read for **eight distinct successful pull_request campaigns**. Every selected campaign has the **same exact set of 43 named jobs**, all completed/success, true `CI Gate` success, seven native progression shards, and both Runtime and Webots. This matching makes the measurements descriptively comparable; differing HEADs, code/workloads within jobs, runner allocations, cache warmness and external dependency states remain uncontrolled.

- Before Chrome-cache change #689 (merged 2026-10-25 09:32 UTC): [40174882423](https://github.com/djibian/webeeblocks/actions/runs/40174882423) (`1e417418...`), [40174984364](https://github.com/djibian/webeeblocks/actions/runs/40174984364) (`f4e08aca...`), [40175117748](https://github.com/djibian/webeeblocks/actions/runs/40175117748) (`da90816e...`).
- After #689: [40184312735](https://github.com/djibian/webeeblocks/actions/runs/40184312735) (`40de0461...`), [40189397333](https://github.com/djibian/webeeblocks/actions/runs/40189397333) (`9727940b...`), [40225994196](https://github.com/djibian/webeeblocks/actions/runs/40225994196) (`9798693c...`), [40230990024](https://github.com/djibian/webeeblocks/actions/runs/40230990024) (`5d255fbf...`), [40231221291](https://github.com/djibian/webeeblocks/actions/runs/40231221291) (`efa19ed1...`).

The `Select suites` start to real `CI Gate` completion is a separate wall-clock *span proxy*, not the overall GitHub run elapsed duration; the median full run elapsed for the three before runs is **19.87 min** as already documented in PR #687. Step durations use recorded `started_at` / `completed_at`; step-level precision is limited to GitHub timestamps. Runner minutes are the sum of occupied job spans, **not billable minutes**. The historical bucket below comprises `webots-smoke` and `historical-blockly-ui` and the four jobs whose names end in `-historical`; it is **not** a claim that these tests are obsolete.

| Observable median (minutes unless noted) | Before (n=3) | After (n=5) |
|---|---:|---:|
| Select-start → true Gate-completion span | 18.27 | 15.97 |
| Sum of occupied job time | 154.03 | 157.93 |
| `parametric-blockly-obstacle` job | 3.10 | 3.63 |
| Six historical-labeled jobs, summed per run | 10.18 | 10.15 |
| 25 explicit successful Webots pull steps, summed per run | 7.63 | 7.58 |
| 14 named Blockly 13.2.1 preparation steps, summed per run | 0.80 | 0.78 |
| Five `Restore exact historical Boost support` steps, summed per run | 0.10 | 0.13 |

The pre/post changes are **observations only, not causal speedups or regressions**. In particular, the parametric job is not faster after #689 in this small sample; the structural improvement is one network download shared *within its job*, with checksum re-verification, not a demonstrated runtime reduction. A single post-run cannot supply a controlled speed claim; nor do these five runs control for code, VM/network, cache or concurrency.

## Historical guarantees that must remain covered

Current workflow and scripts: [ci-webots.yml](../.github/workflows/ci-webots.yml), [ci.yml](../.github/workflows/ci.yml) and [historical Boost action](../.github/actions/historical-boost-support/action.yml).

| Job | Independently meaningful historical obligation / oracle |
|---|---|
| `Webots suite / webots-smoke` | Historical Blockly browser oracle, sidecar protocol and generated controller smoke in genuine R2025a, with world/build/diagnostic checks. |
| `Webots suite / historical-blockly-ui` | Real Blockly sidecar UI: Save / Submit / Restore buttons; requires a built sidecar and genuine Webots. |
| `Webots suite / encoders-historical` | Exports the exact historical BoxWithEncoders Blockly program, runs offline world in R2025a and demands `WEBEEBLOCKS_CI_BOX_ENCODERS_PROGRAM_COMPLETED` after four encoder-based movement cycles. |
| `Webots suite / gyro-gps-historical` | Exact historical BoxWithGyroGPS controller and executable text-print behavior marker `WEBEEBLOCKS_CI_BOX_GYRO_GPS_BEHAVIOR_EXECUTED`. |
| `Webots suite / light-sensor-historical` | Exact historical light-sensor program and marker `WEBEEBLOCKS_CI_BOX_LIGHT_SENSOR_BEHAVIOR_EXECUTED`; world localization checks exact R2025a PROTO references and disables runtime network access. |
| `Webots suite / sensor-probing-historical` | Historical Gyro, GPS, DistanceSensor and color observation outputs, including `WEBEEBLOCKS_CI_SENSOR_PROBE_BEHAVIOR_EXECUTED` and expected sensor prefixes. |

The latter four also reject Webots `ERROR:` and Python `Traceback`, require actual generated controller startup, and preserve their diagnostic artifacts. `encoders-historical`, `gyro-gps-historical`, `light-sensor-historical`, `sensor-probing-historical` allow the existing bounded Webots 124/137 timeout outcomes at their launch layer but demand their respective behavioral witnesses subsequently. **An exit code alone is not an acceptance oracle.** Every claimed replacement must prove these exact obligations, positive and negative paths, and provenance before any retirement; no existing job is recommended for deletion here.

## Repeated setup, provenance and critical-path interpretation

- **Webots:** 25 explicitly named successful Docker image pulls in each of the eight comparable runs, median **7.63 → 7.58 cumulative runner minutes**, across independent GitHub-hosted jobs. Sharing an image across jobs is not free: each runner is isolated; caching a tarball can increase upload/download/storage and introduce mutability or provenance problems. The literal tag `cyberbotics/webots:R2025a-ubuntu22.04` alone does not pin a manifest digest. Do not replace it with an unaudited mutable cache or allow a partial image to count as a successful oracle run.
- **Blockly:** 14 named 13.2.1 asset preparations in each full campaign, median **0.80 → 0.78 cumulative runner minutes**. The separate `Prove clean-checkout product path opened Blockly 13.2.1` step is a verification, not a preparation, and is excluded. There are multiple product/runtime/Windows preparation contracts and exact-version assertions. Collapsing these via a shared unchecked archive is not justified by approximately 3 seconds per step.
- **Historical Boost:** five repeated use sites restore an existing **exact-key, SHA-verified** Jammy Boost archive; median sum **0.10 → 0.13 runner minutes**. The cache is not a proven bottleneck and the fail-closed cache-miss policy for PRs protects provenance.
- **Browsers:** #689 made one temporary SHA-checked Chrome download reusable read-only across direct/detour within one job; its digest is intra-job identity, not upstream publisher authenticity. Browser installation/runtime remains inside the scenarios, so the preceding table does not isolate all browser-preparation time. Do not extrapolate this optimization across runners.
- **Critical path:** the latest non-Gate job in the three before campaigns is `grand-prix-u-geometry` (twice) or Runtime progression shard 3 (once); in the five after campaigns, it is `grand-prix-u-geometry` (three times) or progression shard 0/3 (twice). These are *observed last finishers*, not proof of exact DAG causality. In all eight campaigns historical jobs complete before the actual Gate, so their approximately 10 summed runner-minutes are **not** 10 minutes of demonstrated avoidable wall-clock latency. Native case execution, not simple setup, is the plausible next profiling boundary.

## Decision and admissible next experiment

**Decision: retain every historical test and environment proof.** No safe runtime speed improvement is causally established by the present eight runs. The smallest useful completed increment is this preserved, source-linked obligation and measurement baseline, without modifying CI execution or creating a competing selector patch (#696).

If an execution optimization is later justified, isolate one explicitly measured preparation or one native case's safe partitioning in a separate V5 Draft PR. Record controlled cold/warm workload cohorts with identical exact job names, events, scenarios, timeouts, witnesses, negative cases, environment identities and SHA/run/attempt provenance; compare elapsed **and** runner occupation without hiding failures, and obtain independent GO on the exact Ready HEAD. Never substitute a skipped job, external-network success, synthetic Gate, older green or historical program deletion for coverage.

Reproduction: query each linked run's `/jobs?per_page=100` endpoint; verify its 43 job-name set, status, conclusion and seven shard names, compute job spans and the explicit step labels listed above, and take per-run sums followed by the median across each cohort. This is a bounded historical sample, not a continuous monitor; `tools/ci/ci_optimization_report.py` remains the non-decision weekly observatory.
