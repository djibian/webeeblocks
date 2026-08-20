# Experiment B3 — reactive Webots adapter

This disposable experiment answers one question only:

> Can the already-proved `real Blockly 2020 -> semantic AST -> shared reactive interpreter` chain consume a real Webots `range_front` measurement and make different Webots movement effects from it?

## What is deliberately unchanged

The branch is stacked on draft #46. It reuses without modification:

- the real bundled Blockly 2020;
- the experimental block definitions/compiler frozen by #44;
- the reactive interpreter frozen by #45;
- the exact reactive fixture proved by #46:
  `takeoff -> repeat 3 { if range(front) < 0.5 then left 0.3 else forward 0.3 } -> land`.

No `if`, `repeat` or comparison logic exists in the Webots adapter.

## Webots adapter boundary

`webots_backend.js` is intentionally tiny. It exposes only:

- `takeoff(height)`;
- `move(forward|left, distance)`;
- `readRange(front)`;
- `land()`.

All other semantic capabilities fail closed. `readRange(front)` is sourced from the native Crazyflie R2025a `range_front` DistanceSensor and converted from the PROTO's millimetre lookup-table output to metres.

The Webots-side controller is **kinematic on purpose**: it moves the native Crazyflie node through Supervisor pose updates instead of motors/PID. This proves the sensor/interpreter/action seam and real Webots geometry only. It does **not** claim Crazyflie flight dynamics, backend-B parity, physical Multi-ranger behavior or cflib behavior.

## Discriminating world

Two narrow physical obstacles are arranged so the same real `range_front` sensor should produce this branch sequence as the vehicle moves:

1. near obstacle -> `left(0.3)`;
2. clear ahead after moving left -> `forward(0.3)`;
3. second obstacle now near -> `left(0.3)`.

The browser and Webots controller keep independent causal traces. CI requires:

`takeoff -> range -> left -> range -> forward -> range -> left -> land`

and checks that each movement changes the actual Webots node pose in the commanded axis.

## Fail-closed proof

A second real Blockly workspace changes only the sensor direction to `left`. The compiler still produces a valid semantic AST, but this minimal adapter does not advertise that capability. Execution must fail before any Webots RPC or action is recorded.

## Explicit limits / stop criterion

- No product or `webots-ci` modification.
- No new language feature.
- No variables, procedures or lights.
- No motor/PID flight semantics.
- No physical Crazyflie/Crazyradio/deck claim.
- No merge toward `webots-ci` before the human trial and explicit Lead arbitration.

If CI proves real Webots sensor re-read -> interpreter branch -> movement effect, freeze this draft. Do not expand the language here.
