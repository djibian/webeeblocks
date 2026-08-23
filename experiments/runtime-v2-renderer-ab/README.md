# Runtime v2 renderer A/B experiment (#73)

This experiment compares Blockly 13.2.1 **Thrasos** and **Zelos** inside the real Webots R2025a Runtime v2 Robot Window.

Only the renderer query parameter varies between the two fresh Webots runs. Activity/profile, toolbox, fixture workspace, semantic AST compiler, interpreter, WWI backend, PID/STOP controller and world all remain the product versions from `webots-ci`.

## Evidence

For each renderer the probe records:

- exact `webeeblocks-ast-v1` output;
- actual renderer registry match;
- 1366×768 screenshot;
- workspace/toolbox/flyout/zoom/trash geometry;
- block extents and block counts;
- the native keyboard path: Tab into toolbox, ArrowDown/Up, category activation, flyout block reachability, and workspace focus return.

Unsupported keyboard steps are data, not automatic failures. The experiment does **not** register WebeeBlocks-specific shortcuts to obtain a green result.

The harness fails on semantic mismatch, wrong renderer, missing screenshots/metrics, or inability to instantiate the real Robot Window. It deliberately does not select a visual winner automatically. Recommendation must follow the pre-registered order in issue #73 and be independently audited.

## Non-goals

No renderer productization, theme/CSS redesign, new blocks or activities, debug, project files, physical Crazyflie work, PID/STOP change, Runtime v1 change, or `main` change.
