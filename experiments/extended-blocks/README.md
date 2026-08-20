# Extended Crazyflie blocks — experiment

This branch is intentionally isolated from the frozen `webots-ci` release candidate. It does not modify the product Blockly page, Webots worlds, Crazyflie runtime, PID, STOP semantics or `main`.

## Question

Can WebeeBlocks represent a richer student program — including movement, speed, timing, Multi-ranger sensing, conditions and repetition — as a semantic structure without exposing or generating Python?

## Experimental semantic catalogue

The prototype covers:

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

`extended_blocks.js` compiles the workspace into an experimental backend-neutral AST. No Python generator is involved.

Example semantic fragment:

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

## Proof 1 — semantic unit tests

```bash
node experiments/extended-blocks/test_extended_blocks.js
```

These tests cover a richer sequential mission, a reactive structure and invalid inputs.

## Proof 2 — real bundled Blockly 2020

`ui_harness.html` loads the actual Blockly 2020 build from this repository, the standard Blockly `logic`, `loops` and `math` blocks, and disposable experimental Crazyflie block definitions.

```bash
python3 experiments/extended-blocks/run_ui_harness.py
```

The browser proof constructs the real visual program:

`takeoff → repeat 3 times { if front range < 0.5 m then left 0.3 m else forward 0.3 m } → land`

and requires the exact backend-neutral AST. It also serializes the workspace to Blockly XML, reloads it into a fresh workspace and requires the same AST after round-trip.

This proof exposed and fixed a real integration mismatch: Blockly 2020 `controls_repeat_ext` stores `TIMES` as a **value input**, not a field. The compiler now handles the real Blockly structure while retaining a field fallback only for lightweight test doubles.

## Explicit limits

- This does **not** define final student wording or visual design.
- Conditions and Multi-ranger sensing are **not** claimed executable by runtime v1.
- The disposable block definitions are not loaded by the frozen product UI.
- It does not choose a future runtime implementation for condition/repeat execution.
- It does not claim real Crazyflie behavior.
- Numeric limits remain experimental guardrails.
- No merge into `webots-ci` should occur before human-trial feedback and Lead arbitration.

## Engineering conclusion

The semantic/UI boundary is now testable against the real bundled Blockly 2020. The next useful experiment should not add more block types here; it should test execution of one small reactive AST against a disposable backend/mock, or move to the independent real-Crazyflie transport axis.
