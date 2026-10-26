# Native RESET phase discrimination — #637

**Diagnostic only. RESET_TIMEOUT was not reproduced; no repair or restored main
health is claimed.** No production source, CI, oracle, 5 s deadline, 250 ms
stability window, freshness rule or fail-closed behavior is changed by this PR.

This experiment extends the integrated #651 native TCP path to distinguish
pre-teleport sensor locals, the GPS difference crossing teleportation, and
subsequent physical settling. `instrument.py` inserts only two `fprintf`
statements in an isolated checkout's C source. It logs the existing locals and
predicate results; it neither re-reads sensors nor adds Supervisor requests.
`run.py` restores the original source in `finally`, including on refusal. The
rebuilt diagnostic executable remains local; rebuild production before using it
for another purpose. Do not run this wrapper in a shared checkout.

The existing passive observer records position, orientation, six world velocities
and contact points. The existing #651 baseline still requires four positives,
three negatives, native collision 7, UNSAFE_OR_TIMEOUT, seven distinct RESET ACKs
and unavailable stale outcome/new attempt 8. Any refusal stops acquisition.

## Reproduction

Prepare R2025a, its pinned source assets and Xvfb as described in
[the integrated native procedure](../runtime-reset-contact/README.md). Then:

```sh
python3 experiments/runtime-reset-phase/test_analysis.py
python3 experiments/runtime-reset-phase/run.py \
  --webots-home /absolute/path/to/webots \
  --assets-root /absolute/path/to/webots-r2025a-source \
  --output /absolute/path/to/new-baseline
python3 experiments/runtime-reset-phase/run.py --after-impact \
  --webots-home /absolute/path/to/webots \
  --assets-root /absolute/path/to/webots-r2025a-source \
  --output /absolute/path/to/new-grounded-control
python3 experiments/runtime-reset-phase/analyze.py \
  /absolute/path/to/new-baseline/controller-0.log
python3 experiments/runtime-reset-phase/verify.py
```

`--xvfb /absolute/path/to/Xvfb` and a suitable `LD_LIBRARY_PATH` are supported.
No ambient NODE_OPTIONS is accepted. The grounded control uses `after-impact.cjs`
to delay only the seventh ordinary RESET until the passive observer records
attempt-7 terminal failure, centre Z < 0.05 m and contact(s). It changes host
request timing, never pose, forces, velocities, ACK or stabilization logic.
The observed condition is **after contact, not the first impact impulse**.
Polling and WWI latency can advance simulation before Runtime receives RESET.

The two archived acquisitions used the original wrapper in `phase-run.py`;
the grounded control selected its hook through NODE_OPTIONS. The current wrapper
provides the equivalent explicit `--after-impact` argument and records it.
Original acquisition manifests/provenance are retained, alongside the later
analysis manifest. Analyzer revalidation is not a new native acquisition.

## Observations on main 088218c53af2c2a1b6b12d4b86ec3a24d502af0a

Both campaigns executed real R2025a with nine external TCP controllers and the
production WWI backend/shared interpreter/program builders. Both saw native
collision 7, UNSAFE_OR_TIMEOUT and a successful seventh RESET/new attempt 8.
The release archive SHA-256 was
`c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38`;
webots-bin was
`c12c65e8680b579d0f33c34be452f100a302bdecc6d9344becf356db4a675a1a`.

| Actual attempt-7 measurement | Baseline | Grounded control |
| --- | --- | --- |
| Native collision contact (m) | 0.752553, -2.216684, 0.499382 | 0.752554, -2.216683, 0.499382 |
| Runtime RESET receipt (simulation s) | 1514.336 | 1331.776 |
| GPS centre at receipt (m) | 0.752579, -2.270483, 0.507128 | 0.752608, -2.448116, -0.033091 |
| Pre-teleport gyro X (rad/s) | 1.446472 | 0.005702 |
| GPS-derived Y velocity at +32 ms (m/s) | 70.952598 | 76.503635 |
| First sample with both predicates true | +64 ms | +64 ms |
| Later motion rejection | none | +128 ms: VZ=-0.310097; +160 ms: VZ=+0.154744 m/s |
| Last bad sample | +32 ms | +160 ms |
| Final uninterrupted stable span | 256 ms | 256 ms |
| Last sample / successful RESET in that iteration | +320 ms | +448 ms |

The grounded trigger was observed at 1330.912 s, **864 ms before** the Runtime's
receipt. It already had 16 contact points and small native velocities: this is
not evidence of resetting at peak impact. At the first post-teleport observation
(+32 ms), both campaigns show identity orientation, position (0,0,0.015), zero
six-component native velocity and no contacts. Later ground contacts and vertical
motion differ. In the grounded case, native position/velocity confirm the
post-teleport descent and rebound at +128/+160 ms: these are not solely a GPS
teleport difference. By +192 ms its original predicates remain true for 256 ms.
The strict window correctly restarts after the two physical motion rejections.

The observer and Runtime are separate controllers. Equal simulation timestamps
do not imply simultaneous reads or a common order around synchronous flushes.
Only RESET_PHASE_BEGIN dates Runtime receipt; only its protocol response proves
an ACK. The first observation of attempt 8 is not the ACK timestamp.

## Interpretation and next discriminating experiment

**Observed:** the receipt iteration still uses pre-teleport locals; +32 ms has a
teleport-crossing finite difference while native velocity is zero; both cases
recover fresh poses/measurements. One case has additional real physical motion
and a restarted stability window. The archived per-sample predicates, window
state and finite differences are independently recalculated by `analyze.py`.

**Refuted in these trajectories:** a single teleport-crossing velocity spike is
not sufficient to produce RESET_TIMEOUT; collision 7 and this observed grounded
post-contact state do not inevitably make RESET fail. This is not a universal
bound on sensor recovery or physics, and does not explain the historical FAIL.

**Still hypotheses:** a rarer native contact/solver/force state or longer sensor
inconsistency could prevent the five-second stable postcondition. Neither is
demonstrated. No production correction is justified. In particular, clearing
finite-difference history alone would merely remove a known short rejection;
these measurements do not justify it as a repair of #637.

**Next useful discrimination:** retain these same internal sample fields in the
canonical browser/native historical path, with its exact world, initial state and
protocol sequence/timing. Stop on its first real RESET_TIMEOUT. At elapsed times
beyond the short measured transients, compare every false predicate against
native six-component motion/orientation/contacts. Stationary native state with
persistently contradictory sensor locals would select the sensor/freshness
hypothesis; matching native motion or pose error would select a physical path.
A green campaign alone answers neither. A later intervention should change only
the demonstrated offending factor and preserve the original negative/freshness
oracles. The two present runs differ in other request timings and are not a
matched estimate of the effect of delaying RESET.

The initial two preparation attempts stopped before native controllers because
Xvfb lacked xkbcomp and then libxkbfile; each missing dependency was diagnosed
before another startup. They are not native RESET failures. Acquisition logs,
world/C/binary digests, original/instrumented C, full native and protocol traces,
trigger, and analysis are retained in the two evidence archives. These finite
observations are neither canonical CI, full browser progression, pedagogical
acceptance nor hardware qualification. Keep #637 open and ordinary integrations
suspended.
