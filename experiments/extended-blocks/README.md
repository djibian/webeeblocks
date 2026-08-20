# Extended Crazyflie blocks — experiment

This branch is intentionally isolated from the frozen `webots-ci` release candidate. It does not modify the product Blockly page, Webots worlds, Crazyflie runtime, PID, STOP semantics or `main`.

## Question

Can WebeeBlocks represent a richer student program — including movement, speed, timing, Multi-ranger sensing, conditions and repetition — as a semantic structure without exposing or generating Python?

## Experimental semantic catalogue

The prototype currently covers:

- take off to a relative height;
- land;
- move forward/back/left/right by a distance;
- move up/down by a distance;
- turn left/right by an angle;
- wait;
- set translational speed;
- Multi-ranger value expressions: front/back/left/right/up;
- standard Blockly comparisons and AND/OR expressions;
- standard Blockly `if/else` and `repeat N times` control blocks.

There is deliberately **no** `avoid obstacle` block. The semantic tree keeps the pedagogical sequence visible: measure → compare → decide → act.

## Output

`extended_blocks.js` compiles Blockly-like objects to an experimental, backend-neutral AST, for example:

```json
{
  "kind": "if",
  "condition": {
    "kind": "compare",
    "op": "LT",
    "left": {"kind": "range", "direction": "front", "unit": "m"},
    "right": {"kind": "number", "value": 0.5}
  },
  "then": [{"kind": "move", "direction": "left", "distance_m": 0.3}],
  "else": [{"kind": "move", "direction": "forward", "distance_m": 0.3}]
}
```

The compiler fails closed on unsupported blocks, invalid directions and out-of-range parameters.

## Proof

Run:

```bash
node experiments/extended-blocks/test_extended_blocks.js
```

The tests cover a richer sequential mission and a reactive structure equivalent to:

`repeat 3 times: if front range < 0.5 m then move left 0.3 m else move forward 0.3 m`.

## Explicit limits

- This does **not** define the final student block wording or visual design.
- This does **not** claim that conditions or Multi-ranger sensing are executable by runtime v1.
- It does not yet instantiate these experimental blocks in the real Blockly 2020 browser.
- It does not choose between a future Webots backend and a real-drone backend for these richer semantics.
- Numeric limits are experimental guardrails, not final pedagogical constraints.

The next valuable proof on this branch is a disposable real-Blockly harness that instantiates the proposed blocks plus standard `if/repeat/logic` blocks and verifies that the exact semantic AST is produced without Python generation.
