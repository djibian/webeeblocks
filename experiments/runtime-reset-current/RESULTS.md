# #637 — direct native actuator measurements, 21 October 2026

**Historical cause UNKNOWN. No causal production repair is justified. Main
health is NOT restored.** This acquisition ends the preregistered experiment;
it does not authorize another identical worker or a motor-restoration patch.

## New evidence, distinct from the 600 rad/s fixture

Run [39506425669](https://github.com/djibian/webeeblocks/actions/runs/39506425669),
exact acquisition HEAD `668d77b883fd594b72681d5cfe23e54a1a6b3e16`, attempt 1,
completed/success. One original internal-controller/RobotWindow/browser
autonomous traversal in pinned Docker Webots R2025a, Ubuntu22/Node22. Actual
browser: Chrome156.0.8078.47; deb/executable digests are retained. No delay,
trajectory, scenario, threshold, physics setter or negative oracle was changed.

Artifact **12303527298**, original ZIP **25,317,049 bytes**, SHA-256
`1033ddddd492d0bb69251f090e49089f2d034ee5fa92371dc342ed88eb543684`.
All 35 manifested members, ZIP membership/CRC, original/instrumented C, plugin
and buffered sources, exact world transformation and original business oracles
were reverified. An incomplete first local ZIP copy was rejected; only the
subsequent complete transfer supplied the accepted verification. The earlier
local preparation refusal is separately archived and is not a RESET failure.

The plugin directly reads the four native motor and propeller objects, IDs
243/254/265/276. Exact engine headers and binary disassembly corroborate offsets
640 for currentVelocity, 576/584 for currentThrust/currentTorque. These are
engine-state measurements, not commanded velocity or acceleration inversions.

| Recalculated quantity | Observation |
| --- | ---: |
| Native physical states | 28,896 |
| Buffered consumed states | 28,776 |
| Strict RESETs and all original mission/freshness oracles | 14/14 success |
| Largest real internal motor speed over the whole traversal | 57.6384017296 rad/s |
| Largest cached target speed | 131.2048753578 rad/s |
| Direct thrust/torque versus exact engine formula, maximum discrepancy | 0 |
| Current versus the source's 30 rad/s² recurrence including 1e-6 deadband | 0 |
| Native/consumed RESET comparisons from +64 ms | 141 |
| Predicate disagreements in those comparisons | 0 |
| Native/GPS discrepancy in the compared RESET samples | 0 m |
| Longest RESET acknowledgement latency | 384 ms |

The source recurrence matches the direct measurements here. Its use remains
conditional on the same engine semantics and complete actual target history;
it does not reconstruct the missing historical targets or currents.

## Collision 7: the relevant directly measured trajectory

The original collision-negative occurred at contact coordinate
`(0.754524,-2.217158,0.499370)`, followed by genuine
`RESPONSE 296 ERR UNSAFE_OR_TIMEOUT`. Contact coordinates are not body centre.
First cached all-zero targets in the ensuing interval occur at 531.744 s;
actual maximum motor speed then is 55.1855550194 rad/s. RESET299 is received
at **532.864 s**, 1.120 s later. This cached-zero timestamp is not a separate
direct timestamp of delivery of the unsafe response.

| Relative to RESET299 receipt | Direct motor speeds, rad/s | Total scalar thrust, N | Observation |
| --- | --- | ---: | --- |
| 0 ms | -21.585162, 21.585555, -21.355381, 21.355467 | 0.0737585481 | Body still at collision location; native motion agrees with consumed state |
| +32 ms | -20.625162, 20.625555, -20.395381, 20.395467 | 0.0673102998 | Body teleported and six native velocities zero; GPS difference crosses the jump |
| +64 ms | -19.665162, 19.665555, -19.435381, 19.435467 | 0.0611569636 | Native VZ=-0.274755575 m/s; motion predicate correctly false |
| +352 ms | -11.025162, 11.025555, -10.795381, 10.795467 | 0.0190479774 | ACK OK after unchanged 256 ms stable window |
| +736 ms | 0, 0, 0, 0 | 0 | Actual actuator extinction |

Thus the body reset **does not clear the real residual motor state even after
an ordinary collision**. That part of H1 is now directly observed in the
representative path, beyond the extreme synthetic fixture. It does **not**
follow that this state caused #637: this RESET succeeds, its residual thrust
at receipt is only about 15% of the model's 0.4905 N weight and it declines.
Across all fourteen receipts the largest total thrust is 0.3092630664 N.
No near-600 rad/s internal state is present anywhere in this traversal.

ACK while the motors are still decelerating satisfies the existing actual
pose/motion contract in this control; the 250 ms window and 5 s guard were not
changed. Neither a motor getter nor this successful observation is a new
acceptance oracle. No A-failure/B-repair comparison exists here.

## Historical attribution and changes capable of exposing the mechanism

| Historical change | Established effect | Causal limit |
| --- | --- | --- |
| a98121d2 / #99 merge 6f040e62 | Introduces zero motor targets, body teleport, body resetPhysics and physical stability window | Introduces this RESET architecture; does not identify the cause of the 19 October failure |
| 4d2e94ae | Adds the correct five-second fail-closed guard | Guard reports instability; it must not be removed or enlarged |
| #529 / 70719ea6 | Introduces the autonomous trajectories, collision negatives and successive RESETs | Exposes additional physical states; no proof it introduced a RESET defect |
| #589 / bd581024 | Changes scene grouping/lifecycle and SCENE/TAKEOFF preparation | Possible state/phase modulator; no paired causal evidence |
| #615 / 2515c32c | Changes the backend's wall-clock outcome budget | Possible pre-RESET phase modulator; already present in both scheduled PASS18 and FAIL19 |
| UNSAFE_OR_TIMEOUT path | Commands zero, latches failure and lets native body/actuator dynamics continue before RESET | The new trace measures that decline; the historical delay/current remains unknown |

The complete historical comparison already published in #637 excludes #633/#634
as direct mutations of the autonomous code/world/oracle between PASS18 and
FAIL19. A single PASS remains an invalid historical bisect-good oracle.

## Refuted, open and missing

Refuted in this measured domain: target speed equals actual motor speed; body
reset necessarily clears actuator state; any surviving actuator state necessarily
causes RESET_TIMEOUT; teleport GPS transient necessarily causes a timeout.
The short falling/rebound transient is physically real and correctly refused.
No persistent sensor/native discrepancy appears in these 141 samples.

**H1 as the explanation of historical #637 remains UNPROVEN, not universally
refuted.** The historical five-second trajectory/current/forces are absent.
Different contact/attitude states, actuator asymmetry, measurement freshness or
delivery phases remain possible; no one is selected by this successful control.
Intermittence and a responsible defect-introduction commit are still unknown.

No speculative actuator or GPS patch, new candidate PR, regression cure, new
cohort or extra native run follows. A relevant failing original trajectory must
select the responsible layer before a narrowly preregistered A/B intervention.

## Separate restoration completed: #654

Independently reviewed exact Ready `7dd183a589be2e432251ee7d5d6c9ee9265ac62c`,
owner GO **5592469048**, canonical PR CI **39495884606**, attempt1 success,
true Gate **118904948391** success. Controller16, workflow27 (+ cleanup12)
and JS RESET tests were independently passed on the exact isolated candidate.
The native reset/replay log records three RESETs and two UNSAFE_OR_TIMEOUTs.

Conditional squash integrated #654 as main
**b478f9dd1854d83345abe13ed20fcf7baeffaca5**. PR source HEAD association,
parentage/current-main membership and exact tree equality with Ready7dd were
verified. Contract/vision/roadmap blobs remain c1b0078/df0b3b8/e8c4e24.
Only the inconsistent *host* test envelope changes150→300 s (its unchanged
individual waits already total236 s), plus actual Chrome identity retention.
No native RESET deadline changes. This fixes a separate CI preparation/test
envelope defect, **not #637**. There is no separately observed canonical run on
the squash SHA at this assessment; exact Ready CI and identical tree are stated
separately. Global main health remains NON DEMONSTRATED; ordinary merges remain
suspended while #637 is unresolved.

## Reproduce the offline verification

From an evidence checkout containing this verifier, download the original
artifact12303527298 ZIP (never a repacked directory), then run:

```sh
python3 experiments/runtime-reset-current/verify_result.py --zip original.zip --output new-verification-directory
```

It rejects wrong ZIP bytes and an existing output directory; checks all original
members/source/world/ABI; replays the canonical business-oracle block without
launching Webots; recalculates every direct motor/force sample, RESET predicate,
window and native comparison. `DIRECT_RESULTS.json` is the recalculated result.

`evidence/direct-windows/WINDOWS.json` additionally binds exact original JSONL
lines in all fourteen [-96,+1024] ms RESET windows. Concatenate each file's
ordered parts and verify its complete SHA-256 before gzip decompression. These
506 native/header and484 consumed/header lines are a **labelled subset**, not a
replacement for the complete original artifact or proof of its absent intervals.
