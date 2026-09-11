# Reference Crazyflie capability matrix

This matrix records the **currently integrated** student-facing capability surface
for the reference hardware in issue #157. It is a product inventory, not a
workflow-state database and not a claim that a physical backend is already
qualified on real hardware.

Status vocabulary:

- **covered** — the generic Blockly/AST intent and the current Webots execution
  path both support the capability;
- **partial** — generic semantics exist, but the current Webots backend exposes
  only part of the intended hardware surface;
- **missing** — no current student-facing generic semantics/Webots behavior
  exists;
- **infrastructure only** — the capability is useful internally but is not a
  student-facing primitive;
- **physical deterministic path** — a trusted host execution path is integrated
  and deterministically exercised through fake/injected hardware seams, but no
  real-device qualification follows from that evidence;
- **physical unproven** — no current integrated evidence establishes the
  corresponding real-Crazyflie student execution path.

| Reference capability | Hardware source | Generic Blockly / AST | Current Webots path | Physical path | Current profile exposure | Status / smallest gap |
| --- | --- | --- | --- | --- | --- | --- |
| Take off / land | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_takeoff`, `webeeblocks_v2_land` → `takeoff`, `land` | Current WWI backend advertises and implements both actions | Integrated #276/#308 trusted-host composition consumes the exact teacher-bound takeoff and exact terminal land from one canonical program. Takeoff uses the one-shot acknowledged command path and terminal landing uses controlled command 10 plus fresh #264 completion to `INACTIVE`. This path is deterministically tested with injected hardware seams; it is not real-flight qualification. | Progression 1+ | **covered** in simulation; **physical deterministic path** integrated for the exact supported program envelope; real-device qualification remains unproven |
| Horizontal movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_move` → `move(direction, distance)` with forward/back/left/right AST vocabulary | Current WWI backend advertises and executes forward/back/left/right | Integrated #276 trusted-host execution derives only the exact next horizontal move from the teacher-bound AST, composes fresh yaw with #256/#268 semantics and the shared authority/safety domains, and requires causal acknowledged completion before sequence advance. Deterministic injected-hardware evidence exists; no real-flight qualification is claimed. | Progression 1: forward; progression 3: forward/left; broader reactive profile declares four directions | **covered** in simulation; **physical deterministic path** integrated for exact horizontal move; real-device qualification remains unproven |
| Vertical movement | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_vertical` → `vertical(up/down, distance)` | Current WWI backend advertises and executes up/down with horizontal-position/yaw hold and bounded altitude targets | Exact-AST vertical/capability preflight and pure #256 world-Z semantics are integrated, but the current exact physical-program sequencer intentionally accepts only move/turn between takeoff and terminal land. No vertical physical effect consumer is integrated. | Broad reactive profile only | **covered** in simulation; **physical unproven** — trusted vertical execution remains outside the current effect envelope |
| Yaw turn | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_turn` → `turn(angle)` | Current WWI backend advertises and executes bounded signed yaw turns while holding position/altitude | Integrated #276 trusted-host execution derives only the exact next turn from the canonical AST, applies #268 timing and the shared authority/safety/completion path, and advances only after causal completion. Deterministic injected-hardware evidence exists; no real-flight qualification is claimed. | Broad reactive profile only | **covered** in simulation; **physical deterministic path** integrated for exact yaw turn; real-device qualification remains unproven |
| Wait / pacing | Generic Runtime timing semantic; no dedicated hardware source | `webeeblocks_v2_wait` → `wait(seconds)` | Current WWI backend advertises and executes bounded waits while holding position, altitude and yaw; real-Webots CI checks requested simulated duration and hold tolerances | Exact-AST action/capability preflight is integrated, but `wait` is not in the current trusted physical-program execution envelope. | Broad reactive profile only | **covered** in simulation; **physical unproven** — define a trusted no-effect/hold semantic only if a physical activity needs it |
| Speed selection | Crazyflie 2.1 airframe / flight control | `webeeblocks_v2_speed` → `set_speed(speed)` | Webots Runtime v2 applies a bounded 0.1–0.35 m/s limit to subsequent horizontal `move` actions only; RESET restores the proven 0.35 m/s default; real-Webots CI compares slow/fast traversal causally | #268 supplies the pure physical timing policy used by the trusted motion transport, but the current exact physical-program sequencer does not consume a student `set_speed` statement. | Broad reactive profile only | **covered** in simulation inside the existing proven horizontal envelope; **physical unproven** as a student-program statement |
| Multi-ranger directional distance | Multi-ranger deck | `webeeblocks_v2_range` → `range(direction)`; AST vocabulary has front/back/left/right/up | Current WWI backend advertises and reads front/back/left/right/up through dedicated Webots sensors | Exact-AST range/capability preflight is integrated and optional deck requirements are intent-dependent, but no trusted physical student range-value execution path is integrated. | Progression 3 exposes front; broad reactive profile declares front/back/left/right/up | **covered** in simulation for the generic directional range vocabulary; **physical unproven** |
| Flow Deck V2 downward range | Flow Deck V2 | No `down` value exists in the current student range AST vocabulary | Downward ranging/flow is robot infrastructure rather than a student-visible Runtime v2 range direction | #70 contains physical research evidence, but not a proven student backend | Hardware prerequisite is named in profiles; no dedicated student block | **infrastructure only / justified student-vocabulary exclusion** at current evidence; reopen only for a concrete pupil-facing downward-clearance objective |
| Flow Deck V2 optical flow / stabilization | Flow Deck V2 | No direct student primitive by design | Used as simulation/flight infrastructure, not as an algorithm block | Physical behavior belongs to backend/safety validation | Implicit hardware requirement | **infrastructure only**; do not expose estimator/flow internals without a pedagogical need |
| Multi-ranger upward range | Multi-ranger deck | Generic AST already admits `up` | Current WWI backend advertises and reads `up` through a dedicated upward Webots distance sensor | Exact-AST range/capability preflight is integrated and checks `up` only when the submitted program requires it; no trusted physical student read path is integrated. | Broad reactive profile declares `up` | **covered** in simulation; **physical unproven** |
| Bottom Color LED Deck light/color | Bottom-mounted Color LED Deck | `webeeblocks_v2_light` → `set_light(color)` with a bounded generic palette | Runtime v2 exposes the action through WWI on an attached bottom-deck envelope with side-visible diffuser and LED-driven nearby halo; fixed top/three-quarter/side R2025a render evidence is integrated | Exact-AST preflight requires the LED capability only when the submitted program uses `set_light`; no trusted physical student LED effect path is integrated. | Broad reactive profile only | **covered** in simulation for the generic light/color intent; **physical unproven** |
| Estimator diagnostics / tuning | Crazyflie 2.1 firmware/estimator infrastructure, informed by attached deck sensors | No student vocabulary | Internal only | #70 Lab/research only | None | **infrastructure only** by product rule |

## Conclusions for #157

The currently justified student-facing generic Runtime surface is covered in
simulation: takeoff/land, four-way horizontal movement, vertical movement, yaw,
wait/pacing, bounded speed selection, Multi-ranger `front/back/left/right/up`,
and the generic bottom Color LED light/color intent. There is therefore no
default #157 simulation primitive/backend backlog remaining.

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

The physical boundary is now split explicitly between **integrated deterministic
host execution** and **real-device qualification / broader capability
continuity**. Integrated #276 and #308 establish one trusted, parameter-free
production-host execution chain for the currently supported exact program
envelope:

`takeoff -> zero or more horizontal move/turn effects -> terminal land`.

The host owns the live Crazyradio session and the #278/#249 current-program
bridge. The exact teacher-authorized canonical AST and reconnect-sensitive epoch
are re-asserted at effect boundaries; the browser-held capability bearer remains
non-authority. #266/#262 provide the powered-session/watchdog lifecycle, #267 the
exact-run teacher receipt, #257 fresh supervisor state, #260 accepted yaw where
horizontal motion needs it, #256/#268 geometry/timing, #272 SafeLink readiness,
#271 acknowledgement freshness, #273 process-wide reset/effect exclusion and
#279 causal accepted-effect completion. The external caller still supplies no
motion, landing parameters, provenance token, raw packet or retry decision.

Within that chain, an accepted effect is not treated as complete merely because a
packet was sent or acknowledged. Horizontal move/turn require causally fresh
completion before the exact-program cursor advances. Integrated #308 adds the
normal terminal controlled landing path: command 10 is derived only from the
exact terminal land in the same teacher-bound program, current-program provenance
is reconstructed again after potentially blocking pre-land observations, one
plain no-retry send is acknowledged, and fresh #264 same-epoch finished,
non-flying, high-level-inactive evidence is required before #273 becomes
`INACTIVE` and the exact program completes. Definitive rejection does not advance
the sequence; ambiguous emission or completion poisons ordinary continuation.

This is meaningful physical-backend product implementation, but it is **not a
real-flight qualification claim**. The trusted transport and host composition are
deterministically exercised through fake/injected-hardware seams. Do not infer
from those tests that the supported envelope has passed safe motorized execution
on the reference Crazyflie.

The broader #157 continuity boundary therefore begins after that exact supported
envelope. Vertical student motion, physical `wait`/pacing, student `set_speed`
statements, Multi-ranger value reads and Color LED effects do not yet have an
integrated trusted physical student execution/read path. Add such slices only
when they preserve the backend-neutral student intent and are justified by the
pedagogical/product graph; do not expand the physical vocabulary merely for
hardware completeness.

Real-device qualification of the already integrated takeoff + horizontal
move/turn + terminal-land envelope also remains separate. Any future physical
checkpoint must be prepared under the repository's human-checkpoint contract and
must not be inferred from CI, source inspection, simulation, injected-hardware
tests or #70 Lab evidence. #70 remains the dedicated estimator research boundary
for world-altitude behavior over surface-height discontinuities and must not be
silently promoted into #157 product proof.

The normal cflib close path still emits its documented safety-zero commander
setpoint, so transport-level packet emission is not claimed read-only. Stock
CF2.1 auto-arming can return the vehicle to ReadyToFly after the landing/reset
cycle, so post-landing disarm is not a persistent teacher/safety gate; every
later flight-capable run still requires fresh exact preflight and a new explicit
teacher authorization. Immediate emergency stop and high-level commander stop
remain exceptional motor-cut paths, not normal Stop/Land semantics.

Do not turn source availability, Lab firmware experiments, preflight
compatibility, simulation coverage or deterministic injected-hardware execution
evidence into a stronger real-hardware support claim.

This inventory should be updated only when integrated product evidence changes a
row; live PR/CI/review state remains on GitHub rather than in this document.
