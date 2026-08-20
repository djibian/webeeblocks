# B4 — reactive dynamic backend experiment

Question: can the already-proved real Blockly 2020 → semantic AST → shared reactive
interpreter chain drive the **dynamic** Crazyflie backend-B/STOP semantics instead of
the kinematic Supervisor adapter from #47?

The fixture is intentionally unchanged:

`takeoff → repeat 3 { if range(front)<0.5 then left 0.3 else forward 0.3 } → land`

The Webots controller uses the same Bitcraze PID gains, velocity/yaw caps and common
0.5 s STOP completion boundary already characterized in `webots-ci`. A tiny CI-only
file bridge exposes synchronous RPC to the unchanged browser interpreter. Control-flow
(`repeat`, `if`) remains entirely in the shared interpreter.

Expected causal proof:
- native `range_front` is re-read after every completed dynamic primitive;
- geometry changes cause the branch pattern `LEFT → FORWARD → LEFT`;
- every movement response is emitted only after the common STOP boundary;
- unsupported `range(left)` is rejected by whole-AST preflight before TAKEOFF;
- no Supervisor pose teleport/reset is used for actions.

This is an experimental seam proof only. It does not validate a physical Multi-ranger,
cflib/Crazyradio, or real-flight behavior. It stays draft and must not be merged into
`webots-ci` before human-trial feedback and explicit Lead arbitration.
