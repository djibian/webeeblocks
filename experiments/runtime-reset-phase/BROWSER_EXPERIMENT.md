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

## Acquired undelayed browser control, then bounded timing intervention

The undelayed native browser acquisition really completed on candidate
`2ffb3d440e50330373b7d06738500da4f54f108e`, run `39380546728`, job
`118488964071`. Artifact `12245069155` ZIP SHA-256
`3bba4de4a83f7957b82d5e9718159bf198b4a8b43fcc1c449c011028b25a1821`
and all 13 manifested files were verified. All 14 internal RESET records
recalculate correctly and original/instrumented C differ by the two prints.
Seventh receipt t=433.216 s, position approximately (0.75195,-2.28341,0.46856),
roll 0.29895 rad, gyro X=1.84932 rad/s; teleport-crossing GPS spike at +32 ms,
original predicates true from +64 ms, ACK +320 ms with 256 ms stable. This is a
successful real browser control, not a failure reproduction or final CI Gate.

**Next question, before acquisition:** can changing the physical phase at which
RESET is delivered after collision 7 expose persistent native motion/pose or
contradictory sensor measurements? Execute exactly three cases, delaying only
the seventh message by **1, 8 and 16 native 32 ms steps**. Stop the series on its
first refusal, preserving every started case. This is a timing intervention,
not reconstruction of missing historical scheduling. One factor is explicitly
changed, but the live host/browser timing can vary elsewhere; no fully matched
causal estimate across flights is claimed.

`defer.py` adds a small receiver wrapper in the temporary build. It forwards all
ordinary messages unchanged, holds only the seventh well-formed RESET, does not
drain any more messages while it is held, then releases that same message once
at the requested **simulation** time. The untouched RESET handler only then
starts its original five-second timer. No ACK, sensor, motor, pose or physics is
fabricated. The original C and its receiver are restored after building. This
intervention is clearly distinct from #652's output-only transform and is named
and hashed in each case's provenance. The compiled receiver test checks the
first six/eighth RESET, invalid/non-RESET messages, no early release, no message
drain while pending, exact delayed message and exactly-once delivery for all
three delays. Runtime receipt must equal its logged release time.

Predictions: persistent physical movement/pose error agreeing with false
predicates supports the physical branch; a persistent discrepancy after the
first teleport difference supports sensor/freshness. Success across these finite
phases only bounds those actual trajectories. The native traces establish which
phases were reached; neither delay values nor observer timestamps are relabeled
as historical or internal receipt evidence.

The existing Runtime job runs each `campaign.py --steps N` sequentially, uploads
`reset-phase-browser-delayN-r2025a` immediately, and only on complete success
continues to the entire original core harness without tracing/delay flags.
Every original autonomous oracle still executes in each case and in the
canonical harness. A refusal fails the job and skips later cases; its evidence
is uploaded. The primary acquisition manifest is retained alongside a wrapper
manifest containing the case configuration, timing validation and source files.
