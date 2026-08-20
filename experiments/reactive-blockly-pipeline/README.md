# Reactive Blockly pipeline — stacked experiment

This experiment is isolated from the frozen `webots-ci` release candidate. It is stacked on draft PR #45 and copies the exact experimental compiler/block definitions from draft PR #44 so neither prior draft needs to move.

## Question

Can the already-demonstrated layers compose without a hand-written AST?

`real bundled Blockly 2020 → #44 compiler → AST → #45 interpreter → scripted backend`

## Proof

The browser harness constructs the same reactive visual program used by #44:

`takeoff → repeat 3 { if range(front) < 0.5 then left 0.3 else forward 0.3 } → land`

with scripted ranges `0.40, 0.80, 0.30 m`.

It requires the exact execution trace:

`takeoff → range 0.40 → left → range 0.80 → forward → range 0.30 → left → land`.

It then serializes the real Blockly workspace to XML, reloads it, recompiles it and requires both the identical AST and identical execution trace.

A negative workspace containing a standard historical `text_print` block must fail in the compiler before any backend action occurs.

## Limits

- No Webots execution.
- No cflib/Crazyradio/physical Crazyflie behavior.
- No real Multi-ranger telemetry.
- No variables, procedures, lights or additional primitives.
- Interpreter/backend calls remain synchronous in this proof.
- No merge into `webots-ci` before human-trial feedback and explicit Lead arbitration.

## Stop criterion

Freeze this branch as soon as the dedicated CI proves the composed pipeline and Verification finds no semantic false positive.
