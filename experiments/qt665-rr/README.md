# #665 post-READY: temporal memory investigation (NON-GATE)

## Claim and current boundary

This independent branch investigates the **first memory invariant violation**
preceding the historical `closeEvent -> console -> appendHtml -> QRawFont -> malloc`
SIGSEGV. It neither repeats nor repairs the already-proven pre-READY progress
dialog UAF. #637/ODE remain separate. No product files or existing experiment
branches are modified. No Ready, merge, publication or root-cause claim.

Initial reconstruction: main `c0cb8c1873d48b26a0f67976c65fa92ca5d54f52`,
all 69 preexisting #665 comments through `6503098926`, no PR matching `rr`.
Existing signal-context and self-pipe trials did **not** prove that SIGTERM
caused the historical allocator crash. Do not rerun them as root-cause evidence.

## Executed feasibility, 2026-11-01

`evidence/work-mode-host.json` is the unedited output of `preflight.py` on the
current execution host (Ubuntu 24.04 userspace, Linux 6.18.57, Intel Xeon 8573C,
KVM). Raw x86 `perf_event_open` probes: hardware branches (type 0/config 4) and
Intel conditional branches (type 4/config 0x1c4) return **ENOENT**; software
CPU clock opens successfully. No CPU PMU in sysfs. Child PTRACE_TRACEME returns
**EPERM**. No effective capabilities; seccomp active. Neither sysfs nor the errno
alone locates the hypervisor/security-policy implementation responsible.

Upstream rr **5.10.0**, source tag commit
`7c5a08e538e7999bf996f60a8c206e122f4b8050`, official x86_64 tarball SHA256
`55d9175d88139f775aca36981c55c2f3bca227434217750fc3ee2619501e269b`;
extracted rr executable SHA256
`4c1cdbaa38500eb0f95e6fa2e4317bc41a4188b09542b562b30256512babc6f6`.
`rr --version` succeeds; actual `rr record -o <private-dir>/true-trace /bin/true`
aborts with `PTRACE_SEIZE failed ... EPERM`, exit signal SIGABRT (-6).
This is an **rr feasibility failure**, not a Webots SIGSEGV.
No trace replay or Webots execution occurred here.

**Conclusion: RR_INCOMPATIBLE on this specific Work Mode host.** Hardware
counters and ptrace independently block this path. Installing GDB, changing Qt,
or compiling Webots cannot repair those measured prerequisites.

The single `NON-GATE 665 rr host feasibility` workflow tests an independent
GitHub-hosted Ubuntu 24.04 machine using the same hash-pinned rr. Its green job
means collection completed; inspect `host.json.status` and stderr for the
scientific verdict. A `/bin/true` smoke success is **not** Webots feasibility.
No Webots download or build occurs in this gate. Evidence updates don't trigger
another run (only the workflow file is in the push path filter).

## Reproduce host gate

Download the exact upstream tarball, check the hash above, extract with
`tar --no-same-owner -xzf rr-5.10.0-Linux-x86_64.tar.gz`, add its `bin` to PATH.
No privileged settings are changed by this script.

```sh
python3 experiments/qt665-rr/preflight.py --out /absolute/new/private/rr-host
```

Output directory must not exist. `host.json` retains exact commands, errno,
rr output, CPU, kernel and probe identity. It does not dump environment secrets,
process memory, or an rr trace into a public artifact. An rr trace may contain
private file contents and memory: **keep all real application traces private**.

## Next experiment, after a successful host gate

Do not launch a blind campaign. Use one isolated Linux host with actual PMU
support, permission for child ptrace and perf, a pinned R2025a installation,
Xvfb and software Mesa. Verify `rr record` AND `rr replay -a` on the smoke
subject first. Keep graphics servers outside rr; record the real Webots
process tree. NVIDIA GPU execution is not an acceptable replay dependency.

Next deliverable in this branch: a recorder around the unchanged
`gp-u-v1-L2000-s0-unavailable` trial with exact ELF/Qt/world/events manifests,
and replay equality checks. The historical original ELF must hash to
`1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb`;
Webots source/assets remain
`c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`.

No recorded crash => CRASH_NOT_REPRODUCED. Only a successful replay of the real
Webots events, signal delivery and termination qualifies RR_RECORDING_VALID.
An observed invalid pointer requires reverse watchpoint/lifetime evidence;
the last instruction in malloc is not the first invalidating write.

Source references: [rr 5.10.0](https://github.com/rr-debugger/rr/tree/7c5a08e538e7999bf996f60a8c206e122f4b8050),
[#665](https://github.com/djibian/webeeblocks/issues/665),
[historical post-READY core](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6476654533),
[signal-context proof and its limits](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6498866861).
