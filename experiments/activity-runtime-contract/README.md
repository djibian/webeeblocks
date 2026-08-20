# A2 — activity contract to runtime experiment

This draft is isolated from the frozen `webots-ci` release candidate and from `main`.

## Question

Can one declarative activity profile govern, coherently and fail-closed:

`visible toolbox -> real Blockly 2020 workspace -> semantic AST -> runtime capabilities/bounds -> shared interpreter`?

## What is tested

One reactive program is loaded in the bundled Blockly 2020:

`takeoff -> repeat 3 { if range(front)<0.5 then left 0.3 else forward 0.3 } -> land`.

Three profiles reuse the same world and the same compiler/interpreter snapshots:

1. `reactive-front-enabled`: the program is visible, accepted and executes against a scripted backend (`0.4 -> 0.8 -> 0.3 m` => `left -> forward -> left`).
2. `reactive-front-no-move`: `move` is a known catalog block but hidden/forbidden by the profile; the already-built workspace must be rejected before any backend action.
3. `reactive-no-range`: the block remains visible but the runtime profile lacks `range(front)`; whole-AST preflight must reject before TAKEOFF/action.

The profile also narrows the real Blockly `FieldNumber` for move distance to `0.1..0.5 m`; the same bound is checked again on the AST so a manually altered AST cannot bypass it.

## Provenance / limitation

`frozen_extended_blocks.js`, `frozen_interpreter.js` and `experimental_blocks.js` are disposable snapshots of the already-frozen experimental #44/#45/#46 semantics. They are duplicated here only so A2 is a separate branch from `webots-ci`, #43 and #47. This is explicitly **not** a proposed product architecture.

No Webots dynamics, backend-B/STOP, cflib, real Crazyflie, new block, new world, teacher UI or level engine is added.

## Stop criterion

If the dedicated real-Blockly gate is green and Verification cannot falsify the toolbox/AST/capability/bounds contract, freeze this draft. Do not merge it toward `webots-ci` before human-trial feedback and explicit Lead arbitration.
