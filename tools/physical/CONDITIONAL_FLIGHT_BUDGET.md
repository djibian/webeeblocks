# #157 — quantitative evidence boundary for uniform-floor flight

**Status: preparation only. Physical qualification is UNPROVEN.** This protocol
does not request a checkpoint, authorize a motor, flash a device or supply a
real-world measurement. It remains subordinate to AGENTS.md V5, the teacher
decision, the physical comparison proposal, the owner, and the trusted
TEST_REQUIRED mechanism. It does not reopen #70 or affect #587.

## What is already established, and what is not

- #583: conservative one-shot ground Multi-ranger admission for directions
  demanded by the exact AST, causal PARAM read and confirmed same-epoch LOG
  deletion. This does **not** prove producer age, clearance, or future readings.
- #584: the exact short hover .wbb/AST, retention of the first available or
  unavailable in-flight raw value and nonblocking in-flight range reporting.
  The host's other diagnostic sinks have not all been qualified against stalls.
- #585/#586/#596: wait-time caller-loss observation, a one-shot teacher ABANDON
  through existing caller IPC, terminal teardown ownership and a saturated
  socket regression. An observed 50-ms pacing slice is **not** an upper bound on
  operator gesture → landing, ACK, radio effect, or operating-system scheduling.
- Historical #566: one unavailable in-flight front return, 32766, with no
  independent scene geometry; #572/#580: 200 finite stationary readings in a
  retained archive, but the procedure was FAIL. These do not establish a motor
  effect or a reproducible reliability rate.

**Missing physical bounds**: front sensor visibility and producer freshness
under thrust; maximum horizontal and vertical excursions including terminal
recovery; attitude and rotor swept volume; a lower bound on achievable
deceleration under adverse conditions; maximum time from operator intent to
deceleration and motor-off; and minimum usable endurance for the *exact*
battery/deck/payload/environment configuration. The simulation-only 210 s
Grand Prix limit is a game rule, not an energy or real-flight bound.

The shortest sensor discriminator remains the separately proposed fixed-scene,
uniform-floor 0.50 m hover, wait, single front read, land, with the same exact
.wbb/AST and independently witnessed geometry. It **cannot** run until the
separate operator, physical envelope and containment prerequisites are met and
the owner authorizes an exact checkpoint. A props-off repetition of #572 is not
the missing thrust-conditioned discriminator.

## Conditional, offline arithmetic — never a flight gate

Run, **only after the independent bounds actually exist**:

`python3 tools/physical/conditional_flight_budget.py offline-bounds.json`

The input contains exactly `source_sha` (40 lowercase hex),
`ast_sha256` (64 lowercase hex) and `bounds`. The eleven required bound
entries each contain exactly `value` (finite number in its documented units)
and `evidence_sha256` (lowercase digest of an independently retained source).
Duplicate JSON keys at **any depth** are refused (including repeated bound
values or source identifiers). Input decimal literals are interpreted exactly
for conditional arithmetic. Direct Python API calls with binary `float` bounds
retain their exact binary values rather than a possibly optimistic shortened
decimal reinterpretation. Units are required by the field contract but cannot
be authenticated or converted from independent measurements by this tool. The displayed travel allowance is rounded
**upward**, while both displayed margins are rounded **downward**. The CLI
publishes each outward-rounded binary value as its **exact decimal expansion**
in an unquoted JSON numeric token: the shorter decimal representation from
ordinary float JSON serialization would not always preserve these inequalities.
Check published margins as decimal numbers, not by re-rounding them to binary
float. Unrepresentable bounds and nonfinite derived outputs are refused. These arithmetic safeguards
cannot make an unmeasured physical envelope reliable.

This tool checks only witness identifiers' *syntax*, not whether a source is
real or its measurement justifies a bound. A digest copied or invented by an
agent is **not** evidence. No example numbers in this document are measurements.

| Bound name | Unit and required meaning |
| --- | --- |
| `distance_to_hazard_m` | Positive, independently measured shortest free distance toward the nearest target, enclosure or hazard |
| `prior_horizontal_excursion_m` | Nonnegative worst-case radial position/tracking allowance before an abort begins |
| `rotor_radius_m` | Positive swept rotor/body allowance including physical extent |
| `geometry_uncertainty_m` | Nonnegative upper uncertainty for placement and witnesses |
| `max_hazard_approach_speed_m_s` | Nonnegative supported upper approach speed, not just a nominal set_speed |
| `max_abort_to_deceleration_s` | Supported upper time from actual gesture/trigger to effective deceleration, including host/IPC/ACK delays |
| `min_supported_deceleration_m_s2` | **Positive physical lower bound** throughout the applicable deceleration domain, not a planner command |
| `endurance_lower_bound_s` | Positive conservative minimum *motor-on* endurance under the exact flight configuration and battery acceptance domain |
| `max_planned_motor_time_s` | Positive upper programmed motor-on time including startup/normal descent, not an arbitrary simulation clock |
| `max_abort_to_motor_off_s` | Positive upper motor-on terminal tail after the trigger, including uncertain recovery/landing when appropriate |
| `energy_time_reserve_s` | Nonnegative *additional* motor-on reserve for battery variation and observer uncertainty; zero requires justification |

The returned hypothetical travel allowance is
`v × L + v²/(2 × a)`, valid **only** when the claimed bounds truly apply to
the whole maneuver. Conditional horizontal margin is
`D − (R + r + u + v × L + v²/(2a))`.
The energy-duration margin is
`T_endurance_lower − (T_planned_upper + T_abort_motor_off_upper + T_reserve)`.
The two time terms are deliberately additive/conservative; they are not a
flight-duration prediction. If a relevant effect cannot be decelerated
(e.g. lost estimate/epoch, absent ACK, uncontrolled fall), no positive `a`
can be asserted for that failure mode; the sheet is **INCOMPLETE/UNPROVEN**.
A bounded descent time does not imply bounded XY displacement or impact energy.

The tool outputs **CONDITIONAL_ARITHMETIC_ONLY** even for positive margins,
and `flight_authorized: false`, `physical_qualification: UNPROVEN`.
A negative margin refutes the supplied conditional envelope; a positive one
does **not** validate its physical inputs, the recovery mechanism, its safety,
or suitability for school use. Do not use output as an approval, automatic
preflight or substitute for an independent operator/containment decision.

## Reproducible future measurement record (human-gated only)

1. **Before any test**, create a fixed protocol bound to the exact integrated
   SHA, AST hash, firmware binary/params, decks, mass, propellers, battery ID,
   condition/age and state of charge, temperature, floor texture, light,
   site geometry and confinement. Attach an independent ruler/geometry witness.
   Verify the physical package and approved checkpoint. No retry or changed
   setup in response to an adverse value. There is **no approval now**.
2. **Front availability**: retain raw uint16, direction, filterMask readback,
   connection epoch, LOG publication ticks, observer errors, deletion ACK,
   flight state and exact AST digest. Keep the original raw values including
   32766/32767 and missing records. Record independent target position,
   dimensions and continuous visual witness of optical line of sight at floor
   and hover. A changed LOG tick does not date sensor production; do not claim
   freshness/clearance from it.
3. **Abort and recovery**: independently timestamp visible operator gesture,
   host-side terminal observation, last authorized command, ACK and completion,
   physical onset of descent/deceleration, physical touchdown and motor-off.
   Preserve original clocks and synchronization uncertainty rather than
   declaring a common clock without calibration. Retain all failed/late events.
   A missing event, effect ambiguity, lost epoch, or unbounded wait means **no
   finite maximum** from that attempt. A controlled LAND signal is not proof of
   actual landing. Never force a risky abort merely to fill this table.
4. **Excursions and confinement**: witness full swept position and attitude,
   body/rotor extent, lateral/vertical excursions through normal execution,
   cancellation, recovery and possible drop. Determine bounds or an independently
   sufficient containment domain *before* motorized experimentation; a nominal
   1.00 m target is not a qualified clearance. Account for people, external
   equipment, Flow/deck visibility, failure of control, and the possibility of
   a fall rather than a controlled landing.
5. **Energy**: use independently justified, time-correlated under-load evidence
   for the exact battery and mass/deck setup, including cell-voltage sag,
   low-voltage behavior, temperature and end-of-run reserve. A nominal battery
   label, no-load voltage or a single lucky duration does not establish a
   usable lower-bound endurance. The 210 s simulation cap cannot fill this
   field. Do not introduce firmware tuning, an unsanctioned endurance-to-empty
   flight, or a new sensor/second radio controller for convenience.
6. Archive immutable original witnesses, raw traces, checksum manifest,
   clock-calibration and missing-data statements. Review separately sensor
   availability, trajectory bounds, aborted/ambiguous recovery, energy, and
   procedure adherence. **Do not** merge their outcomes into a false physical
   PASS. Any real measurement requires a fresh owner-approved exact checkpoint
   and a safely controlled domain; no material test is authorized here.

## Independent falsification before any use

The machine regression `tools/ci/test_physical_conditional_flight_budget.py`
must reject every absent or duplicated JSON key, forged-form digest,
booleans/strings/nonfinite or negative inputs, zero duration/deceleration
and non-representable magnitude. It tests both near-zero margin signs and
directed output rounding for **synthetic** fixtures.
It cannot prove witness authenticity or physically attainable margins.
