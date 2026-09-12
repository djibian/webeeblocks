# Reference Crazyflie capability matrix

This matrix records the **currently integrated** student-facing capability surface
for the reference hardware in issue #157. It is a product inventory, not a
workflow-state database and not a claim that deterministic host integration is
already real-device qualification.

Status vocabulary:

- **covered** — the generic Blockly/AST intent and the current Webots execution
  path both support the capability;
- **partial** — generic semantics exist, but the current Webots backend exposes
  only part of the intended hardware surface;
- **missing** — no current student-facing generic semantics/Webots behavior
  exists;
- **infrastructure only** — the capability is useful internally but is not a
  student-facing primitive;
- **deterministic physical path integrated** — the trusted physical-host execution
  path is covered by deterministic fake/injected-hardware regressions, but no
  corresponding real-device qualification is claimed;
- **physical unproven** — no current integrated evidence establishes the
  corresponding student physical execution path.

| Reference capability | Hardware source | Generic Blockly / AST | Current Webots path | Physical path | Current profile exposure | Status / smallest gap |
| --- | --- | --- | --- | --- | --- | --- |
| Take off / land | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_takeoff`, `webeeblocks_v2_land` → `takeoff`, `land` | Current WWI backend advertises and implements both actions | Exact-AST live capability/preflight is integrated. The trusted host deterministically composes causal takeoff and exact terminal command-10 landing through the same teacher/session/watchdog/supervisor/SafeLink/acknowledgement/exclusion authority domain; accepted landing completes only after fresh same-epoch non-flying/high-level-inactive evidence. This is fake/injected-hardware proof, not real-flight qualification | Progression 1+ | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Horizontal movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_move` → `move(direction, distance)` with forward/back/left/right AST vocabulary | Current WWI backend advertises and executes forward/back/left/right | Exact-AST preflight plus trusted host-owned one-shot SETPOINT_HL effect execution is integrated for the exact next teacher-bound horizontal move after causal takeoff. Fresh current-program provenance, yaw, SafeLink, acknowledgement and causal completion remain required. No real-device qualification is claimed | Progression 1: forward; progression 3: forward/left; broader reactive profile declares four directions | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Vertical movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_vertical` → `vertical(up/down, distance)` | Current WWI backend advertises and executes up/down with horizontal-position/yaw hold and bounded altitude targets | Integrated #333 admits the exact teacher-bound vertical statement into the trusted physical sequence, eagerly validates the complete nominal-altitude path inside 0.2–1.5 m before flight, emits one relative-world-Z SETPOINT_HL GO_TO through the existing authority/acknowledgement/completion chain, and advances nominal altitude only after definitive completion. The host-owned vertical timing policy has a fixed 0.5 m/s peak ceiling independent of student horizontal `set_speed`; terminal command-10 descent follows the completed final nominal altitude. No real-device qualification is claimed | Broad reactive profile only | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Yaw turn | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_turn` → `turn(angle)` | Current WWI backend advertises and executes bounded signed yaw turns while holding position/altitude | Exact-AST preflight plus trusted host-owned one-shot SETPOINT_HL effect execution is integrated for the exact next teacher-bound yaw turn after causal takeoff, with the same authority, acknowledgement and completion boundaries as horizontal motion. No real-device qualification is claimed | Broad reactive profile only | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Wait / pacing | Generic Runtime timing semantic; no dedicated hardware source | `webeeblocks_v2_wait` → `wait(seconds)` | Current WWI backend advertises and executes bounded waits while holding position, altitude and yaw; real-Webots CI checks requested simulated duration and hold tolerances | Exact-AST action/capability preflight is integrated. Integrated #316 admits exact teacher-bound `wait(seconds)` only inside the established takeoff/land envelope with its 0.1–5.0 s semantic bounds validated before takeoff. The ordinary host caller cannot supply duration, cursor or completion; host-monotonic pacing emits no cflib/CRTP/SETPOINT_HL, commander, reset or acknowledgement effect, keeps the powered session/watchdog and connection epoch live, re-establishes current-program provenance before and after the wait, and advances the exact action cursor only after completion. This is fake/injected-hardware proof, not real-device qualification | Broad reactive profile only | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Speed selection | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_speed` → `set_speed(speed)` | Webots Runtime v2 applies a bounded 0.1–0.35 m/s limit to subsequent horizontal `move` actions only; RESET restores the proven 0.35 m/s default; real-Webots CI compares slow/fast traversal causally | Integrated #322/#320 consumes the exact teacher-bound `set_speed` statement as per-run host-local no-effect state inside the proven 0.10–0.35 m/s physical envelope. Out-of-envelope values reject the complete physical program before takeoff; the speed step emits no cflib/CRTP/SETPOINT_HL, commander, reset or acknowledgement transaction and changes only later horizontal-move timing. Turn, takeoff, landing and vertical timing remain independent. No real-device qualification is claimed | Broad reactive profile only | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Multi-ranger directional distance | Multi-ranger deck | `webeeblocks_v2_range` → `range(direction)`; AST vocabulary has front/back/left/right/up | Current WWI backend advertises and reads front/back/left/right/up through dedicated Webots sensors | Integrated fresh same-epoch observation, reset/effect exclusion, conservative dynamic preflight and #362 trusted-host composition derive each range demand only from the exact teacher-bound shared interpreter. Valid firmware millimetres below 8000 are converted to metres exactly once; unavailable/stale/ambiguous samples fail closed. The range value remains non-authority data, while every later interpreter-selected effect reconstructs its existing teacher/session/watchdog/current-program/acknowledgement/completion authority. No real-device qualification is claimed | Progression 3 exposes front; broad reactive profile declares front/back/left/right/up | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Flow Deck V2 downward range | Flow Deck V2 | No `down` value exists in the current student range AST vocabulary | Downward ranging/flow is robot infrastructure rather than a student-visible Runtime v2 range direction | #70 contains physical research evidence, but not a proven student backend | Hardware prerequisite is named in profiles; no dedicated student block | **infrastructure only / justified student-vocabulary exclusion** at current evidence; reopen only for a concrete pupil-facing downward-clearance objective |
| Flow Deck V2 optical flow / stabilization | Flow Deck V2 | No direct student primitive by design | Used as simulation/flight infrastructure, not as an algorithm block | Physical behavior belongs to backend/safety validation | Implicit hardware requirement | **infrastructure only**; do not expose estimator/flow internals without a pedagogical need |
| Multi-ranger upward range | Multi-ranger deck | Generic AST already admits `up` | Current WWI backend advertises and reads `up` through a dedicated upward Webots distance sensor | The integrated trusted-host range path accepts interpreter-derived `up` exactly like the other Multi-ranger directions, with fresh same-epoch observation, exact current-program provenance, no caller-selected direction/value and no effect authority minted by the sample. No real-device qualification is claimed | Broad reactive profile declares `up` | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Bottom Color LED Deck light/color | Bottom-mounted Color LED Deck | `webeeblocks_v2_light` → `set_light(color)` with a bounded generic palette | Runtime v2 exposes the action through WWI on an attached bottom-deck envelope with side-visible diffuser and LED-driven nearby halo; fixed top/three-quarter/side R2025a render evidence is integrated | Integrated #341 consumes the exact next teacher-bound `set_light(color)` through a narrow one-shot `colorLedBot.wrgb8888` PARAM effect inside the existing session/teacher/watchdog/SafeLink/current-program/exclusion boundary. It requires a same-epoch causal freshness fence, exact write echo and direct exact-value readback before returning to `FLYING`; rejected/unemitted effects remain retryable only when no effect occurred, while uncertain emitted outcomes are terminal/recovery-required. No generic parameter-write API or real-device qualification is claimed | Broad reactive profile only | **covered** in simulation; **deterministic physical path integrated; real-device unproven** |
| Estimator diagnostics / tuning | Crazyflie 2.1 firmware/estimator infrastructure, informed by attached deck sensors | No student vocabulary | Internal only | #70 Lab/research only | None | **infrastructure only** by product rule |

## Conclusions for #157

The currently justified student-facing generic Runtime surface is covered in
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

The physical boundary is no longer uniformly “unproven.” Integrated
#193/#196/#238/#241/#243/#244/#246/#249 establish fresh exact-AST live capability
and connection-epoch evidence. Integrated #256/#257/#260 establish the pure
movement transform plus fresh supervisor/yaw observations. Integrated
#262/#264/#266/#267/#268/#271/#272/#273/#278/#279/#283 provide the reusable
powered-session, teacher, watchdog, SafeLink, acknowledgement, effect-exclusion,
current-program and completion trust chain. Integrated #295 binds the exact
teacher-authorized program sequence. #276 then consumes the exact next horizontal
move or yaw turn through one no-retry SETPOINT_HL effect after causal takeoff,
#305/#308 extend that same host-owned sequence through exact terminal controlled
landing and fresh non-flying completion, #316 admits exact teacher-bound bounded
waits as no-effect host-monotonic sequence steps, #322/#320 adds exact per-run
horizontal speed state without emitting a physical effect, #333 adds bounded
relative-world-Z vertical effects with eager nominal-altitude validation and
terminal landing descent derived from the completed final nominal altitude, #341
adds exact bottom Color LED effects through one-shot PARAM write plus same-epoch
freshness and direct readback, and #362 composes the existing fresh Multi-ranger
observer with the exact teacher-bound shared Runtime interpreter and all-reachable
physical preflight inside the production trusted host. Range-selected control
flow remains interpreter-owned and every resulting effect retains its independent
authority/acknowledgement/completion boundary.

The currently integrated deterministic physical execution envelope is therefore:
trusted reset/postconditions and reconnect-sensitive preflight -> exact-run teacher
authorization -> watchdog activation/liveness -> causal takeoff -> zero or more
exact interpreter-selected observations/no-effect state transitions and trusted
horizontal move/yaw-turn/vertical/bottom-light effects -> exact terminal
controlled landing from the trusted final nominal altitude -> fresh same-epoch
finished/non-flying/high-level-inactive completion. Multi-ranger observations are
fresh same-epoch non-authority data under the process-wide reset/effect exclusion;
branch/repeat/variable progression stays inside the shared interpreter. Every
effect boundary and no-effect step reconstructs the required host-owned authority/
provenance; caller-selected sensor/motion/light parameters, speed/wait values,
branch/cursor/completion or caller-returned provenance do not become authority.
Ambiguous observation, acknowledgement, transport, completion or lifecycle state
remains fail-closed rather than authorizing a retry or later effect.

That result is deterministic fake/injected-hardware integration evidence only.
It does **not** qualify real flight or real-device performance. The available
real-device evidence from the superseded #226 checkpoint established only bounded
hardware identity/presence observations and cannot be reused as execution
qualification. In particular, the deterministic Multi-ranger and bottom Color LED
paths are integrated but remain real-device unqualified.

#70 remains the separate Lab path for world-altitude behavior over surface-height
discontinuities. Its estimator evidence must not be promoted into #157 execution
support, and the current evidence authorizes no motorized checkpoint. #72 remains
gated on representative proven physical continuity for the capabilities selected
by the final real-flight activity.

There is no remaining currently justified generic student capability gap in the
deterministic simulation↔physical architecture. The substantive remaining #157
boundary is representative real-device qualification beyond that integrated
deterministic envelope. Keep that qualification separate from deterministic
composition proof; do not invent another Blockly/AST/backend slice merely to keep
#157 active.

Do not turn source availability, Lab firmware experiments, preflight
compatibility, simulation coverage or deterministic host regressions into a
real-hardware support claim.

This inventory should be updated only when integrated product evidence changes a
row; live PR/CI/review state remains on GitHub rather than in this document.
