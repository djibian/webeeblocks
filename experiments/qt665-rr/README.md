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

The temporary `NON-GATE 665 rr host feasibility` workflow tested an independent
GitHub-hosted Ubuntu 24.04 machine using the same hash-pinned rr. Ordinary-user
and sudo measurements both failed; the latter removed the permission mask and
proved hardware counters unavailable. See **RESULTS.md** for runs and ZIP
identities. Green jobs mean collection completed, not scientific success.
The concluded workflow is now archived as `host-feasibility.workflow.yml`,
outside the active workflow directory; the canonical contract was not weakened.

## Reproduce host gate

Download the exact upstream tarball, check the hash above, extract with
`tar --no-same-owner -xzf rr-5.10.0-Linux-x86_64.tar.gz`, add its `bin` to PATH.
No privileged settings are changed by this script.

```sh
python3 experiments/qt665-rr/preflight.py --out /absolute/new/private/rr-host
```

Output directory must not exist. `host.json` retains exact commands, errno,
rr output, CPU, kernel and probe identity. Synthetic `/bin/true` incomplete trace
fragments were collected in the Actions artifact. An application rr trace may
contain private file contents and memory: **keep all real application traces
private**. None was generated/uploaded here.

## Next experiment, after a successful host gate

Do not launch a blind campaign. Use one isolated Linux host with actual PMU
support, permission for child ptrace and perf, a pinned R2025a installation,
Xvfb and software Mesa. Verify `rr record` AND `rr replay -a` on the smoke
subject first. Keep graphics servers outside rr; record the real Webots
process tree. NVIDIA GPU execution is not an acceptable replay dependency.

`record_trial.py` prepares a recorder around the unchanged
`gp-u-v1-L2000-s0-unavailable` trial with ELF/Qt/world/events manifests,
and replay equality checks. **Not yet exercised on a native-capable host.**
The historical original ELF must hash to
`1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb`;
Webots source/assets remain
`c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`.

No recorded crash => CRASH_NOT_REPRODUCED. Only a successful replay of the real
Webots events, signal delivery and termination qualifies RR_RECORDING_VALID.
An observed invalid pointer requires reverse watchpoint/lifetime evidence;
the last instruction in malloc is not the first invalidating write.

### Prepared host commands (not executed here)

Use a **fresh isolated checkout** of this experimental branch on the adapted
host. Install rr from the checked tarball above, GDB, Python >=3.10,
Node >=22/npm, Xvfb, make and the ordinary R2025a
SDK/Qt/X11/Mesa runtime dependencies. No GPU rendering. Install the original
Webots R2025a distribution with its upstream assets, not a #701/self-pipe image.
The recorder refuses the wrong ELF/Qt hashes. All three Qt hashes are in its
source. Keep sufficient private disk space for the process-tree trace; no
size/time estimate is qualified on these unsupported hosts.

```sh
# Run from the isolated repository checkout. The private root must be new.
export WEBOTS_HOME=/usr/local/webots
capture_root=$(mktemp -d /var/tmp/wbb665-rr-XXXXXXXX)
chmod 700 "$capture_root"
python3 experiments/qt665-rr/preflight.py --out "$capture_root/gate"
```

**Inspect the gate. Stop unless `RR_SMOKE_RECORD_REPLAY_VALID`.** Resolve actual
permission/PMU failures with the host administrator; neither this protocol nor
the recorder modifies system security settings. A virtual CPU's brand/model
alone cannot establish PMU support. Only after that successful gate prepare the
ordinary generated runtime assets (network allowed only during preparation):

```sh
bash tools/prepare_runtime_v2.sh
python3 experiments/qt665-rr/record_trial.py \
  --webots-home "$WEBOTS_HOME" \
  --host-report "$capture_root/gate/host.json" \
  --out "$capture_root/native"
```

The recorder uses the **existing native harness command**:

```sh
rr record -o "$capture_root/native/trace" \
  python3 -u tools/ci/run_grand_prix_u_prototype.py \
  --native --suite unavailable --seed 0 --side 2.0
```

It records the complete harness process tree, including Webots, controllers,
Node and the disposable Xvfb. Unlike inserting rr into the owned Webots process
group, this leaves the parent recorder outside the groups receiving the normal
teardown SIGTERM. This topology is a **design to qualify**, not an executed
Webots replay result. It also captures preparation subprocesses launched by
the unchanged harness; recording only `webots-bin` would require a separately
qualified launch/teardown adapter. No readiness or cleanup deadline is enlarged
for recording. A timing failure remains a failure, with evidence retained.
rr's scheduling (including serialization of recorded threads) and this
read-only sampling observer can change which race is reached. Replay fidelity
is a property of the **recorded execution**, not proof of identical timing to
the historical crash. Non-reproduction under rr cannot refute that crash.

The recorder then invokes the following, only for a complete trace:

```sh
rr pack "$capture_root/native/trace"
rr replay -a "$capture_root/native/trace"
rr dump -e "$capture_root/native/trace"
rr dump -p "$capture_root/native/trace"
```

These outputs and application stdout/stderr go into private files. The returned
status deliberately grants no automatic native replay verdict. Inspect native
PID/exec/task identity, actual loaded Qt/libc/Mesa maps, READY, events.jsonl,
the negative result, SIGTERM delivery and final process state. Compare record
and replay output and confirm there is no divergence or trace incompleteness.
`SHA256.json` covers the retained private files including packed trace payloads;
the native harness keeps its own oracle and evidence seals. Inspect mmap
records for files missed by the sampling observer, which cannot prove absence
of short-lived mappings. Hashes of files seen through `/proc` are associated
with the maps' device/inode, not merely their pathnames.

If a native fault is captured, identify its actual recorded PID in the task
dump, then use `rr replay -p <recorded-native-PID> -e <trace-directory>`.
In GDB: `handle SIGSEGV stop print pass`, `thread apply all bt`, `info registers`,
`x/i $pc`, `when`. Identify a specific corrupted word/object first. Set a
hardware watchpoint on that word and `reverse-continue` to its last writer;
then distinguish a legitimate free/reallocation from a stale access and
reconstruct the object's allocation generation, not only its address.
Use `reverse-stepi` around the actual invalidating instruction and `when` to
record its exact rr event. For signal causality also locate the SIGTERM frame
and interrupted PC, and show the first violating store predates the later
malloc fault. Do not start with breakpoints on every allocator operation.

If rr remains unavailable, the **single** proposed fallback is
[`GDB_DISCRIMINATOR.md`](GDB_DISCRIMINATOR.md). No other campaign is prescribed.

Source references: [rr 5.10.0](https://github.com/rr-debugger/rr/tree/7c5a08e538e7999bf996f60a8c206e122f4b8050),
[#665](https://github.com/djibian/webeeblocks/issues/665),
[historical post-READY core](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6476654533),
[signal-context proof and its limits](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6498866861).
