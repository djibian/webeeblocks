# Native RESET contact diagnostic — #637

This is a **simulation-only investigation tool**, not a repair, canonical CI,
full progression proof, classroom acceptance or physical flight qualification.
It leaves production controllers, safety predicates, 5 s timeout, 250 ms stability
window, collision oracles and the existing CI suites unchanged.

The native R2025a binary and source assets can run outside Docker using external
TCP controllers. This makes targeted experiments possible in an environment
without Docker, Chrome or Unix-domain controller sockets. All nine original
robots/controllers are connected. The only expected local IPC errors concern
unavailable Unix sockets; the TCP connections and real Runtime READY are required.
Other startup/transport failures stop the experiment and retain its logs.

## Reproduce

Use Node with its built-in `WebSocket` (Node 22+), Python 3, a C/C++ toolchain,
Webots R2025a and Xvfb. `run.py` rebuilds the original Runtime in this isolated
checkout, uses a new output directory, and stops its own child processes.
For systems with restricted package installation, Xvfb and its libraries may be
extracted from distribution packages and supplied through `--xvfb` and
`LD_LIBRARY_PATH`; this does not alter simulation physics.

The official Linux release used for the retained experiment was
`https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a-x86-64.tar.bz2`.
Its measured SHA-256 was
`c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38`;
`bin/webots-bin` was
`c12c65e8680b579d0f33c34be452f100a302bdecc6d9344becf356db4a675a1a`.
These are retained byte identities, not a claim of independent release attestation.

Prepare a clean R2025a source checkout at
`c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, containing
`projects/robots/bitcraze/crazyflie`, `projects/objects/backgrounds`,
`projects/objects/floors`, `projects/appearances`, and `projects/default`.
The standalone Linux release omits some project assets: install those source
project directories in the **separate diagnostic Webots installation** as well,
so nested `webots://projects/...` dependencies resolve locally. No production
installation needs to be overwritten.

From this repository's root (replace the two installation paths):

```sh
python3 experiments/runtime-reset-contact/test_evidence.py
node --check experiments/runtime-reset-contact/probe.js
python3 experiments/runtime-reset-contact/run.py \
  --webots-home /absolute/path/to/webots \
  --assets-root /absolute/path/to/webots-r2025a-source \
  --mode baseline --output /absolute/path/to/new-baseline-output
python3 experiments/runtime-reset-contact/run.py \
  --webots-home /absolute/path/to/webots \
  --assets-root /absolute/path/to/webots-r2025a-source \
  --mode sweep --output /absolute/path/to/new-sweep-output
```

If any RESET refuses, the probe records the first refusal and stops; **do not
rerun it blindly**. Inspect the native trace, actual Runtime
`RESET_TIMEOUT_DIAGNOSTIC`, protocol logs, source/binary digests and environment.
An output directory is never silently reused or erased.

## What the modes establish

- **baseline** imports the *existing* autonomous probe's program builders and
  oracle helpers. It executes the four initial positive missions and the next
  three negative missions, through collision attempt 7 and fresh attempt 8.
  Production WWI backend and shared interpreter carry real requests over the
  Webots WebSocket transport. The passive #649 observer retains every 32 ms
  sample. This deliberately bounded reproducer does **not** replace the complete
  15-attempt canonical browser suite and does not exercise Blockly UI or `.wbb`.
- **sweep** uses a separate, explicitly **intervening** Supervisor. It injects
  four synthetic initial states inspired by measured falls/impacts, observes
  each after 0/1/4/16 simulation steps, and then requests ordinary Runtime RESET.
  The fixture changes native pose/rotation/velocity only before that request;
  it never supplies an ACK or controls the RESET stabilization logic. The
  approximate states in `cases.json` are **not exact historical replays** of
  a complete native/ODE/actuator state. Normal RESET also advances evaluator
  configurations, which remain active and logged: the 16 observations are not
  a matched causal estimate varying only one physical factor.

The first delay of zero means the injection has been issued and acknowledged by
its Supervisor, **not** that Runtime necessarily receives RESET in that same
simulation step. The trace and ready record retain the actual observations.
Node `wall_ms` is a host protocol timestamp; Supervisor `time` is simulation
observation time. Neither dates the Runtime's precise receipt or ACK internally.

## Retained observations — 19 October 2026

Source base: `main@681bf3846ea7a2b67ee7683d1b5c920c954be81b`, no tracked
production diff. `provenance.json` binds the new experiment scripts, original
program-builder/backend/interpreter/C source, rebuilt executable, world and
Webots binary by SHA-256. `sha256.json` binds all retained output files;
compressed evidence and their digests are in `evidence/`.

The native baseline completed: 4 achieved missions, the three genuine negative
outcomes, collision attempt 7 at contact `(0.752543,-2.216290,0.499372)`,
`UNSAFE_OR_TIMEOUT`, 7 successful Runtime RESET traces/ACKs and fresh attempt 8.
Its observer contains 31,297 samples from 0.032 to 1001.504 simulated seconds.
Immediately before the observed attempt-7 teleport (t=983.520), the centre was
`(0.752574,-2.270541,0.502600)`, vertical speed about `-0.10797 m/s`, angular
X velocity about `+2.15729 rad/s`, with no contact in that sample. At t=983.552
it was `(0,0,0.015)`, identity orientation, six zero native velocities. Attempt
8's new customData was observed at 983.872. These are observations, not RESET
request/ACK oracles. Its chronology differs from the canonical browser run.

The final synthetic sweep's exact results are recorded in `RESULTS.json` and its
raw evidence archive. Each accepted RESET still used the original production
pose/motion predicates, 250 ms window and 5 s deadline. The three adversarial
local evidence tests reject a completion marker alone, absent native RESET
traces, timeout/refusal, duplicated cases and stale/wrong ACKs.

**Conclusion:** these observations do not reproduce the historical scheduled
`RESET_TIMEOUT`, identify its cause, prove its disappearance or restore main
health. They establish a runnable native experimental path and finite successful
counterexamples to an unconditional RESET failure after the tested synthetic
states. Further investigation should target an actually failing full-state
trajectory; no timeout, tolerance, oracle or student strategy is relaxed here.
