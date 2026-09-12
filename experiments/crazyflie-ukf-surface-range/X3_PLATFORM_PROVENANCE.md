# X3 STM32 OTP platform provenance probe

This support slice narrows one provenance question discovered while reviewing the
Crazyflie 2.1 BMI088 interrupt path for #70. It does **not** resolve that interrupt
wiring contradiction and does not enable a checkpoint.

The exact pinned Crazyflie firmware
`54f31e243a0b28b67efef5ba20dbb6d9890a5478` reads its platform string from STM32
OTP at `0x1fff7800`: 16 blocks of 32 bytes, selecting the first block whose first
byte is non-zero. If there is no such block, or if that first non-zero byte is
`0xff`, the firmware falls back to `0;CF20`. The X3 probe mirrors only that
selection rule and retains the observed bytes.

`probe_x3_platform_otp.py` uses pinned-cflib-compatible `LogConfig.add_memory()`
raw-memory log variables. It deliberately limits each log-control configuration
to at most five memory descriptors, takes three identical observations of every
byte group, and fails closed if a group changes or is malformed. It then reads the
selected 32-byte OTP block and accepts platform identity only when the observed
STM32 OTP string explicitly reports device type `CF21`. An `R=` field is retained
only when actually present in those observed bytes.

The probe never flashes firmware, writes parameters, writes memory, resets the
estimator or invokes a commander. It does send the ordinary CRTP log-control
packets needed to read memory; normal cflib link close may still emit its documented
safety-zero commander setpoint. The expected cflib source is
`45fdb784c9d13074c42835f3b5ac1d12133bf873`, but the standalone script does not
itself attest the complete installed Python runtime. A later trusted bundle must
pin and verify that closure before relying on a physical observation.

Most importantly, an observed `0;CF21` or even `0;CF21;R=B1` proves only the
unit-reported STM32 OTP platform string. It does **not** prove BMI088 INT2/INT3 net
continuity, rehabilitate `sensorData.interruptTimestamp` as gyro or accelerometer
producer time, validate any frozen-predictor uncertainty bound, or establish a
physical verdict. `electrical_interrupt_source` therefore remains `UNPROVEN`.

Offline inspection and tests require no cflib, radio or hardware:

```sh
python3 experiments/crazyflie-ukf-surface-range/probe_x3_platform_otp.py --describe
python3 experiments/crazyflie-ukf-surface-range/test_probe_x3_platform_otp.py
```

A future read-only observation, if separately justified, uses an explicit
Crazyradio URI and a new output directory:

```sh
python3 experiments/crazyflie-ukf-surface-range/probe_x3_platform_otp.py \
  --uri radio://0/80/2M --output ./x3-platform-otp
```

The command writes `probe-start.json` and `platform-otp.json`. Exit status 0 means
only that the selected observed STM32 OTP string explicitly reported `CF21`; exit
status 2 means the read completed but platform identity remained unproven. Neither
status is `TEST_REQUIRED`, PASS/FAIL for #70, or permission for firmware changes or
motorized action.
