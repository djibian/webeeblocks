# Vertical pilot — V5 independent-review dossier (DRAFT, NO MERGE)

**Authority:** evidence only; not a Controller GO, CI Gate, owner authorization,
hardware qualification or an approved pedagogical activity.

## Exact provenance

- Integrated prerequisite: PR #952 Draft @ `198c48669ac3bcfdd2990486eed8edf2ad0eeee9`.
- Experimental native bench: PR #954 Draft @ `a84d477e31f72c3cd87abfa6191fabaf408450ae`.
- Native GitHub Actions run **42878862498**, artifact **13795080041**
  (`experiment-953-native-takeoff-r2025a-a84d477e31f72c3cd87abfa6191fabaf408450ae`).
- Downloaded artifact SHA-256:
  `8e9f3af202e0790fd4156c970165693c2231c22a3d2543dc9f43c67b57b645b0`.
- Candidate native evaluator SHA-256:
  `be6a520bc3ef25792053457761b6f6f25afbf19526045be1476a8780e14a5e7d`.
- The fixture world SHA-256 is
  `9b1f4f62841c653b406c6d85401d9990890d5afdec5548c4987b67881801a286`
  across all nine recorded scenarios. 8 ms physics, 32 ms native PID.
- **No claim** that this separate product-composition branch has itself passed
  the exact binary native test: ported behavior MUST be compiled and exercised
  on its own exact HEAD before integration.

## Bounded nine-scenario evidence

| Scenario | Native status | Maximum z (m) | Clearance from z=1.165 m (m) | Motor saturations |
|---|---|---:|---:|---:|
| ceiling | pre-acceptance `VERTICAL_LIMIT` | 1.059425 | .105575 | 0 |
| ceiling_large_ascent | pre-acceptance `VERTICAL_LIMIT` | .842292 | .322708 | 0 |
| ceiling_safe_ascent | upward VERTICAL ACK | 1.038451 | .126549 | 0 |
| ceiling_takeoff | `INVALID_TAKEOFF` for 1.1m, then 1.0m accepted | 1.059425 | .105575 | 0 |
| primitives | TAKEOFF, WAIT, MOVE, VERTICAL, TURN, LAND, RESET, new TAKEOFF, STOP | .730716 | .434284 | 0 |
| route_lh | two open H, two physical L, terminal LAND, `STATE achieved` | .979358 | .185642 | 0 |
| stop | MOVE interrupted by `USER_STOPPED`; native LAND confirmed | .842292 | .322708 | 0 |
| reset | ground RESET + TAKEOFF accepted; airborne RESET `LANDING_UNCONFIRMED` | .842292 | .322708 | 0 |
| deadline | 210000ms after admission, independent LAND confirmed | .852118 | .312882 | 0 |

`index.json` reports all scenario stimuli completed. This is not nine successful
**missions**; expected negative tests are negative, and all reports explicitly
set `full_mission_success_claim=false`.

## Mandatory distinctions: evaluator observation revocations

- STOP/MOVE: `invalid-native-observation` at **8.328s**, then
  `GP_ROUTE_SAFETY_LAND evaluator-unavailable` and native forced LAND
  at **8.352s**; ground ready at **11.616s**. An expected fail-closed path
  after STOP, **not** a positive oracle outcome.
- Regular LAND + RESET: previous attempt `native-context-revoked` at
  **17.160s**; new admitted attempt starts at **18.272s**; second attempt
  closes for inactive context after STOP at **22.440s**.
- Normal L/H course: LAND native ground ready at **77.856s**,
  evaluator `invalid-native-observation` at **78.472s**, and the WWI backend
  subsequently reads `STATE achieved`. No native `GP_U_DEADLINE` in
  that case. This is consistent with the evaluator's documented rule
  that publication-positive is not erased by later ALIVE revocation;
  **independent V5 reviewer MUST verify the exact success-latching order
  and reject stale/unlatched cross-epoch outcomes**.
- RESET from ground: former attempt `invalid-native-observation` at
  **2.184s** before new admission at 3.872s. Must not be counted as valid
  active-flight continuity.
- 210s deadline: evaluator closes explicitly with `reason=time-limit` at
  **213.136s**, exactly 210s after 3.136s admission.
- None of these records justifies suppressing `_close`, weakening an oracle,
  changing the deadline, or translating an observation lapse into success.

## Product change and dependency

One source-locked, route-only composition function:
`tools/grand_prix/route_vertical_product.py`, called only from the
`route_observations` branch of `prepare_u_runtime.py`.

1. Keep the #952 progressive TAKEOFF reference as-is.
2. Reuse the *same* physical native PID and existing attitude/motor mixing;
   shift only the common collective to the measured hover feed-forward +
   bounded integral + measured vz damping across aerial TAKEOFF, IDLE, WAIT,
   MOVE, VERTICAL, TURN, and LAND until touchdown. Never bypass
   `if (command == CMD_LAND && land_touchdown)` motor stop.
3. Before assigning `active_id` or targets, reject TAKEOFF exceeding
   `origin_z+1.15 - headroom(vz,0)`; before accepting VERTICAL up,
   reject target exceeding `origin_z+1.15-headroom(vz,dz)`.
4. `headroom(v,dz) = 0.095 + 0.30*dz + 0.064*max(v,0)
   + max(v,0)^2/(2*0.25)` for positive upward VERTICAL;
   TAKEOFF uses a separate `0.080` base reserve with the same speed terms.
   This is an **empirical guard**, not a formal invariant for all trajectories.
5. Preserve unchanged simulator backend, physical sender, motor clamps,
   existing 8ms/32ms clocks, evaluator/scene/oracles, RESET, STOP, independent
   210000ms LAND and mission success guard. No direct-trajectory or added
   VERTICAL governor is adopted.

## Known unresolved refutations / V5 review gates

1. **No exact product-binary native A/B yet.** Benchmark run comes from the
   diagnostic #954 code, not the separated product branch. Compile and compare
   requests, rotor outputs, refusal semantics and postconditions at exact HEAD.
2. **Narrow measured envelope:** only .10 and .30m upward command amplitudes,
   limited near-zero initial vertical velocity; no proof for the full .10–.50m
   exposed Blockly domain, and no positive-vz adversarial native envelope.
   Fail closed on unknown performance; do not enlarge oracle ceiling.
3. **Course breadth:** native `STATE achieved` for reference course index 5
   (`gp-route-v2-L2000-2500-3000-TGD-s105-H2`); no complete evidence
   for all 12 reference courses or 1/3-H alternative turns. Negative
   boundary/contact/progress tests needed. No AST-guided pupil route pass.
4. **Success after revocation:** independent reviewer must prove that
   `STATE achieved` is bound to the same epoch, context and
   ground-confirmed success latched **before** ALIVE revocation.
5. **Error taxonomy:** `VERTICAL_LIMIT` and `INVALID_TAKEOFF` mean native
   preventive refusals; `GP_ROUTE_EVALUATOR_CLOSED reason=altitude`
   means physical oracle breach; `GP_U_DEADLINE` means 210s elapsed.
   `TIME_LIMIT` is an overloaded WWI code and must not be presented as a
   unique cause. A wall-clock `Runtime v2 request timeout` is a transport
   non-response, never an oracle verdict. No generic backend modification
   is authorized solely to improve labels.
6. **Safety regression:** continued STOP, airborne RESET refusal, normal
   ground-confirmed LAND and 210s independent LAND at exact candidate HEAD;
   zero actuator saturation in all valid observed envelopes.
7. **Governance:** remain Draft and NO MERGE until independent V5 review,
   exact HEAD CI Gate for Ready, owner approval and appropriate main freshness.
   No physical Crazyflie flight authorization or classroom PASS is inferred.
