# Results and durable restart boundary — 2026-11-01

## New experimentally supported result

`RR_INCOMPATIBLE` on the two observed execution environments. This is a
feasibility result, **not** a causal result about Webots. No new Webots run,
replay, crash, compilation, Qt patch or oracle change was performed.

| Environment | Child ptrace | Hardware branch counter | Software clock | Actual rr record |
|---|---|---|---|---|
| Work Mode KVM, Xeon 8573C | EPERM | ENOENT | opens | PTRACE_SEIZE EPERM, SIGABRT |
| Actions ordinary user, EPYC 7763/Microsoft | succeeds | EACCES | EACCES | paranoid=4 refusal, rc=1 |
| Actions sudo, EPYC 7763/Microsoft | succeeds | ENOENT | opens | hardware counter unavailable, rc=1 |

Raw Intel conditional-event config is diagnostic only on AMD; the portable
PERF_TYPE_HARDWARE/BRANCH_INSTRUCTIONS probe also returned ENOENT under sudo,
and rr selected its own CPU-specific counter and independently refused it.
No sysctl settings were changed. The sudo experiment was motivated by the
permission mask and is not an identical retry of a concluded hardware test.

## Provenance

All three actual rr invocations used upstream 5.10.0 executable SHA256
`4c1cdbaa38500eb0f95e6fa2e4317bc41a4188b09542b562b30256512babc6f6`.
Tarball SHA256 `55d9175d88139f775aca36981c55c2f3bca227434217750fc3ee2619501e269b`.

| Actions run / HEAD | Original artifact | Downloaded ZIP SHA256 |
|---|---|---|
| [41288407404](https://github.com/djibian/webeeblocks/actions/runs/41288407404), `06db8c27733c64bdf9503c4db6e6c2ed6cf7f0f7` | 13076465813, 4099 bytes, 8/8 CRC | `fc340e22f6e404097112421ef481e2d01d00350abdf731d644aba7ebdcceed31` |
| [41288515740](https://github.com/djibian/webeeblocks/actions/runs/41288515740), `bde113890fcf7b56b2635b9f9e554a75cbcbb65b` | 13076481095, 4175 bytes, 8/8 CRC | `a40778fb0f28535738831035994217e6efbc7662898abb250bac2d3cfd173deb` |

The `host.json` files were extracted unchanged from the ZIP bytes and retained
as `evidence/github-{unprivileged,privileged}-host.json`. `work-mode-host.json`
is the local probe output. Evidence file hashes are in `evidence/SHA256SUMS`.
Only `/bin/true` incomplete trace fragments were in the synthetic Actions
artifacts. No application trace or raw core was uploaded.

Green feasibility jobs mean that collection succeeded. The actual rr attempts
failed. There is **no** RR_RECORDING_VALID / CRASH_NOT_REPRODUCED claim for
Webots, because Webots was never launched by this investigation.

## Canonical CI and workflow retirement

The independent branch's temporary workflow was rejected by the existing
repository contract in canonical Draft runs **41288426638** and **41288518329**:
`test_only_approved_workflows_exist` and `test_no_post_merge_push_trigger`.
These FAIL observations remain valid for their respective HEADs. The tests
and allowlist were not weakened. After the two discriminating experiments,
the temporary workflow is removed from `.github/workflows` and retained as
`host-feasibility.workflow.yml` under this experiment for reproducibility.
Do not reinstall/relaunch it on another hosted runner without changed evidence
that makes hardware PMU availability plausible. No CI Gate/GO/Ready/merge claim.

## Prepared next step and limits

`record_trial.py` is a **prepared, not natively exercised** one-shot recorder for
a clean checkout on an adapted Linux host. It refuses this host's failed gate;
that refusal was actually exercised and produced no output directory. Python
syntax and CLI help were checked. There is no test claiming native replay.
It calls the existing unchanged native harness, verifies the historical ELF
and the three original Qt hashes, observes mapped native files, retains their
identities and runs pack/autopilot replay. A stdout match is explicitly **not**
promoted to a native scientific verdict: PID/task/maps, signals, READY, events
and termination still require review.

After the concluded experimental workflow was archived, the **39 existing
workflow-contract tests passed locally** (including their own existing fixture
subprocesses); no contract or test was edited. The three evidence JSONs parse,
their script/rr identities match, and all three retained evidence-file SHA256s
recalculate correctly. These checks do not constitute a canonical CI Gate or
independent review.

The one fallback is specified in `GDB_DISCRIMINATOR.md`, not executed. It
proposes a concrete allocator ownership invariant and a matched prebuilt pair;
it does not repeat the already-proven mere presence of malloc in SIGTERM.

**What the successor must not infer:** no first faulty memory operation has
been found; no hypothesis among Qt lifetime, previous heap corruption and
signal reentrancy has been proven or globally refuted. Pre-READY #701 and
#637/ODE remain separate. The Cancel-veto NO_GO remains applicable to general
adoption of the old self-pipe. No product repair or distribution is authorized.

**Next useful action:** obtain one actual rr-capable host and pass the existing
host gate, then one native capture; or implement the single bounded GDB
experiment on a ptrace-capable runner, respecting its target/budget conditions.
Do not rerun the three host probes or the historical #665 demonstrations.
