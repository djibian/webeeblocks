# #637 — recovered independent LAND captures

This evidence branch retains the original local native acquisitions from the
independent continuation study. The environment temporarily disappeared; the
files were later recovered, their original manifests verified without changes,
and a new archive sealed and reread. This is retrospective preservation, not
an archive published before acquisition or independent timestamp attestation.

Archive: evidence/land-637-recovered-captures.tar.gz, 1,832,032 bytes,
SHA256 a7ae2f4818fa8d07d5f55d19714f780005283311b63ee4a98efd21688c936cbb.
337 retained files plus RECOVERED_SHA256.json. Extract into a private directory
and check its manifest before running analyze_captures.py against the extracted
land-637-recovered-captures directory. The script verifies original per-capture
manifests and recalculates request positions, final displacement, first contact
and maximum pitch. Treat pitch-only old logs as pitch-only evidence; do not
invent roll/yaw traces or measured internal motor velocities.

The recovered native command-force tar retains its previously reported SHA256
fd3ff25f3d40a219c8166c2cccbdd16b2ee6e269e2e187e214aedec2efd49b88.
The first-step residuals and audit/replay calculations are included. Original
studies remain at eccfe5701c2459bc1ae737bcea70bf5004061f27,
4078589bdb096b058ad054c484c9811dfdee3698 and
3326b9ba9eec27870aefe4b2230edf95fdedec8f.

The complete C/PID/propeller historical input replay reproduces final X
-2.40115223257 m on unchanged main. The 0.15 m/s reference ramp plus position
hold gives +0.165643915511 m (about 0.9 mm displacement from request). The
published regression driver on the same source independently rejects the
baseline (completed=1 failed=1, Webots exit 1) and accepts the repair
(completed=1 failed=0, 2.976 s observed stability, both processes exit 0).
The twelve height/step captures and separated interventions are retained.
Neither these shell fixtures nor an ACK qualifies the official full missions.

Refusals are preserved: native-independent-01 lacked local libXfont support;
full-baseline-01 used an unsuitable inherited Qt TCP proxy;
regression-candidate-01 after environment restoration lacked /usr/bin/xkbcomp.
No native observation or PASS is assigned to those preparation failures.
All successful old manifests verify without changed members. The recovered
archive seals original files, including binaries, worlds, wrappers and logs;
its own hashes establish internal integrity, not independent physical truth.

Important new refutation: canonical Draft run 40280309908, exact PR #700 HEAD
669d3a075e45add5d8ad5058628a8cb6ad0bbc82, successfully prepared the pinned
binary/cache but the real Grand Prix short negative failed with reason
low-outside-zone at 15.008 s instead of the required wrong-landing reason.
Artifact 12632226197, ZIP SHA256
c77e61a1918ea5fc87a59e8952bd82733f206f989e963e38e88523b7aa9a96a3,
CRC 45/45 and short-case manifest were independently checked. This is a real
native regression of the constant slow descent's timing, not a startup failure.
It is not waived by the local shell successes. The takeoff-zone exception ends
at 15 s; a refined approach must preserve this rule and every negative oracle.
No GO, LAND-wide qualification, RESET restoration, main-health restoration,
pedagogical acceptance, TEST_REQUIRED or flight follows from this archive.
