# Runtime v2 Blockly assets

Runtime v2 uses the pinned `blockly@13.2.1` dependency declared in this directory. Generated browser assets live in `vendor/` and are intentionally not committed.

From a clean checkout, prepare the Runtime v2 Robot Window once before opening `worlds/crazyflie_runtime_v2.wbt`:

```bash
./tools/prepare_runtime_v2.sh
```

Requirements:

- Node.js 22 or newer;
- npm;
- network access during this preparation step to install the pinned npm dependency.

The resulting Robot Window is self-contained at runtime: Blockly browser assets
are served from the local `vendor/` directory and the pinned Webots R2025a
bridge is served from `webots/`. No external browser resource is required while
Webots is running.

`tools/prepare_runtime_v2.sh` and `tools/prepare_runtime_v2.ps1` are developer
preparation paths. CI must exercise them from a checkout where `vendor/` does
not already exist; a workflow-only npm preparation is not product packaging
evidence. Student Windows machines use the prepared classroom archive and need
neither Node.js nor npm.
