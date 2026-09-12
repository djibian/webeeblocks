# X3 independent-input acquisition support

The integrated [archive audit](evidence/analysis-2026-09-11/README.md) establishes
that the old recordings lack continuous pressure and IMU samples. This collector
fills the acquisition part of that gap using the existing #251 firmware. It
does not implement or validate an independent vertical estimator.

## Exact firmware and recorded signals

The expected binary is the #251 artifact's `cf2.bin`, 250,176 bytes:

`67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`

It was independently read from [artifact 10089812000](https://github.com/djibian/webeeblocks/actions/runs/34314942011/artifacts/10089812000)
and the enclosing ZIP matched checkpoint #251's published SHA-256
`c7b9b9143118fb7572e7b23a7f61e9936f220a1eb5f56e98ea39852f52c39cc3`.
The authoritative artifact ID/digest are in
[#251's result](https://github.com/djibian/webeeblocks/issues/251#issuecomment-5604562996).
The collector checks the local binary; the operator confirms its installation.
This is explicitly not remote firmware attestation. No flash is performed.

| CSV block | Period | Signals | Fetch payload |
| --- | ---: | --- | ---: |
| `barometer` | 20 ms | `baro.asl`, `pressure`, `temp` | 12 bytes |
| `imu` | 10 ms | `acc.x/y/z`, `gyro.x/y/z` | 24 bytes |
| `pose` | 20 ms | downward range, roll/pitch, UKF Z/VZ, `stabilizer.intToOut` | 24 bytes |
| `detector` | 20 ms | S3 state/reason/offset/barometer delta, local Flow flag, late eligibility | 24 bytes |

Every field is fetched as a float; each block fits cflib's 26-byte log payload.
Units remain the pinned firmware units: barometer altitude in m, pressure in
mbar, temperature in Celsius; accelerometer in g; filtered gyro in degrees/s;
downward range in mm; roll/pitch in degrees; UKF Z in m and VZ in m/s.
`stabilizer.intToOut` is a difference of two values from the pinned firmware's
`usecTimestamp()` clock, from the interrupt timestamp carried by the stabilizer's
current `sensorData` to the end of that stabilizer iteration. The pinned
`2026.08@54f31e...` TIM7 prescaler has a known 84/85 nominal-rate defect documented
in [X3_PRELPF_TIMING_OBSERVER.md](X3_PRELPF_TIMING_OBSERVER.md) and upstream PR
[bitcraze/crazyflie-firmware#1684](https://github.com/bitcraze/crazyflie-firmware/pull/1684),
which is based on that exact firmware commit. Consequently the raw `intToOut`
number is not a true elapsed-microsecond measurement as stored; the deterministic
prescaler correction alone is `raw * 85 / 84`, before separate oscillator and
sensor/interrupt provenance uncertainty. Diagnostic UKF outputs and this latency
diagnostic must not become independent displacement inputs.

Both the 24-bit device log timestamp and host monotonic receipt time are retained
for every row. The wireless log timestamp uses a different FreeRTOS-based clock
path and is not corrected by the TIM7 85/84 rule. Log time does not identify a
sensor's producer time, and fetching acceleration/gyro in one block does not prove
simultaneous sensor acquisition. The `intToOut` value is read later by the log
worker from shared state and is not atomically paired with the pose or IMU row; it
characterizes the firmware's internal sensor-to-output path only after preserving
its distinct clock semantics and still does not validate `sensor_time_error_s` or
supply a producer timestamp. The chosen cadence is an acquisition configuration,
not proof that inertial integration or a 5 cm / 1 s bound is achievable. No
missing row is interpolated.

## Machine checks and output

```sh
python3 experiments/crazyflie-ukf-surface-range/capture_independent_inputs.py --describe
python3 experiments/crazyflie-ukf-surface-range/test_capture_independent_inputs.py
```

These commands require no cflib, radio or physical action. Tests use explicitly
synthetic links/telemetry and exercise the complete acquisition lifecycle plus
missing streams, wrong configuration/binary, invalid rows, timestamp wrap versus
duplicates, connection/parameter timeout, interruption and log-stop failure. They
do not prove live throughput.

For an eventual prepared checkpoint, the trusted procedure supplies the exact
checkpoint URL and request SHA, the proven cflib runtime, this exact script and
the exact local firmware file. The recording CLI additionally requires one
explicit radio URI, a new output directory, duration (30–300 s), and explicit
`--props-removed --installed-bin-confirmed`. The script checks all required live
log names and reads the unchanged #251 parameters before declaring recording
ready. It allows 30 s for the asynchronous connection/parameter download after
opening the driver, then 5 s for every stream to become observable. These are
protocol wait bounds, not a hard process deadline for OS/USB/file operations.
It writes no parameter, estimator reset or commander request. Normal
cflib close retains its documented safety-zero setpoint behavior.

The immutable `capture-start.json` records the evidence identity
`x3-independent-props-off`. This name is deliberately distinct from the
superseded `s3-props-off` human checkpoint: the X3 capture exists to test the
independent IMU/barometer information path, not to repeat or validate the scalar
S3 terrain classifier. The string is capture provenance only until the trusted
human-checkpoint mechanism explicitly implements and enables a matching profile;
it does not itself request `TEST_REQUIRED` or authorize physical action.

Output includes four CSVs and immutable start/ready/result metadata. Startup
samples stay in the raw files; `recording-ready.json` is a receipt-clock marker,
not an independently measured physical event boundary. Missing/malformed values
stay visible in their raw row and make the capture incomplete. A gap over five
configured log periods, duplicate/backward timestamp, stopped stream, transport
failure, interruption or uncertain cleanup cannot yield `CAPTURED`. Smaller
gaps are recorded in the per-stream maximum and remain part of later data-quality
analysis. A forward 24-bit timestamp wrap is distinguished from a backward clock.

`CAPTURED` means acquisition completed, never physical PASS, scientific adequacy
or durable publication. A crash may leave only partial files; absence of a final
result is incomplete/unknown. Existing output directories are never overwritten.

## Remaining prerequisites before TEST_REQUIRED

The acquisition component, frozen pressure probe, conditional metric-reference
processor, conditional vertical replay predictor and generic Git-backed evidence
publication mechanism are now integrated. No new physical test follows from this
component alone. The remaining checkpoint preparation is narrower:

- Prepare the measured stationary/terrain/vertical/mixed procedure, synchronized
  independent reference and event boundaries. A 30 s calibration and both signs
  of each physical case are retained; the same analysis path must process every
  case. The [conditional reference processor](METRIC_REFERENCE.md) preserves
  external annotations and clock/metric intervals; its arithmetic does not
  validate the physical measurements, clock assumptions or synchronization.
- Pre-register and justify the deterministic error, tilt, initial-velocity,
  intersample-acceleration, sensor-time, barometer and delivery-latency bounds
  consumed by [the frozen vertical predictor](FROZEN_VERTICAL_PREDICTOR.md).
  Outcome data must never be used to narrow these bounds. The retained
  `stabilizer.intToOut` diagnostic can falsify assumptions about the internal
  sensor-to-output path but cannot by itself validate sensor producer timing.
- Package and validate the exact cflib runtime, exact #251 firmware file, capture
  script, reference/predictor support and executable physical procedure in the
  trusted checkpoint preparation. The collector's module hashes identify two
  observed modules; they are deliberately not a complete dependency lock. Live
  cadence/availability remains unproven until the bounded props-off capture.
- Use the integrated generic raw-publication path from #296 / `docs/TEST_EVIDENCE.md`
  for the produced bounded CSV/JSON/text evidence. This collector never deletes
  or uploads raw files, and a manual browser attachment is not canonical evidence.

Preserve the local-range Flow split, all #251 parameters and the no-motorized
boundary. No estimator or controller change follows from successful acquisition.

## Inspected API sources

- [Firmware log names/units](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/stabilizer.c), including the existing `stabilizer.intToOut` sensor-to-output diagnostic.
- [Pinned `usecTimestamp()` timer configuration](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/hal/src/usec_time.c) and upstream exact-base correction/review in [bitcraze/crazyflie-firmware#1684](https://github.com/bitcraze/crazyflie-firmware/pull/1684).
- [Pinned cflib LogConfig/TOC/log lifecycle](https://github.com/bitcraze/crazyflie-lib-python/blob/45fdb784c9d13074c42835f3b5ac1d12133bf873/cflib/crazyflie/log.py).
- [Pinned cflib asynchronous connection/parameter-ready and close lifecycle](https://github.com/bitcraze/crazyflie-lib-python/blob/45fdb784c9d13074c42835f3b5ac1d12133bf873/cflib/crazyflie/__init__.py).
