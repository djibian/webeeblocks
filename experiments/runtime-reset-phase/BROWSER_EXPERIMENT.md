# #637 — internal-controller browser acquisition

## Question and decision rule, before acquisition

Does the original autonomous RobotWindow/browser path, with internal Webots
controllers, expose a persistent RESET predicate failure absent from the retained
external TCP acquisitions? Execute one complete existing browser campaign, retain
every attempt, stop on its first refusal. Do not rerun for a green result.

- Physical hypothesis: after the teleport-crossing GPS sample, false predicates
  agree with native motion or pose/contact deviation.
- Sensor hypothesis: after that short transient, false predicates persist while
  native pose and six velocities satisfy the corresponding physical condition.
- Success: neither hypothesis is selected for the historical timeout. Compare
  the actual receipt phase and settling with #652, then design a bounded phase
  intervention rather than claiming a repair.

The runtime source on historical 8b12e52 and current main differs only by the
already integrated diagnostic counters/timeout print. The old archive lacks
full physical/solver/actuator state and internal sensor trajectory; their exact
historical values cannot be reconstructed. Chrome's historical binary was not
pinned. The current image is pinned; Chrome remains the existing runner's
downloaded version. No historical scheduling identity is claimed.

## Execution

An initial targeted step in the existing Runtime core job sets
`WEBEEBLOCKS_RESET_PHASE_TRACE=1` and runs the unchanged complete autonomous
browser probe before the full core harness. Only
`tools/ci/run_progression_autonomous_mission.py` consumes it. It reuses exactly
the two output-only `fprintf` insertions of `instrument.py` for that probe's
Docker build, then restores the original C immediately, including on build
failure/exception. The diagnostic executable belongs only to the probe's build;
it is not a qualified production package and the generated package lock is
unchanged. Without the explicit flag the ordinary build is unchanged.

The original Docker image, world, seven evaluators, native 32 ms observer,
internal controller launch, real RobotWindow, program builders, interpreter,
WWI backend, browser waits, 1500 s budget, all 14 RESETs, positive/negative
oracles and freshness assertions remain. No synthetic physical injection,
replay ACK, delay or strategy change is introduced. The extra prints/observer
can affect host scheduling, so a successful run cannot establish absence of
intermittence. No production correction is claimed.

The immediately published `reset-phase-browser-r2025a` artifact retains the original and
instrumented C, exact candidate/image/build/executable provenance, raw internal
samples in `webots.log`, complete native JSONL, browser events, world and SHA-256
manifest. `reset-phase-summary.json` reuses #652's predicate/window recalculation;
partial/unreadable evidence stays UNPROVEN and cannot replace the raw trace or
turn a failed native run into PASS. A successful requested acquisition also
requires all 14 complete internal RESET records. No threshold is relaxed.

After success the diagnostic output directory is moved aside, then the entire
original core harness executes without the tracing flag. It therefore runs its
own ordinary autonomous oracle as before; no core property is skipped. The final
`runtime-v2-core-progression` artifact preserves both runs. On a targeted refusal
the job stays failed and uploads the failed trajectory immediately; it does not
retry that RESET or claim that the remaining core harness succeeded.

In an unrestricted Docker environment, from a clean isolated checkout:

```sh
WEBEEBLOCKS_RESET_PHASE_TRACE=1 python3 tools/ci/run_progression_autonomous_mission.py
```

The output directory is the existing runner's
`ci-artifacts/progression-autonomous-mission`. Preserve it before any further
invocation: the historical runner recreates its output directory.

## Local capability limit actually observed

In the Work execution environment, `socket.socket(AF_UNIX)` raises
`PermissionError: [Errno 1] Operation not permitted`. The downloaded real Chrome
155.0.8059.84 also aborts before opening any page:
`FATAL:chrome/browser/process_singleton_posix.cc:297 ... socket() failed:
Operation not permitted (1)`. Docker is absent. These are preparation limits,
not native RESET failures. No browser/CI success is inferred from local tests;
the acquisition must run on the normal GitHub Docker runner. TCP native trials
are possible locally but do not test internal controller scheduling.

Keep #637 open, main-health unproven and ordinary integrations suspended until
a causal correction and applicable validation exist.
