# WebeeBlocks

WebeeBlocks is an offline-first block-programming environment for learning
algorithmic reasoning through robotics. Students build a Blockly program,
exercise it in Webots and, for the final teacher-authorized activity only, may
reuse the same backend-neutral program with a real Crazyflie.

## Product foundation

- Webots R2025a;
- Blockly 13.2.1 with the Zelos renderer;
- French student interface;
- explicit Open, Save and Save As for portable `.wbb` projects;
- a backend-neutral AST, preflight validation and shared interpreter;
- Webots simulation as the normal classroom execution environment;
- no student accounts, progress tracking, grading engine or automatic hints.

The durable product constraints are in
[`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md).

## Source layout

| Path | Contents |
| --- | --- |
| `plugins/robot_windows/blockly_v2/` | current Blockly 13.2.1 Robot Window UI |
| `plugins/robot_windows/blockly/webeeblocks/` | AST, interpreter and product contracts |
| `controllers/crazyflie_runtime_v2/` | shared Webots Runtime controller |
| `worlds/` | Webots activities and regression worlds |
| `tools/ci/` | executable acceptance oracles and preparation tools |
| `experiments/` | explicitly non-product research artifacts |

The historical Blockly/Runtime implementation is retained temporarily for
regression evidence. Its runtime files remain active; its upstream development
demos, tests and tooling are preserved by the
`v3-archive/pre-v3-webots-ci` tag instead of the active tree.

## Prepare the current Runtime

Linux:

```bash
./tools/prepare_runtime_v2.sh
```

Windows PowerShell:

```powershell
./tools/prepare_runtime_v2.ps1
```

These developer commands prepare the pinned Blockly browser distribution used
by the Robot Window. Students do not run Node.js or npm. The Windows classroom
artifact additionally contains the compiled controller, local R2025a Robot
Window bridge, offline Crazyflie assets, one-click launcher and integrity
manifest. See [`docs/WINDOWS_DEPLOYMENT.md`](docs/WINDOWS_DEPLOYMENT.md).

## Development

- `develop` is the integration branch;
- `main` is the human-controlled stable branch;
- one vertical product slice is delivered through one Ready pull request;
- `CI Gate` is the single required check and selects conservative Runtime and
  Webots suites;
- promotion to `main` and physical Crazyflie tests are human operations.

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) and [`AGENTS.md`](AGENTS.md).

## License

The project declares GPL-3.0. Bundled third-party components retain their own
license notices; a classroom release must preserve them.
