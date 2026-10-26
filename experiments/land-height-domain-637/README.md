# Current LAND repair — six takeoff heights, two native physics steps

Subject: unchanged shared C in #700 Ready
819d3e8c423a78408786c4bd213c71c1e9f76b70 (same runtime bytes as 9ee769c).
Actual R2025a C/PID/motors/sensors, qualification cylinder/inertia, plane.
This follows the ACK/contact boundary study; it is not a canonical mission proof.

The native request sequence is TAKEOFF(height), WAIT .5, MOVE forward .1 twice,
LAND, with the historical no-earlier-than request times and no resubmission.
Heights were fixed to .20/.35/.50/.80/1.00/1.50 m, independently of outcomes;
physics 32 and 8 ms, **controller/sensors always 32 ms**. No PID, geometry,
friction, safety threshold, timeout or production source was changed. The driver
uses a diagnostic height environment input and reports the exact ACK state.
It retains the independent 3 cm position / altitude / attitude / velocity /
0.50 s stability oracle over the three seconds after ACK, and rejects nonzero
motor targets after any observed pre-ACK contact. The historical fixture's
contact-before-ACK coverage assertion is deliberately not asserted for these
*different height* diagnostic cases; actual coverage is reported below.
The mandatory canonical historical fixture keeps its coverage assertion.

| Height m | Final XY error mm, physics 32 ms | Final XY error mm, physics 8 ms |
| --- | ---: | ---: |
| .20 | 11.8666 | 4.1314 |
| .35 | 15.4510 | 15.2945 |
| .50 | 16.6467 | 11.3081 |
| .80 | 10.0174 | 10.3659 |
| 1.00 | 6.5200 | 6.9512 |
| 1.50 | .5351 | .5719 |

All twelve native sequences finish completed=1 failed=0, maximum final XY error
16.647 mm <30 mm. Continuous final post-ACK stability is 2.464–2.976 s.
Only four cases observe the contact latch before ACK: 32 ms at heights .20/.35/
.50 and 8 ms at .35. Other cases ACK under the original altitude/VZ window before
a qualifying contact is observed by the 32 ms controller; motors are then stopped
by terminal LAND. Some ACK samples still have measurable angular motion or centre
Z about .0426 m (origin about .015 m). These observations **do not prove an
intrinsic ground-contact/full-motion ACK invariant**. Independent terminal pose
and motion evidence is necessary. No case is transferred to a different
trajectory, step, world or complete mission.

All original per-capture manifests were verified without changed members after
the direct native producers stopped. Full executed C/driver/runner, binaries,
worlds, complete physical/controller logs, exact ACK states, source/binary hashes,
exit codes and a preservation manifest are archived. The runner has explicit
local ROOT/HERE paths that must be adjusted for reproduction. Supply
USER=root LAND_REPLAY_HEIGHT=HEIGHT LAND_QUALIFY_CASE=nominal and --step 8 or 32;
no production program or controller is edited by this height input.

Archive: evidence/height-captures.tar.xz, 505600 bytes, SHA256
53db274632c5cb6aa1159bdc895b50ff4a2d4fc553fcde924d096bbece9e97fa.
SUMMARY.json retains measured anchors, final positions, exact ACK/end/coast markers.
Verify PRESERVATION_SHA256.json and each original capture manifest after extraction.
These are local scientific observations, not independent timestamp attestation,
CI Gate, global LAND/RESET restoration, author GO, pedagogical PASS or flight proof.
The impulse/platform failures in the adjacent boundary study remain retained.
