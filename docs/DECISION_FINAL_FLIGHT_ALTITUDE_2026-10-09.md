# Decision — final real flight and altitude research (2026-10-09)

**Status:** repository-owner scope decision, proposed as documentation by
this PR. This is not a new physical observation, an accepted altitude
capability, or a change to safety/governance rules.

## D1 — Real finality independent of the table

Preserve the eight existing progressive activities and Webots simulation
as the teaching baseline. A final teacher-authorized **physical mission**
must be achievable above a **uniform floor**, with only physically proven
capabilities and a qualified corridor. Simulation can contain richer worlds,
but the exact program admitted to real flight must be first validated in
simulation and then executed **unchanged**, through the established
Blockly → AST → preflight → interpreter → backend path.

Keep teacher approval, live hardware/capability checks, provenance,
abort/failsafe and independent physical qualification. Success in Webots or
CI does not prove real flight. [#72](https://github.com/djibian/webeeblocks/issues/72)
may advance after relevant [#157](https://github.com/djibian/webeeblocks/issues/157)
evidence without waiting for table research.

## D2 — #70 preserved; candidate C alone in scope

The goal of [#70](https://github.com/djibian/webeeblocks/issues/70) is a
**genuine** floor → table → floor crossing at stable world-frame altitude,
acceptable X/Y and controlled recovery, with no ceiling range and no
additional hardware. Merely clearing the table by following its surface
vertically is **not** sufficient.

The **only** research candidate to explore is **C**: world-frame vertical
motion derived independently from IMU and barometer over a defensible
bounded duration. The lower ToF may support local clearance/optical-flow
depth, **not** become a circular world-Z reference. Indirect coupling
through attitude, velocity and estimator covariance must also be
examined; a nominal separation of inputs does not establish independence.

Owner-excluded approaches:
- **A:** official-firmware terrain-following climb/descent.
- **B:** known-table geometry, two-plane map or mapped-terrain EKF
  compensation.
- A ceiling/up-range reference, added positioning hardware, or
  automatic return to UKF/S3 parameter tuning as a main approach.

A/B are excluded by the owner's target and design constraints, **not**
claimed to be mathematically or physically impossible. If C fails the
mission's evidence requirements, **no substitute table-crossing capability
is offered**.

## Evidence and next eligible research

Archived [#561](https://github.com/djibian/webeeblocks/issues/561) and
[its analysis](X3_FAIL_561_ANALYSIS.md) show stationary IMU/barometer
recording and an unexplained later UKF health failure. The barometric
signal is too variable to assume a strong fast Z reference; those
observations alone do not refute every short-horizon fusion method.
Neither the current UKF state nor the ToF can serve as the independent
truth for C. Stable world altitude in real flight is **UNPROVEN**.

An eligible bounded Lab result must first:
1. State a justified physical error/duration/recovery budget and
   assumptions (IMU bias, initial velocity, attitude, pressure, timing,
   covariance coupling, missing measurements and Flow scaling).
2. Inspect official models, reanalyse archived raw windows and
   simulate/replay both edges and failure cases before physical work.
3. Identify the *specific* unresolved physical unknown; only if
   decision-critical, propose a minimal independent, props-off
   acquisition with its own preregistration and trusted checkpoint.
   One continuous trace may suffice for first discrimination, but not
   for independent confirmation after data-driven tuning.
4. Retain all results and predeclared physical failure/acceptance
   evidence before any possible motorized qualification. No test or
   motor action is authorized by this record.

The original X3 characterization/confirmation plan (12+12 captures)
is **not a mandatory gate**. Preserve its frozen contracts and results;
do not retroactively recast an incomplete X3 run as a PASS.

**Stop rule:** if C cannot credibly satisfy constant world altitude plus
X/Y/recovery in the defined corridor, report the bounded failure or
UNPROVEN conclusion, keep table flight unavailable and do **not** fall
back to A/B without a new explicit owner decision.

## D3 — Product priority

Prioritize the real-device safety and capability qualification in #157,
then the bounded final mission #72 once its relevant gates converge.
#70 remains independent, optional Lab research with investment strictly
limited to information that could change its scientific decision.

Research basis: the two owner-reviewed scientific dossiers dated
2026-10-08 and existing GitHub archives, **not** new measurements from
this documentation PR.
