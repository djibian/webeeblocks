# C0 — real Crazyflie read-only capability probe

Experimental only. This directory is intentionally isolated from the frozen `webots-ci` release candidate.

## Question

Can WebeeBlocks establish a real Crazyradio/Crazyflie link, identify the expected Flow V2 + Multi-ranger decks, obtain read-only telemetry, and map a backend-neutral mission to possible cflib primitives **without any motor/arming path**?

## Safety boundary

C0 is telemetry-only. `c0_probe.py` does **not** import MotionCommander, Position/HighLevelCommander or any commander module, and exposes no setpoint, arming, takeoff, landing or motor API. The mapping shown in the report is text only and is never executed.

The unit test statically parses the Python AST and fails if commander imports or motorized call names appear in executable code.

## Mock / CI

```bash
python3 experiments/real-crazyflie-capability-probe/c0_probe.py
python3 -m unittest -v experiments/real-crazyflie-capability-probe/test_c0_probe.py
```

A green mock/CI proves only the safety plumbing and fail-closed behavior. It is **not physical proof**.

## Real read-only probe

Requires `cflib==0.1.32` and the Crazyradio USB permissions normally required by cflib.

Explicit URI is preferred when known:

```bash
python3 experiments/real-crazyflie-capability-probe/c0_probe.py \
  --live \
  --uri 'radio://0/80/2M/E7E7E7E7E7' \
  --output c0-real-report.json
```

Or scan first:

```bash
python3 experiments/real-crazyflie-capability-probe/c0_probe.py --live --scan --output c0-real-report.json
```

The probe:

1. initializes cflib drivers;
2. opens only the selected link and waits for `fully_connected` with a bounded timeout;
3. enumerates physical decks through cflib's deck-memory manager and requires Flow (`bcFlow*`) plus `bcMultiranger`;
4. reads `range.front/back/left/right/up`, `motion.deltaX/deltaY`, `range.zrange`, and `stateEstimate.x/y/z` only;
5. prints a display-only mapping from the sample WebeeBlocks mission to possible cflib MotionCommander primitives;
6. closes the link in `finally` on every path.

No firmware flashing is performed.

## Why these signals

Bitcraze's current cflib `Multiranger` utility uses the `range.front/back/left/right/up` log variables. The firmware documents `motion.deltaX/deltaY` as Flow-deck measurements and `range.zrange` as the downward range value. `stateEstimate.x/y/z` is read as estimator telemetry only.

Deck names are obtained from the deck discovery/memory subsystem rather than inferred merely from the presence of log variables in the firmware TOC.

## Stop criterion

Freeze this draft once mock CI is green and Verification cannot find an indirect motorized path. Do not open C1 automatically.

C0 becomes **physically demonstrated** only after a real run with the user's Crazyradio 2.0 + Crazyflie 2.1 + Flow Deck V2 + Multi-ranger and inspection of the produced values. Until then the hardware status is `NON TESTÉ`.
