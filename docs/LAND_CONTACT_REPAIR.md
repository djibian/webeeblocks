# Native LAND contact repair (#637)

## Bounded behavior

LAND captures current X/Y/yaw/height and reuses the existing position/yaw
controller during descent. The altitude reference descends at 0.15 m/s, clamped
at origin_z, instead of stepping immediately to origin_z. This is a reference
slope, **not a guaranteed bound on actual vertical speed**. No PID gain, motor,
collider, inertia, material, physics step, safety threshold, completion window,
timeout, negative test or mission oracle changes.

The independent Grand Prix authority still enters LAND and applies control on
the exact expiry tick at 210 s. It also captures the current landing height on
that tick. There is no deferred action, deadline extension or regained success.
The existing shared LAND completion predicate is unchanged; the independent
Grand Prix grounded/finite/stable authority remains necessary.

The rate is an engineering candidate: traversing the supported nominal 1.50 m
takes 10 s of reference progression inside the unchanged 25 s action timeout.
That calculation alone does not qualify tracking, stopping or any real flight.

## Independent causal check and local observations

The audits at eccfe5701c2459bc1ae737bcea70bf5004061f27,
4078589bdb096b058ad054c484c9811dfdee3698 and
3326b9ba9eec27870aefe4b2230edf95fdedec8f were independently extracted and
recalculated. Their 7+5 refusal tests passed. A new native R2025a command-force
acquisition reproduced the historical first contact: maximum position residual
6.03e-10 m, linear velocity 4.11e-10 m/s, pitch 6.76e-10 rad, angular Y
1.12e-8 rad/s. These are agreements with rounded logs, not physical tolerances.
The first mechanical tip therefore does not require active PID feedback.
Later amplification and the origin of upstream height differences are distinct.

The full shared C/PID with real native propellers was then driven through the
historical effect timings: TAKEOFF 0.50 at 2.464 s, WAIT 0.50 at 6.848 s,
MOVE forward 0.10 at 7.552 and 9.536 s, LAND at 11.392 s. The offline
qualification shell retains the original R2025a actuation/cylinder/inertia;
its simplified visuals, injected transport and scene-ready stub do not prove
the full browser/scene/mission workflow.

| Local intervention | Final X after 3 s | Maximum pitch during LAND |
| --- | ---: | ---: |
| Unchanged main, 32 ms physics/control | -2.401152233 m | 0.75996 rad |
| Altitude reference ramp alone | +0.150311969 m | 0.03445 rad |
| Same ramp plus hold at LAND request | +0.165643916 m | 0.03427 rad |

The last position is about 0.9 mm from the LAND request point. The unchanged
baseline still acknowledged LAND before sliding out of the target; an ACK is
not a valid landing oracle. A separate 8 ms physics/32 ms control baseline
had a different trajectory and acknowledgement timing, so it is not an
identical-entry-state comparison and is not the selected correction.

Twelve additional ramp+hold runs used nominal heights
0.20/0.35/0.50/0.80/1.00/1.50 m with 32/8 ms physics, always 32 ms control.
All twelve sequences completed and settled in the local observations, maximum
LAND pitch 0.04086 rad. These are bounded engineering observations, not official
mission acceptance, universal stability or real-flight qualification.

**Evidence limitation:** the local execution environment became unavailable
before these new raw archives could be published. Terminal calculations and
summaries were observed, but no durable raw archive is claimed. The independently
repeated command-force tar had local SHA256
fd3ff25f3d40a219c8166c2cccbdd16b2ee6e269e2e187e214aedec2efd49b88;
that digest is not a download link or proof that the bytes remain available.
The original three published studies are unaffected.
The owner-attributed report is preserved on
[issue #637](https://github.com/djibian/webeeblocks/issues/637#issuecomment-6404765591).
Do not substitute this reported local evidence for exact-candidate CI.

Before the loss, composition pose/deadline tests, LAND instrumentation (11),
timeout (4), and controller contract (16) completed positively. The final
regression driver/runner is reconstructed after that loss and is **not claimed
locally executed**. Its first authoritative execution is canonical CI.

## Durable native regression and acceptance

tools/ci/run_land_contact_regression.py compiles the current shared flight
source and current PID against real R2025a. It replaces only the request
transport, scene-ready check and outer step wrapper. The latter always calls
the real wb_robot_step; sensors, motors, physics and the command state machine
remain real. The qualification PROTO, source, wrapper, binary provenance,
world, complete logs and digests are archived beside the normal progression
artifacts, after all direct producers stop.

The driver sends each historical request once, stops submitting after any
error, and observes for three seconds after the terminal response. A separate
native pose oracle requires the existing 3 cm position, 5 cm altitude,
2 degree attitude/yaw, 0.12 m/s horizontal, 0.15 m/s vertical and 0.10 rad/s
angular thresholds continuously for at least 0.50 s after LAND. It rejects the
large historical slide even when LAND acknowledges success. These checks add
a regression obligation and do not relax product or mission predicates.

The regression is mandatory in both existing sequence/neutral-start canonical
campaigns, **in addition to** their entire browser-based positive/negative
missions. No historical test is removed, reclassified or skipped. It uses
headless rendering only for its own mechanical shell; full native mission
launch arguments, rendering, budgets and oracles remain unchanged.

Example, on a machine with Webots R2025a and Xvfb:

python3 tools/ci/run_land_contact_regression.py --home /path/to/webots --xvfb /usr/bin/Xvfb --out /new/output

For an explicit historical diagnostic, --runtime-source accepts a separately
extracted main@f5435a8... C file; its exact hash/path is retained. CI passes no
such override and proves the current checkout. --step 8 is a separate optional
diagnostic; default CI physics/control remains 32 ms.

## Integration boundaries

Require the newest exact Ready-HEAD pull_request run of .github/workflows/ci.yml,
all applicable native missions and the real successful CI Gate. Another
execution must provide independent V5 review of code, causal evidence,
regression support, negative cases, the exact 210 s authority and remaining
refutations before conditional integration on fresh main.

This repair does not establish RESET restoration, fix the pre-READY #665
family or #699's separate asset preparation, clear #638's Grand Prix evidence,
accept #635's pedagogy, restore main globally, authorize TEST_REQUIRED or
authorize hardware flight. The author execution supplies no independent GO.
