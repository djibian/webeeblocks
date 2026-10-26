# #637 / #700 — native ACK and low-contact boundary counter-tests

Subject: runtime bytes in #700 `9ee769c1e1e78b6a0d910d1bcf2b586bf77049fc`
(and unchanged in `819d3e8c423a78408786c4bd213c71c1e9f76b70`).
Comparison: original Ready `785362be34cb8334cea00505ba5fd0999d9bacd4`.
Responds to preparatory independent note #700 comment 6412706776.
No GO/NO_GO integration verdict is supplied by this author execution.

## Method and retention

The existing full-C native regression is reused with diagnostic request transport
and independent physical observations. The shared runtime/PID are unchanged.
The driver adds an observation at the exact LAND OK call, and controlled physical
interventions: one imposed horizontal velocity at first contact, or an obstacle
imported at LAND admission. R2025a runs actual motors, sensors and contacts at
32 ms. These are extra diagnostic worlds, not official mission configurations
or a new acceptance oracle. The existing 3 cm / pose / speed / attitude / stable
0.50 s post-ACK oracle remains intact. Deliberate refusals are retained as such.

R2025a release tar SHA256 c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38;
webots-bin SHA256 c12c65e8680b579d0f33c34be452f100a302bdecc6d9344becf356db4a675a1a.
The previous runtime paths had disappeared during the pause. Restored archive
files were checked against all 6039 regular tar members. Two staged libraries
were truncated; their original bytes were restored before accepted acquisitions.
Initial Bus-error runs supply no accepted native observation. One platform
preparation also lacked USER metadata. The original failed captures are retained;
changed log members in two failed preparations are explicitly listed under
study/refused-log-manifests.json. Their old manifests are not rewritten as valid.
All six substantive captures' original manifests verify without changed members.
The later archive manifest establishes preservation, not pre-registration or
independent attestation.

## Exact observations and refusals

| Case | Runtime | Native observation at ACK 13.792 s unless stated | Independent post-ACK oracle |
| --- | --- | --- | --- |
| nominal plane | new | VX=0.0000658 m/s, pitch=-0.000562 rad | completed=1 failed=0 |
| horizontal velocity imposed to +0.35 m/s at first contact | new | VX=0.0000159 m/s, X=0.202998 m | **failed=1**, final point outside 3 cm |
| same imposed velocity | original Ready | VX=0.244975 m/s, pitch=-0.042912 rad, X=0.247842 m | **failed=1**, final X=0.274814 m |
| nearby vertical wall imported at LAND request | new | ACK 13.856 s, VX=0.0000354 m/s, pitch=-0.000302 rad | completed=1 failed=0 |
| 1 cm platform under landing point | new | Z=0.024952 m, VX≈0, pitch=-0.000625 rad | **failed=1**, later pose/motion unstable |
| same platform | original Ready | Z=0.037420 m, VX=0.015620 m/s | **failed=1**, later pose/motion unstable |

The added impulse changes velocity at the contact observation, not a pupil
command; it is not evidence that an unchanged official witness creates that
impulse. New-runtime displacement from contact is about 5.3 cm. Its eventual
point error is about 3.6 cm relative to the LAND request, so the unchanged 3 cm
regression oracle correctly rejects it. The old Ready also rejects it and
acquits while still moving, with a much larger final point error. This does not
establish a newly introduced point-retention regression; it establishes a
remaining bound on what the fix and bare ACK can claim.

On the platform, the first qualifying contact at 13.376 s has centre
Z=0.0245305 m and **positive cylinder/plane clearance +0.00945147 m**. Thus the
height-based predicate demonstrably accepts a non-floor low contact. It is an
actuation trigger, not a certification of collision partner identity/normal or
of successful landing. The later oscillation is an observed failure in both
runtimes; its full cause is not established here. Do not relabel it PASS.
The Grand Prix explicitly has uniform floor and no low obstacles, so this
platform is not one of its seven official hidden configurations. Applicability
to any broader scenario must be assessed before transferring a restoration
claim. No exact positive CI result proves a universal ground-contact classifier.

Nominal and wall cases show actual near-zero motion at ACK, but the source still
uses the original height/VZ condition for ACK. No general horizontal/attitude
ACK invariant is inferred. Complete mission/RESET pose oracles remain necessary.
The nominal capture also includes temporary contact loss after touchdown; the
motor targets remain zero throughout the later observed settling phase.

## Archive

`evidence/boundary-captures.tar.gz`: 718023 bytes;
SHA256 adebac53d64a8d79a3968b21b764e3896b62b865365c08f07b3501601dc380f3.
Complete driver, executed runner, full C inputs/binaries/worlds/logs/observations,
original per-capture manifests, failed preparations and a preservation manifest
are included. Verify SHA256.json after extraction. RESULTS.json retains exact
ACK/first-low-contact/end records. The full original contact observations remain
in controller.log; target velocities are command observations, not internal
rotor telemetry. All producers of substantive captures had stopped before sealing.

Reproduce a case with the archived runner (adjust its explicit ROOT/HERE paths):

```
USER=root LAND_QUALIFY_CASE=slide python3 runner.py --home WEBOTS_HOME \
  --xvfb XVFB --out NEW_DIRECTORY
```

Cases: nominal, slide, wall, platform. Select the archived original Ready source
with --runtime-source for the comparison. A nonzero result on slide/platform is
the retained diagnostic refusal, not a reason to weaken the oracle or blindly
repeat the same acquisition. No change to PID, contact geometry, friction,
timeouts, existing mission oracles or decision authority is made here.
