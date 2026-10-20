# #637 — remove the extra synchronized observer, buffer self-observations

Preregistered before native acquisition, 20 October 2026.

Facts: historical 39226828934 has one genuine autonomous attempt-7 RESET_TIMEOUT
without detailed post-reset data. #651/#652 and #653's 1/8/16-step trials pass.
The eight unchanged-browser trials 39392827296 completed 112 strict RESETs; the
single CPU=1 trial 39395235948 completed 14. Their downloaded ZIP digests and all
165/27 outer and 17/19 per-acquisition manifested files were verified locally;
1,111 + 139 post-transient comparisons show no predicate disagreement. The CPU
trial measures cpu.max=100000/100000. No cause or disappearance is established.

Historical CPU/load, Chrome identity, delivery timings, ODE and actuator state,
and consumed sensor trajectory are missing. They cannot be reconstructed.
The artificial 600-rad/s actuator fixture establishes only its own mechanism.
Successful controls refute unconditional failure under the sampled conditions;
they do not refute rare physical or observation faults in the historical FAIL.

Question: does removal of the additional synchronized observer and per-step
diagnostic output expose the failure in the original internal browser path?
The observer was absent historically and adds a synchronization participant.
This tests a measurement/scheduling influence, not historical reconstruction.

Exactly ONE fresh process acquisition; no retry or replacement. Preserve a
preparation failure, first native refusal, host timeout, or complete success.
The browser, interpreter, builders, request ordering, waits, world geometry,
all fourteen RESETs, negative/freshness oracles, seed=1, physics thread=1,
32 ms, 5 simulated seconds, 250 ms and 1500 host seconds remain unchanged.
No CPU quota is applied. The source is restored immediately after compilation.
The separate Python observer Robot is omitted. The Runtime retains native pose,
matrix, six velocities, contacts, cached consumed GPS/IMU/gyro and motor TARGETS
in memory at each iteration before command processing. No direct motor current
measurement is claimed. Two existing phase prints write to a memory stream.
Memory is flushed to files only when the original RESET predicates have already
selected acceptance or timeout, before emitting that response. This does affect
later scheduling; same timestamp never establishes simultaneous reads.
Native self reads and memory formatting also have overhead; this is reduced
structural interference, never an assertion of an unperturbed experiment.
128 MiB per-attempt buffer limit fails explicitly, without accepting RESET.
Raw native trajectory since the preceding completed RESET is retained; original
Runtime responses remain in webots.log. Phase-response joining uses exact ids
and refuses missing/duplicate responses. No ACK is inferred from teleportation.

Predictions and decision:
- A timeout with persistent false predicates matching native movement/pose
  selects a physical branch for this actual trajectory. Examine actuation and
  contacts before attributing a mechanism.
- A prolonged disagreement after +64 ms selects sensor/read-order/freshness
  investigation. Preserve both observations and their sampling phase.
- Success tests only this no-extra-controller case. It disproves a universal
  requirement for the extra observer to make RESET succeed, not stochastic
  masking and not historical failure disappearance. Do not repeat identically.
- A host timeout, incomplete scenario, measurement or preparation failure is
  distinct from native RESET_TIMEOUT and prevents a complete acceptance claim.

Run in a clean isolated checkout with Docker:
`bash tools/prepare_runtime_v2.sh` then
`python3 experiments/runtime-reset-buffered/run.py`.
Retain ci-artifacts/progression-autonomous-mission in full. The dedicated
push-only workflow runs this case once and always uploads retained bytes.
This experiment is not CI Gate, a production repair or a main-health verdict.
