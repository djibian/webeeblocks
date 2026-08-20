# Reactive AST interpreter — experiment

This experiment is intentionally isolated from the frozen `webots-ci` release candidate. It does not modify the product Robot Window, Blockly product UI, Webots worlds, Crazyflie runtime, PID, STOP semantics or `main`.

## Question

Once real Blockly 2020 has produced the backend-neutral AST demonstrated in draft PR #44, can WebeeBlocks execute `repeat`, `if` and `range` semantics deterministically **without putting control-flow logic inside a Webots or cflib backend**?

## Scope

The interpreter accepts the experimental AST envelope already demonstrated by #44:

```text
Blockly → AST → interpreter → backend actions / sensor reads
```

The backend contract is intentionally small:

- `readRange(direction)`
- `takeoff(height_m)`
- `move(direction, distance_m)`
- `vertical(direction, distance_m)`
- `turn(angle_deg)`
- `wait(seconds)`
- `setSpeed(speed_m_s)`
- `land()`

The backend does **not** implement `if`, `repeat`, comparisons or boolean logic. These remain one shared semantic layer for future Webots and cflib backends.

## Discriminating fixture

The test executes exactly the representative reactive AST used by #44:

`takeoff → repeat 3 { if range(front) < 0.5 then left 0.3 else forward 0.3 } → land`

The scripted Multi-ranger sequence is:

```text
front = 0.40 m, 0.80 m, 0.30 m
```

The exact required trace is therefore:

```text
takeoff(0.5)
readRange(front) -> 0.40
move(left, 0.3)
readRange(front) -> 0.80
move(forward, 0.3)
readRange(front) -> 0.30
move(left, 0.3)
land()
```

This proves that the sensor expression is re-evaluated on every loop iteration rather than cached once before the loop.

## Fail-closed checks

`test_interpreter.js` also requires rejection of:

- missing scripted sensor samples;
- unsupported statement kinds (including any hypothetical `avoid_obstacle` shortcut);
- invalid repeat counts;
- an unsupported AST envelope;
- invalid/missing backend methods;
- excessive execution/nesting budgets.

Boolean `AND`/`OR` use short-circuit semantics, which is tested to ensure that a skipped branch does not perform a phantom sensor read.

## Run

```bash
node experiments/reactive-ast-interpreter/test_interpreter.js
```

## Explicit limits / non-claims

- The branch does not import the #44 compiler and does not change #44; it consumes the AST **contract shape** already demonstrated there.
- No Webots execution is claimed.
- No `cflib`, Crazyradio or physical Crazyflie behavior is claimed.
- No real Multi-ranger telemetry is claimed.
- Timing/concurrency semantics are not yet modeled; backend calls are synchronous in this disposable proof.
- This is not a final runtime architecture decision.
- No merge into `webots-ci` should occur before human-trial feedback and explicit Lead arbitration.

## Engineering conclusion criterion

If the dedicated test is green, this experiment answers only one question: a single shared interpreter can own reactive control-flow semantics while a backend remains limited to actions and sensor reads. The next experiment should be selected separately rather than expanding this branch with Webots or cflib.
