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
| Take off / land | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_takeoff`, `webeeblocks_v2_land` → `takeoff`, `land` | Current WWI backend advertises and implements both actions | Exact-AST physical requirement/preflight checking is integrated; physical student execution authority/path is not proven | Progression 1+ | **covered** in simulation; **physical unproven** |
| Horizontal movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_move` → `move(direction, distance)` with forward/back/left/right AST vocabulary | Current WWI backend advertises and executes forward/back/left/right | Exact-AST movement/capability preflight is integrated; physical student execution authority/path is not proven | Progression 1: forward; progression 3: forward/left; broader reactive profile declares four directions | **covered** in simulation for the generic horizontal vocabulary; **physical unproven** |
| Vertical movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_vertical` → `vertical(up/down, distance)` | Current WWI backend advertises and executes up/down with horizontal-position/yaw hold and bounded altitude targets | Exact-AST vertical/capability preflight is integrated; physical student execution authority/path is not proven | Broad reactive profile only | **covered** in simulation for the generic vertical vocabulary; **physical unproven** |
| Yaw turn | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_turn` → `turn(angle)` | Current WWI backend advertises and executes bounded signed yaw turns while holding position/altitude | Exact-AST action/capability preflight is integrated; physical student execution authority/path is not proven | Broad reactive profile only | **covered** in simulation for the generic yaw-turn vocabulary; **physical unproven** |
| Wait / pacing | Generic Runtime timing semantic; no dedicated hardware source | `webeeblocks_v2_wait` → `wait(seconds)` | Current WWI backend advertises and executes bounded waits while holding position, altitude and yaw; real-Webots CI checks requested simulated duration and hold tolerances | Exact-AST action/capability preflight is integrated; physical student execution authority/path is not proven | Broad reactive profile only | **covered** in simulation; **physical unproven** |
| Speed selection | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_speed` → `set_speed(speed)` | Webots Runtime v2 applies a bounded 0.1–0.35 m/s limit to subsequent horizontal `move` actions only; RESET restores the proven 0.35 m/s default; real-Webots CI compares slow/fast traversal causally | Exact-AST action/capability preflight is integrated; physical student execution authority/path is not proven | Broad reactive profile only | **covered** in simulation inside the existing proven horizontal envelope; **physical unproven** |
| Multi-ranger directional distance | Multi-ranger deck | `webeeblocks_v2_range` → `range(direction)`; AST vocabulary has front/back/left/right/up | Current WWI backend advertises and reads front/back/left/right/up through dedicated Webots sensors | Exact-AST range/capability preflight is integrated and optional deck requirements are intent-dependent; physical student execution authority/path is not proven | Progression 3 exposes front; broad reactive profile declares front/back/left/right/up | **covered** in simulation for the generic directional range vocabulary; **physical unproven** |
| Flow Deck V2 downward range | Flow Deck V2 | No `down` value exists in the current student range AST vocabulary | Downward ranging/flow is robot infrastructure rather than a student-visible Runtime v2 range direction | #70 contains physical research evidence, but not a proven student backend | Hardware prerequisite is named in profiles; no dedicated student block | **infrastructure only / justified student-vocabulary exclusion** at current evidence; reopen only for a concrete pupil-facing downward-clearance objective |
| Flow Deck V2 optical flow / stabilization | Flow Deck V2 | No direct student primitive by design | Used as simulation/flight infrastructure, not as an algorithm block | Physical behavior belongs to backend/safety validation | Implicit hardware requirement | **infrastructure only**; do not expose estimator/flow internals without a pedagogical need |
| Multi-ranger upward range | Multi-ranger deck | Generic AST already admits `up` | Current WWI backend advertises and reads `up` through a dedicated upward Webots distance sensor | Exact-AST range/capability preflight is integrated and checks `up` only when the submitted program requires it; physical student execution authority/path is not proven | Broad reactive profile declares `up` | **covered** in simulation; **physical unproven** |
| Bottom Color LED Deck light/color | Bottom-mounted Color LED Deck | `webeeblocks_v2_light` → `set_light(color)` with a bounded generic palette | Runtime v2 exposes the action through WWI on an attached bottom-deck envelope with side-visible diffuser and LED-driven nearby halo; fixed top/three-quarter/side R2025a render evidence is integrated | Exact-AST preflight requires the LED capability only when the submitted program uses `set_light`; physical student execution authority/path is not proven | Broad reactive profile only | **covered** in simulation for the generic light/color intent; **physical unproven** |
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

Color LED simulation uses one generic light/color action and an integrated
bottom-mounted deck representation with a side-visible diffuser and nearby
LED-driven halo. Fixed R2025a top, three-quarter and side renders exercise the
real `color_led` device and gate that normal-view color visibility without
modeling deck electronics or photometric fidelity.

The substantive remaining #157 boundary is physical-backend continuity/proof.
The integrated physical preflight core derives required actions, range sensors
and movement/vertical capabilities from the exact submitted backend-neutral AST,
keeps optional deck requirements intent-dependent, and produces a canonical
non-authority AST binding that later code can verify before
authorization/submission. The host-side read-only probe now also exposes a
persistent `ReadOnlyCapabilitySession`: it opens one explicit Crazyradio URI,
waits for the connected parameter snapshot, creates an opaque epoch only after
the link is live, invalidates that epoch from cflib's disconnect callback, and
creates each descriptor read from the current connected evidence instead of
caching an earlier descriptor object. Reopening therefore rotates the epoch, and
a disconnect makes both epoch and capability reads fail closed. The session
exposes no WebeeBlocks movement, light, arming or setpoint method and retains the
documented cflib safety-zero close-path qualification.

This still is not execution authority or a complete physical backend. Integrated
#249 connects the production physical-submission path to that live host session:
the exact current activity profile and backend-neutral workspace AST are
preflighted against fresh live capability evidence, then both semantic
requirements and the reconnect-sensitive connection epoch are re-asserted
immediately before any later separately authorized physical effect. Workspace,
profile or connection changes invalidate the prior binding. The bridge remains
non-authority and exposes no WebeeBlocks flight command API.

The remaining #157 boundary therefore begins after that validated pre-effect
assertion: a separately authorized physical effect consumer with explicit teacher
authorization before any flight-capable command/effect, firmware-independent
arming semantics (stock brushed Crazyflie 2.1 auto-arms when pre-flight checks
pass), an independent emergency-stop watchdog/liveness guard, controlled normal
land/disarm behavior and proof of real execution continuity. Integrated #256 now codifies the non-authority semantic transform for the
future direct cflib HighLevelCommander path: body-relative horizontal movement is
rotated into world-frame displacement from an accepted yaw, vertical intent stays
relative world-Z and turns stay relative yaw. That adapter imports no cflib API
and emits no command, so physical execution authority remains unproven. A later
effect consumer still must supply the accepted live yaw and bound normal command
completion by fresh supervisor/high-level trajectory state rather than host-side
sleep alone. Immediate emergency stop and high-level commander stop remain
exceptional motor-cut paths, not normal Stop/Land semantics.

Do not turn source availability, Lab firmware experiments, preflight
compatibility, simulation coverage or this implementation direction into a
real-hardware support claim.

This inventory should be updated only when integrated product evidence changes a
row; live PR/CI/review state remains on GitHub rather than in this document.
