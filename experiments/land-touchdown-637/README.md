# LAND s3: contact followed by powered rebound (#637 / #700)

The exact Ready `785362be34cb8334cea00505ba5fd0999d9bacd4` was refuted by
[canonical run 40282444841](https://github.com/djibian/webeeblocks/actions/runs/40282444841).
Original [artifact 12633173229](https://github.com/djibian/webeeblocks/actions/runs/40282444841/artifacts/12633173229):
ZIP SHA256 `445bd574d1ee8412d8d681e49b35ce60dda3e8302f8d9384befaa3e6f7abaf9a`;
CRC 184 members and 161 manifest entries independently verified.
The s3 witness ends at (0.7204718393, 1.6866522783) instead of (0.70, 1.50),
wrong-landing at 155.080 s. This remains a genuine refutation of that candidate.

## What the original evidence establishes

At 174.800 s, just before contact, VY=-0.02083 and VZ=-0.16471 m/s.
The contact interval changes the attitude and motion; VY later reaches
+0.42957 m/s at 175.200 s. This is not solely continued sliding against the floor.

Between 174.880 and 175.280 s, all 50 native 8 ms intervals have strictly
positive cylinder/plane clearance (minimum 0.754 mm), and every scene box is
more than 0.212 m away from the body centre. The unchanged cylinder fits inside
a 0.0523 m sphere. Contacts cannot produce the lateral acceleration there.
Infer body-Z thrust from the independent vertical balance
`T = m * (delta(VZ)/dt + g) / Rzz`, then predict both horizontal accelerations
using `T/m * Rxz` and `T/m * Ryz`. The inferred thrust is 0.46944–0.49467 N;
the maximum X/Y prediction residual is 4.724e-12 m/s². Peak AY is 1.900 m/s².
These are roundoff-level force-balance identities, not measured rotor telemetry.
No horizontal output was fitted. `analyze.py` verifies integrity, geometry and
this calculation from the original ZIP.

The shared C still runs the airborne velocity/altitude/attitude PID during the
0.50 s LAND confirmation window. Thus contact initiates the disturbance, and
powered motion after separation amplifies it. The evidence does not identify a
unique internal PID term or justify replacing the physical model or retuning
all gains. Earlier first-contact studies eccfe570/4078589/3326b9b remain scoped
to their historical 32 ms event; this analysis concerns the new 8 ms s3 event.

## Discriminating native intervention

`run.py` / `probe.py` use R2025a, the same 0.05 kg cylinder (height .03 m,
radius .05 m), 8 ms physics, the s3 pose/linear velocity at 174.800 s and an
explicitly approximate backward 8 ms angular derivative. They impose only
constant body-frame hover force, 0.4905 N, with zero external torque: no PID,
propeller-telemetry claim or fitted force sequence. This reduced model does
not exactly replay the original hidden actuator/controller/contact-solver state.

| Intervention | Cut after snapshot | XY displacement after 2 s |
| --- | ---: | ---: |
| Keep hover force | never | 2.711347 m |
| Cut at contact, control phase 0 | 32 ms | 0.000282 m |
| Cut at contact, control phase 8 | 8 ms | 0.000278 m |
| Cut at contact, control phase 16 | 16 ms | 0.000275 m |
| Cut at contact, control phase 24 | 24 ms | 0.000275 m |
| No-floor control, hover force | never | 0.255605 m |

Each cut case has an exactly identical complete physical prefix to its powered
control through the intervention observation. Constant thrust plus contact is
sufficient for substantial amplification without an active PID. Contact removal
and thrust removal are distinct interventions. These results support an
unpowered settling phase, not a universal physical guarantee or full mission PASS.

## Product intervention and full C discrimination

The repair keeps the two-segment descent and XY/yaw hold until a finite low
ground contact is observed within the existing height tolerance. It then latches
zero motor targets, including through temporary rebound/contact loss. It still
waits for the unchanged LAND height/VZ/0.50 s condition, and preserves the safety
checks, 25 s action timeout, RESET and exact independent 210 s deadline. Every
new ordinary or forced LAND clears the latch. A high/unavailable contact cannot
activate it; no mission outcome is derived from this latch.

The mandatory 32 ms native regression now actually covers contact before ACK
and observes every motor target on subsequent samples, in addition to its
independent post-ACK pose/stability oracle. Original Ready source: first contact
13.472 s, **completed=1 failed=1**, 104 coast observations (powered samples
refute coasting). Corrected source: same contact time, **completed=1 failed=0**,
104 zero-target coast observations, final X=0.149908237694 m, stable=2.976 s.
The older Ready's final X=0.1551717472 m happened to satisfy the pose-only oracle;
that old success is retained, not relabeled. The optional 8 ms historical replay
acknowledges before contact and does not exercise this boundary.

The full composed runtime/deadline fixture also checks one ground contact then
contact loss, refusal of high/NaN contact heights, no PID reapplication and the
same terminal ACK tick (212656 ms). It retains its existing fault, file, pose,
RESET and exact-deadline cases. A fixture stub never becomes native proof.

Local real Grand Prix tests use the ordinary real Blockly 13.2.1 builder,
preflight, .wbb round trip, shared interpreter, C/PID/broker/evaluator and TCP
extern transport. All seven seeds 0/1/3/4/14/15/17 succeed with the same AST;
all nine retained negative/reset cases pass their existing assertions, including
both exact 210.000 s expirations and the second identical run after RESET.
This is preliminary local evidence, not canonical exact-Ready-HEAD CI or an
independent GO. The final canonical run must retain full mission traces.

## Preservation and reproduction

`evidence/captures.tar.gz`: 698017 bytes, SHA256
`059db3ecb3a6c86ce97ec48b8ab656d32d59bde29a428461676f70d9aa823218`.
It contains the complete reduced captures and paired full-C regressions,
executed drivers/sources/binaries/worlds/logs and manifests. Local Grand Prix
metadata/logs and original per-capture trace digests are included; its large
`native_trace.csv` files are explicitly omitted from this supplementary archive.
The original failing Actions ZIP remains available at the link above.
The environment fingerprint is retrospective, not pre-registration or independent
attestation. Verify ARCHIVE_SHA256.json after extraction. The archive retains
executed script versions; later reruns have distinct captures.

Reproduction, with numpy/scipy for axis-angle reconstruction and real R2025a:

```
python3 experiments/land-touchdown-637/run.py --home WEBOTS_HOME --xvfb XVFB \
  --trace ORIGINAL_S3/native_trace.csv --out NEW_CAPTURE
python3 experiments/land-touchdown-637/analyze.py ORIGINAL.zip NEW_CAPTURE
```

No global LAND/RESET restoration, #665 resolution, main-health restoration,
pedagogical acceptance, real-flight permission or independent author GO follows.
