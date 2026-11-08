# Webots R2025a scene revision experiment

This patch extends the [source-built observation frame](../native_frame/README.md).
It adds the current world incarnation and 64-bit revision to the frame at
capture and exposes a separate live revision query for the experiment.
The engine refuses a guarded velocity change unless the captured incarnation
and revision still match immediately before the native effect. Validation,
consumption of the revision and the existing Solid velocity setters all run
in the same engine-thread Supervisor dispatch. The API acknowledges only
an applied effect. Saturation makes the revision invalid. A newly loaded
world has a different incarnation.

This is an isolated diagnostic with the existing Supervisor privileges.
It has no connection to pupil code, TAKEOFF admission, ALIVE renewal,
Grand Prix RESET acceptance or independent LAND. The guarded velocity
setter is a concrete native test effect for the ordering property.

## Covered source paths

| Effect | Native point | Verified here |
| --- | --- | --- |
| Solid named state restore | `WbSolid::reset` before pose and physics changes | Move and restore at 16 ms, two increments |
| Queued Supervisor field write | `WbSupervisorUtilities::processImmediateMessages` before `apply` | Fixture setup |
| Primitive Supervisor MF insertion and removal | Typed insert and remove after request and index validation | Collision triangle changes and is restored at 24 ms, two increments |
| Scene insertion and removal | `WbNodeOperations::initNewNode` and `deleteNode` at the parent field edit | Add and remove at 16 ms, original cardinality restored |
| Native Supervisor velocity write | `WbSupervisorUtilities::handleMessage` before the Solid setters | Stale refusal, fresh application, replay refusal |
| Supervisor node physics reset | `WbSupervisorUtilities::handleMessage` before `resetPhysics` | Zeroed velocity and invalidated token at 16 ms |
| Supervisor ODE force/offset/torque | `WbSupervisorUtilities::handleMessage`, valid dynamic body before `dBodyAdd*` | Three native stale-token probes added; engine recompilation/run pending |
| World reset | `WbWorld::reset` before reconstruction | Hook present, qualification pending |
| Robot controller restart | `WbRobot::restartController` prior to session restart | Native stale-token refusal probe added; rebuilt-engine run pending |

The controller-restart and ODE effect probes must be rerun on a rebuilt native engine; retained results do not qualify them. The separate global-reset probe described below is already included. The engine can still be changed through other paths. GUI pose and field
editing, unclassified native writes, direct topology edits, DEF/USE,
full PROTO regeneration, save/load variants, world reload and
disconnect/reconnect still need source coverage and native tests.
The field-write hook is conservative and also counts legitimate protocol
writes. Production needs verified native provenance for those writes, ODE
and visual-only propellers. The Floor PROTO crash in the lab remains
unqualified. An old token cannot regain validity in the covered experiment.
The product's per-attempt admission and atomic effects at the pilot and
result boundary are separate work for #911 and #913.

## Reproduce

Apply `webots-r2025a-revision.patch` after the observation patch on the exact
Webots R2025a source revision. This deliberately changes wire version 1 to 2.
Rebuild both ends together. The C `WbSupervisorPhysicsFrame` layout is unchanged.

```sh
git -C /path/to/webots apply --check "$PWD/tools/grand_prix/native_revision/webots-r2025a-revision.patch"
git -C /path/to/webots apply "$PWD/tools/grand_prix/native_revision/webots-r2025a-revision.patch"
export WEBOTS_HOME=/path/to/webots
make -C "$WEBOTS_HOME/src/webots" -j8 release
make -C "$WEBOTS_HOME/src/controller/c" -j8 release
python3 tools/grand_prix/native_revision/check.py --patched /path/to/staged-v2 \
  --output /path/to/new-revision-run
```

The [Linux run](results-linux.json) compiled both ends and observed
revision `3 → 4 → 5` for move and restoration at the same simulated instant.
The captured token refused an actual velocity write. Revision 5 accepted
it once, producing revision 6. The native physics reset advanced to 7.
Transient topology advanced to 8 then 9 with the original root cardinality
restored. The original token remained invalid throughout.

The predecessor at `886ab42d3e28468122ef81f6e6f0995fd87ae157` allowed the stale
velocity effect after a primitive MF insertion and removal at the same
simulated instant. In the fixed engine, inserting a point at index 1 of an
`IndexedFaceSet.coord.point` in a Solid's bounding object changes the triangle.
Removing the point restores the original three points. The revision advances
9 → 10 → 11 at 24 ms and the captured token cannot change velocity. The separate
node insert/remove still advances exactly once per effect.

## Route-5 revision shadow

Run `native_frame/route_shadow.py` as documented for #922, with the v2
distribution and `--with-revision`. The witness reads the frame revision
with the payload and checks the live incarnation and revision after the
legacy Supervisor reads. A changed token discards the sample before parity
counting. The legacy evaluator and its pilot retain authority.

The [Linux route witness](route-5-revision-linux.json) compares 2128 eligible
samples with zero divergences. The single frame at 10400 ms is discarded.
It was captured at revision 1315 and the subsequent native read observed
revision 1316 in the same world, after the RESET-side velocity change.
The complete stock and patched lifecycle witnesses are identical.
This establishes rejection of the observed ordering case for the instrumented
paths. It neither qualifies exhaustive mutation coverage nor admits a
product transition to the compact observation.

## Draft repair: reply isolation (not native-qualified)

The two experimental revision replies (105/106) are now emitted by
`WbController::writeAnswer` **after** the ordinary robot, Supervisor and device
answers, and before the already-terminal optional frame 104. The decoder
accepts a revision token only when exactly 24 bytes remain and an outstanding
revision request exists; it accepts an effect acknowledgement only when exactly
one byte remains and an outstanding guarded request exists. Unexpected lengths,
unsolicited replies and missing payloads fail closed. The ordinary responses
have already been written before any of these experimental trailers.

These methods are separately flushed under the existing robot mutex; combined
105/106 or 104/revision responses deliberately fail closed rather than claim
a valid token or effect acknowledgement. A lost acknowledgement does not prove
that the native velocity effect was absent; callers must not blindly retry.
Host-side source contract tests: `python3 -m unittest
tools.grand_prix.native_revision.test_reply_tail`. This does **not** constitute
a Webots R2025a rebuilt-binary protocol injection test or a production
attestation. Test valid and truncated 105/106 alongside ordinary time and
device replies, then an optional frame, before declaring the repair qualified.

## Draft global-RESET coverage repair (native proof pending)

The source review of the previous Draft HEAD identified a distinct uncounted
`C_SUPERVISOR_SIMULATION_RESET_PHYSICS` path: it calls
`WbApplication::resetPhysics()` directly, not `WbSolid::reset()` nor the
per-node RESET_PHYSICS case. This patch increments the revision once at the
global Supervisor effect boundary, before the call to clear ODE physics.
`check.py` now tests a moving Solid's fresh token, global RESET without a
simulation step, revision increment, zeroed velocity and native refusal of
the older token. This is a **new, unexecuted witness** until both Webots
binaries are rebuilt from the pinned sources and the output is recorded.
The previous `results-linux.json` remains historical proof of the older
scope and is not presented as qualification of this repair. Joint-position,
GUI and other mutation paths remain unqualified.
