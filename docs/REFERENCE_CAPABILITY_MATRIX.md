# Reference Crazyflie capability matrix

This matrix records the **currently integrated** student-facing capability surface
for the reference hardware in issue #157. It is a product inventory, not a
workflow-state database and not a claim that a physical backend is already
proven.

Status vocabulary:

- **covered** — the generic Blockly/AST intent and the current Webots execution
  path both support the capability;
- **partial** — generic semantics exist, but the current Webots backend exposes
  only part of the intended hardware surface;
- **missing** — no current student-facing generic semantics/Webots behavior
  exists;
- **infrastructure only** — the capability is useful internally but is not a
  student-facing primitive;
- **physical unproven** — no current integrated evidence establishes the
  corresponding real-Crazyflie student execution path.

| Reference capability | Hardware source | Generic Blockly / AST | Current Webots path | Physical path | Current profile exposure | Status / smallest gap |
| --- | --- | --- | --- | --- | --- | --- |
| Take off / land | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_takeoff`, `webeeblocks_v2_land` → `takeoff`, `land` | Current WWI backend advertises and implements both actions | Physical student backend not proven | Progression 1+ | **covered** in simulation; **physical unproven** |
| Horizontal movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_move` → `move(direction, distance)` with forward/back/left/right AST vocabulary | Current WWI backend advertises and executes forward/back/left/right | Physical student backend not proven | Progression 1: forward; progression 3: forward/left; broader reactive profile declares four directions | **covered** in simulation for the generic horizontal vocabulary; **physical unproven** |
| Vertical movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_vertical` → `vertical(up/down, distance)` | Current WWI backend advertises and executes up/down with horizontal-position/yaw hold and bounded altitude targets | Physical student backend not proven | Broad reactive profile only | **covered** in simulation for the generic vertical vocabulary; **physical unproven** |
| Yaw turn | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_turn` → `turn(angle)` | Current WWI backend advertises and executes bounded signed yaw turns while holding position/altitude | Physical student backend not proven | Broad reactive profile only | **covered** in simulation for the generic yaw-turn vocabulary; **physical unproven** |
| Wait / pacing | Generic Runtime timing semantic; no dedicated hardware source | `webeeblocks_v2_wait` → `wait(seconds)` | Current WWI backend advertises and executes bounded waits while holding position, altitude and yaw; real-Webots CI checks requested simulated duration and hold tolerances | Physical student backend not proven | Broad reactive profile only | **covered** in simulation; **physical unproven** |
| Speed selection | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_speed` → `set_speed(speed)` | Webots Runtime v2 applies a bounded 0.1–0.35 m/s limit to subsequent horizontal `move` actions only; RESET restores the proven 0.35 m/s default; real-Webots CI compares slow/fast traversal causally | Physical student backend not proven | Broad reactive profile only | **covered** in simulation inside the existing proven horizontal envelope; **physical unproven** |
| Multi-ranger directional distance | Multi-ranger deck | `webeeblocks_v2_range` → `range(direction)`; AST vocabulary has front/back/left/right/up | Current WWI backend advertises and reads front/back/left/right/up through dedicated Webots sensors | Physical student backend not proven | Progression 3 exposes front; broad reactive profile declares front/back/left/right/up | **covered** in simulation for the generic directional range vocabulary; **physical unproven** |
| Flow Deck V2 downward range | Flow Deck V2 | No `down` value exists in the current student range AST vocabulary | Downward ranging/flow is robot infrastructure rather than a student-visible Runtime v2 range direction | #70 contains physical research evidence, but not a proven student backend | Hardware prerequisite is named in profiles; no dedicated student block | **infrastructure only / justified student-vocabulary exclusion** at current evidence; reopen only for a concrete pupil-facing downward-clearance objective |
| Flow Deck V2 optical flow / stabilization | Flow Deck V2 | No direct student primitive by design | Used as simulation/flight infrastructure, not as an algorithm block | Physical behavior belongs to backend/safety validation | Implicit hardware requirement | **infrastructure only**; do not expose estimator/flow internals without a pedagogical need |
| Multi-ranger upward range | Multi-ranger deck | Generic AST already admits `up` | Current WWI backend advertises and reads `up` through a dedicated upward Webots distance sensor | Physical student backend not proven | Broad reactive profile declares `up` | **covered** in simulation; **physical unproven** |
| Bottom Color LED Deck light/color | Bottom-mounted Color LED Deck | `webeeblocks_v2_light` → `set_light(color)` with a bounded generic palette | Runtime v2 exposes the action through WWI and a simple bottom-mounted RGB LED surface on the reference Crazyflie model | Physical student backend not proven | Broad reactive profile only | **covered** in simulation for the generic light/color intent; **physical unproven** |
| Estimator diagnostics / tuning | Crazyflie 2.1 firmware/estimator infrastructure, informed by attached deck sensors | No student vocabulary | Internal only | #70 Lab/research only | None | **infrastructure only** by product rule |

## Conclusions for #157

The currently justified student-facing generic Runtime surface is now covered in
simulation: takeoff/land, four-way horizontal movement, vertical movement, yaw,
wait/pacing, bounded speed selection, Multi-ranger
`front/back/left/right/up`, and the generic bottom Color LED light/color intent.
There is therefore no default #157 simulation primitive/backend backlog remaining.

Flow Deck downward ToF remains a deliberate infrastructure-only exclusion at
current product evidence. No current activity has a pupil-facing
downward-clearance learning objective, while #70 uses that signal for estimator
and safety research. Do not add `range(down)` merely for hardware completeness;
reopen the vocabulary only when a concrete activity demonstrates that need.

Color LED simulation uses one generic light/color action and a simple
bottom-mounted controllable RGB surface. It deliberately models the observable
student effect rather than deck electronics.

The substantive remaining #157 boundary is physical-backend continuity/proof.
Physical support remains explicitly unproven for student execution. Do not turn
source availability, Lab firmware experiments, or simulation coverage into a
real-hardware support claim. The eventual physical backend must preserve the
same backend-neutral AST intent and independent preflight/safety boundary.

This inventory should be updated only when integrated product evidence changes a
row; live PR/CI/review state remains on GitHub rather than in this document.
