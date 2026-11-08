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
| Scene insertion and removal | `WbNodeOperations::initNewNode` and `deleteNode` at the parent field edit | Add and remove at 16 ms, original cardinality restored |
| Native Supervisor velocity write | `WbSupervisorUtilities::handleMessage` before the Solid setters | Stale refusal, fresh application, replay refusal |
| Supervisor node physics reset | `WbSupervisorUtilities::handleMessage` before `resetPhysics` | Zeroed velocity and invalidated token at 16 ms |
| World reset | `WbWorld::reset` before reconstruction | Hook present, qualification pending |

The engine can still be changed through other paths. GUI pose and field
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
