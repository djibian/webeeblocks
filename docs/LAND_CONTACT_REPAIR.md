# Native LAND contact repair (#637)

## Behavior and unchanged boundaries

LAND captures current X/Y/yaw/height, then reuses the existing bounded
position/yaw controller. Its height reference has two continuous linear
segments: 0.40 m/s while more than 0.30 m above origin, then 0.15 m/s for the
last 0.30 m, clamped at origin_z. A start below that transition uses only the
slow segment. These are setpoint slopes, not guaranteed actual velocity bounds.

The faster far approach avoids unnecessarily spending the mission's existing
low-flight/takeoff allowance on a slow high-altitude descent. It does not
change the 15 s exception, low-altitude geography, 210 s deadline, terminal
criteria, safety thresholds, windows, timeouts, PID gains, motors, colliders,
inertia, materials or product physics step. The independent Grand Prix
authority still starts LAND and applies control on the exact expiry tick;
its height reference is initialized from that tick's measured pose.
No delayed action, regained success or weakened negative oracle is introduced.

## Independent evidence and retained counterexamples

The original studies eccfe5701c2459bc1ae737bcea70bf5004061f27,
4078589bdb096b058ad054c484c9811dfdee3698 and
3326b9ba9eec27870aefe4b2230edf95fdedec8f were independently recalculated.
Their 7+5 refusal tests passed, and a fresh native command-force acquisition
reproduced the historical first contact without active PID feedback:
position residual <=6.03e-10 m, linear velocity <=4.11e-10 m/s,
pitch 6.76e-10 rad and angular Y 1.12e-8 rad/s. These describe agreement with
rounded logs, not physical accuracy or product tolerances. Later amplification
and the source of upstream height differences remain distinct questions.

The full C/PID with real native propellers also reproduces the complete
historical slide to X=-2.40115223257 m despite ACK LAND. A constant 0.15 m/s
reference plus hold reduced that particular terminal displacement to about
0.9 mm. Twelve additional height/step cases completed locally. The final
published regression driver independently rejects the baseline after ACK
and accepts that constant-slope candidate. These mechanical-shell results
are retained, not substituted for the official mission campaigns.

**The constant-slope candidate was then refuted by a true Grand Prix test.**
Canonical Draft run 40280309908, HEAD 669d3a075e45add5d8ad5058628a8cb6ad0bbc82,
prepared and verified the generated binary/cache successfully, but its short
negative returned low-outside-zone at 15.008 s instead of required wrong-landing.
The takeoff exception elapsed while the slow descent/terminal sequence was
still pending. The 2,470,350-byte original ZIP artifact 12632226197 has SHA256
c77e61a1918ea5fc87a59e8952bd82733f206f989e963e38e88523b7aa9a96a3;
CRC 45/45 and the short-case manifest were checked. No alternative failure
reason is accepted and no oracle or deadline is changed. This refutation
motivates the faster far approach, not a retry of the same candidate.

The new two-segment profile passes the local historical regression with
real physics: final X=0.1551717472 m, within 3 cm of its LAND request point;
first observed contact VZ=-0.11452814 m/s. This is a different trajectory
from the constant-slope experiment and inherits none of its other trials.
Composition pose/deadline and instrumentation tests are rerun on the changed C.
The real Grand Prix negative and all official positive/negative missions
still require canonical evidence of the final exact Ready HEAD.

## Recovered original captures

The local environment temporarily became unavailable before publication.
Its original files later became accessible again; all completed per-capture
manifests verified without changed members. They are now preserved in
[the recovered evidence branch](https://github.com/djibian/webeeblocks/tree/e770fe8adb7fbb5f2a76e561a885527fd9ed0228/experiments/land-descent-637).
Its tar contains 337 original/support files plus a recovery manifest:
1,832,032 bytes, SHA256
a7ae2f4818fa8d07d5f55d19714f780005283311b63ee4a98efd21688c936cbb.
The independent command-force tar retains its originally reported SHA256
fd3ff25f3d40a219c8166c2cccbdd16b2ee6e269e2e187e214aedec2efd49b88.
Read-only analysis and recalculated summaries are included. The temporary
archive-unavailability report remains in history; late preservation is neither
pre-registration nor independent timestamp attestation. Original preparation
failures are retained without assigning them native observations or PASS.

## Mandatory regression, in addition to full missions

tools/ci/run_land_contact_regression.py compiles the current shared C/PID
against real R2025a. It injects only request transport, scene readiness and
an outer step wrapper that calls the real wb_robot_step. The existing offline
qualification shell preserves original actuation/cylinder/inertia with
simplified visuals. This is not a browser, scene-loading or full-mission proof.

The driver sends each historical request once, stops submitting after any
error and observes for 3 s after terminal response. A separate native oracle
requires position within 3 cm, altitude within 5 cm, attitude/yaw within
2 degrees, horizontal speed below 0.12 m/s, vertical speed below 0.15 m/s
and angular speed below 0.10 rad/s continuously for 0.50 s. It rejects the
historical large slide even if LAND acknowledges. These are additional
regression checks, not replacement product success predicates.

Source, driver, world, original C, binary provenance, complete logs and digests
are archived after direct producers stop. The regression is mandatory in
both sequence/neutral-start canonical campaigns in addition to every existing
browser-based positive/negative case. Their launch arguments, rendering,
budgets and oracles remain unchanged. Headless rendering is used only for
the new mechanical shell. --runtime-source is an explicit historical diagnostic;
CI supplies no override and proves the current checkout. --step 8 is an optional
separate diagnosis; the default regression remains 32 ms physics/control.

## Exact generated inputs and integration

The shared C change invalidates the source-keyed prepared qualification cache.
Use the existing same-repository Draft maintenance build in the pinned image,
observe the actual binary size/SHA256, update only its generated-lock entry
and verify/prime that exact cache. Preserve vendor/runtime/image locks,
verifiers, Ready-only cache consumption and the distinct CI Gate (Draft).
A successful preparation or Draft prototype is not integration evidence.

Require the newest exact Ready-HEAD pull_request .github/workflows/ci.yml run,
every applicable native proof and the real successful CI Gate. Another
execution must independently examine code/support/evidence, unchanged negative
oracles, exact 210 s authority and remaining refutations before conditional
integration on fresh main. The author execution supplies no independent GO.
RESET restoration, pre-READY #665/#699, #638's other evidence, #635 pedagogy,
global main health, TEST_REQUIRED and real flight are not established here.
