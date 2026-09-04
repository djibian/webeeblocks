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
| Horizontal movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_move` → `move(direction, distance)` with forward/back/left/right AST vocabulary | Current WWI backend advertises only forward/left | Physical student backend not proven | Progression 1: forward; progression 3: forward/left; broader reactive profile declares four directions | **partial**: Webots backend must close back/right before claiming full generic coverage |
| Vertical movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_vertical` → `vertical(up/down, distance)` | Current WWI backend explicitly rejects vertical execution | Physical student backend not proven | Broad reactive profile only | **partial/missing execution** |
| Yaw turn | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_turn` → `turn(angle)` | Current WWI backend explicitly rejects turn execution | Physical student backend not proven | Broad reactive profile only | **partial/missing execution** |
| Wait / pacing | Generic Runtime timing semantic; no dedicated hardware source | `webeeblocks_v2_wait` → `wait(seconds)` | Current WWI backend explicitly rejects wait execution | Physical student backend not proven | Broad reactive profile only | **partial/missing execution** |
| Speed selection | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_speed` → `set_speed(speed)` | Current WWI backend explicitly rejects speed execution | Physical student backend not proven | Broad reactive profile only | **partial/missing execution** |
| Multi-ranger directional distance | Multi-ranger deck | `webeeblocks_v2_range` → `range(direction)`; AST vocabulary has front/back/left/right/up | Current WWI backend advertises front/left/right | Physical student backend not proven | Progression 3 exposes front; broad reactive profile declares front/back/left/right/up | **partial**: horizontal front/left/right is covered in Webots; back/up remain outside the current backend |
| Flow Deck V2 downward range | Flow Deck V2 | No `down` value exists in the current student range AST vocabulary | Downward ranging/flow is robot infrastructure rather than a student-visible Runtime v2 range direction | #70 contains physical research evidence, but not a proven student backend | Hardware prerequisite is named in profiles; no dedicated student block | **missing** as a student-facing capability; decide whether downward range has a real pedagogical use before adding vocabulary |
| Flow Deck V2 optical flow / stabilization | Flow Deck V2 | No direct student primitive by design | Used as simulation/flight infrastructure, not as an algorithm block | Physical behavior belongs to backend/safety validation | Implicit hardware requirement | **infrastructure only**; do not expose estimator/flow internals without a pedagogical need |
| Multi-ranger upward range | Multi-ranger deck | Generic AST already admits `up` | Current WWI backend does not advertise `up` | Physical student backend not proven | Broad reactive profile declares `up` | **partial** |
| Bottom Color LED Deck light/color | Bottom-mounted Color LED Deck | No current block, AST statement, interpreter action or backend capability | No integrated controllable light surface found | Physical student backend not proven | None | **missing**: smallest coherent future slice is one generic color/light intent plus a simple visible bottom-deck Webots surface |
| Estimator diagnostics / tuning | Crazyflie 2.1 firmware/estimator infrastructure, informed by attached deck sensors | No student vocabulary | Internal only | #70 Lab/research only | None | **infrastructure only** by product rule |

## Conclusions for #157

The generic AST already covers more motion and ranging intent than the current
Webots WWI backend advertises. The next capability work should therefore prefer
**closing existing generic simulation gaps before adding block families**.

Two genuine vocabulary decisions remain visible:

1. whether Flow Deck downward range is pedagogically useful enough to justify a
   generic student-facing `down` range direction;
2. the Color LED Deck, which currently has no student-facing semantics at all
   and should be added later as a small generic light/color capability rather
   than deck-specific electronics controls.

Physical support remains explicitly unproven for student execution. Do not turn
source availability, Lab firmware experiments, or simulation coverage into a
real-hardware support claim. The eventual physical backend must preserve the
same backend-neutral AST intent and independent preflight/safety boundary.

This inventory should be updated only when integrated product evidence changes a
row; live PR/CI/review state remains on GitHub rather than in this document.
