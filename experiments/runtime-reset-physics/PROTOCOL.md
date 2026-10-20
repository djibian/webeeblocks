# #637 — native ODE observation without Runtime Supervisor queries

Fixed before acquisition, exactly ONE fresh original browser campaign, no retry.
Parent experiment 39489946433 / 94c9efc completed fourteen strict RESETs and the
complete original positive/negative/freshness oracles. Downloaded artifact
12296001306 SHA-256 2191cafcbfbe173dde51fe78dbee7a9aa3a64e8d1f5594618c6066737523fc10
and its 21-file manifest were recalculated. The two-print transform plus buffered
header were verified, 25,767 native samples retained, 139 post-transient predicate
comparisons agreed. RESET 7 received at 449.504 s during a fall near first impact,
centre Z=.024354244 m, roll=.886395764, gyro X=1.484586964 rad/s, VZ=-2.199009598
m/s, accepted +352 ms. This is not a historical timeout or disappearance proof.

New discriminating question: do extra synchronous Supervisor state queries
perturb the internal-controller command path enough to mask an intermittent
failure? Exact R2025a c6793d8 supervisor.c shows get_position, get_orientation,
get_velocity and get_contact_points call wb_robot_flush_unlocked. The preceding
buffered acquisition therefore removed a controller/output surface but retained
these synchronous interactions. They do not establish unperturbed delivery.

Intervention: remove these additional calls from the Runtime. Keep the existing
consumed GPS/IMU/gyro and cached motor targets in memory; motor.c establishes
get_velocity reads its cache without flush. No extra Runtime sensor samples,
physics mutation, command, delay or per-step diagnostic output is added. Dumps
occur only after the unchanged RESET predicate has selected OK or timeout.

A native physics plugin records ODE pose, orientation, six velocities and contact
observations. Its collide callback ALWAYS returns 0 so normal Webots collisions
continue. dCollide observations are **geometric candidates**, not a claim that
each candidate became a force-bearing contact. ODE contact joint count is also
retained without assuming zero means an unconstrained body. Geometry pair ids
are session-local ODE ids, not Webots node ids; node_id is explicitly null.
No addForce, setPosition/velocity, new joint, attachment or send is performed.
The native file is flushed per physics step for retention on a first failure.
Plugin geometry queries and writing have overhead and may affect scheduling;
this is not a claim of no observer effect or historical identity.

Exact WbSimulationWorld.cpp calls stepEnd AFTER mCluster->step but BEFORE
increaseTime(timeStep). dWebotsGetTime returns milliseconds. Raw engine_time_ms
and the explicit +.032 s state time are both retained. Controller/native joining
uses that source-defined time, not a fitted shift; missing/duplicate timestamps
or truncated contact candidates refuse complete diagnostic validation. The
candidate contacts concern the preceding step interval, not the centre position.
Raw physics-state.jsonl, consumed-state.jsonl, buffered-phase.log and webots.log
remain primary. native-reset-state.jsonl is a derived time join using customData
from the consumed cache. Exact actual protocol responses, never inferred ACKs,
are joined by id to phase data for the existing predicate/window analyzer.

All original business oracles, internal controllers, browser HTTP reports,
14 RESETs, programs, sequence/waits, geometry, seed=1, physics threads=1, 32 ms,
5 simulated seconds, 250 ms, fail-closed behavior and 1500 host seconds remain.
The extra observer Robot is absent. WorldInfo adds only the read-only plugin.
Sources are restored immediately after build. Image, source/plugin/executable
digests and actual Chrome identity are archived. No production lock is changed.

Predictions: a genuine timeout with persistent native motion/pose matching false
predicates supports physical investigation; a persistent discrepancy after the
teleport-crossing sample supports freshness/read-order investigation. Agreement
and success establishes only this finite control, not disappearance. Historical
ODE/actuator state, Chrome identity, CPU/load and exact delivery remain absent.
A first preparation/measurement/host-budget failure stops without replacement
and cannot be relabeled RESET_TIMEOUT. No repeated green campaign follows.

Execute from a clean isolated checkout with Docker:
`bash tools/prepare_runtime_v2.sh` then
`python3 experiments/runtime-reset-physics/run.py`.
Preserve ci-artifacts/progression-autonomous-mission. The branch-specific
push-only workflow is not CI Gate. #637 remains open, cause unknown, main health
not restored and ordinary integrations suspended.
