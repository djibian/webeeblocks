# X3 archived-input audit — 11 September 2026

**VERIFIED_BY_ARTIFACT_INSPECTION:** #292 resolves access to the retained raw
text. **UNPROVEN:** these recordings cannot establish independent vertical
displacement from IMU/barometer measurements. The required measurements were
not recorded. Do not fit a predictor or infer zero displacement from absent or
inactive fields.

Evidence state: `main@c65c5561690c5c1703082ae9367e43961d032320`.
Scientific question and frozen falsification criteria:
[#70 architecture review](https://github.com/djibian/webeeblocks/issues/70#issuecomment-5606273253).
This is derived analysis, separate from the original owner verdicts. #70 remains
Lab-only; no estimator, controller, parameter or flight authority changes.

## Reproduce

From the repository root, using Python 3.10 or later:

```sh
python3 experiments/crazyflie-ukf-surface-range/audit_archived_inputs.py > /tmp/x3-inventory.json
cmp /tmp/x3-inventory.json experiments/crazyflie-ukf-surface-range/evidence/analysis-2026-09-11/inventory.json
```

The script verifies every retained file against both `SOURCE.json` and
`MANIFEST.sha256`, including sizes, and rejects missing, unexpected or changed
raw files. It inventories every CSV and keeps excluded streams explicitly
marked. It never runs a historical capture script, treats a TOC cache as sensor
samples, resamples missing signals or issues a physical verdict. Exit zero means
the inventory completed, not that the scientific hypothesis passed.

## Provenance and coverage

| Checkpoint | Tested WebeeBlocks SHA | Verified files | CSVs | Excluded CSVs |
| --- | --- | ---: | ---: | ---: |
| #180 | `173b7c5b189b4c4241d7fbde5b1443214dd20a14` | 50 | 36 | 0 |
| #236 | `8561ec3e9609acc40677b88d98eada3aae0ad954` | 16 | 14 | 2 |
| #251 | `6562ad827bf0c8bf2c9b609edad36f3e15652133` | 28 | 26 | 6 |

All **94 retained files / 76 CSVs** match the import's hashes and sizes. #180's
36 CSVs include four START/END marker files. #236's two excluded CSVs record an
operator-error fast trial; #251's six excluded CSVs are the invalid initial
precheck. They remain auditable and are not reclassified as valid experiments.
The nested binary invalid initial series omitted from #236 remains an explicit
omission in `SOURCE.json`; this audit does not claim to inspect it.

Archive hashes in the generated inventory are the source archive digests recorded
by #292, not a new download verification. #236/#251 matched owner-published
digests during that import; #180 had no prior published archive digest. Matching
local manifests establishes retained-byte integrity, not independent proof of
capture provenance. Firmware-bundle hashes are different objects and must not be
substituted for raw-result archive hashes.

## What the traces actually contain

| Required information | #180 | #236 | #251 |
| --- | --- | --- | --- |
| Continuous `baro.asl`, `baro.pressure`, `baro.temp` | Absent | Absent | Absent |
| Accelerometer `acc.x/y/z` | Absent | Absent | Absent |
| Gyroscope `gyro.x/y/z` | Absent | Absent | Absent |
| Roll/pitch diagnostic | Present | Absent | Absent |
| Independent metric vehicle-Z trajectory | Not retained | Not retained | Not retained |
| Explicit measured mixed terrain/vehicle event | Not retained | Not retained | Not retained |

Header availability is reported from CSVs only. The cached #180 log TOC
`B411033C.json` lists `baro.*`, `acc.*` and `gyro.*` as available, but none of their
samples was captured. `motion.deltaX/deltaY` are optical-flow measurements, not
accelerometer measurements. `stateEstimate.z/vz` are the UKF output influenced
by ToF and cannot supply the requested independent input.

The potential substitutes are specifically insufficient:

- **#180 `sensorFilter.baroHeight`:** all 4,448 retained samples are exactly
  zero across calibration/A/B/C. In pinned upstream UKF source, `baroOut` is a
  static log variable with no assignment; the three S3 applicators do not add
  one. This is an inactive diagnostic, not zero barometric noise.
- **`sensorFilter.surfBaroD`:** S3's event-relative value is conditional on its
  detector path and its reset/restart baseline. It is not a continuous pressure
  series. It is identically zero in #180/#236/#251 stationary calibrations and
  in the valid #236 B/C controls. Those zeros cannot estimate sensor uncertainty.
- **#251 `baro0/baroDec`:** entry and eligible-decision snapshots are held between
  detector events. A1/A2 never reach `lateElig`; their `baroDec` remains zero.
  A3 reaches the late path and supplies useful snapshots, but no continuous
  stationary/vertical/mixed control stream for the same before/after statistic.

The complete-run START/END markers in #180 do not identify the start/end of each
physical transition. None of the retained result manifests includes a measured
vehicle-Z trajectory or a synchronized metric reference. The historical human
observations remain valid in their own scope; clearance or UKF Z must not be
relabelled as independent vehicle ground truth.

## Scientific consequence

The frozen statistic (0.5 s pre-event median; 0.5 s post-event median from
0.25–0.75 s after transition end; drift learned only from stationary calibration)
cannot be computed from the required raw signal. Neither an uncertainty bound
nor a bias/attitude-aware inertial displacement can be recovered from these
archives. The same missing inputs prevent evaluating the simple IMU/barometer-
only world-Z alternative.

Therefore no quantitative comparison against **5 cm / 1 s** is reported. This
is **UNPROVEN because inputs/reference are missing**, not a counterexample to all
possible IMU/barometer methods, nor evidence supporting a new terrain model.
Do not search for windows on A3, reconstruct a continuous barometer from held
snapshots, reuse ToF-derived VZ, or repeat generic S3-A/B/C to fill this gap.

## Smallest next experiment preparation

The next useful change is acquisition and offline analysis support using the
existing #251 firmware, with its historical parameters unchanged. A firmware
estimator patch or a new flash is not justified merely to expose these inputs:
the pinned firmware already declares them. Verify the live log TOC at setup;
missing or failed logging must stop preparation before a physical gesture.

Prepare one bounded props-off information checkpoint with:

1. Continuous `baro.asl/pressure/temp`, `acc.x/y/z`, `gyro.x/y/z`, roll/pitch,
   downward ToF and existing state/diagnostic fields. Preserve device log and
   host timestamps and explicitly distinguish log time from sensor producer
   time. Assess cadence, loss, duplicates and cross-block alignment before any
   inertial claim; ordinary 20 ms log samples do not automatically prove a
   faithful inertial replay. Each CRTP log block must fit the existing payload
   budget.
2. One stationary calibration of about 30 s, followed by one terrain, one true
   vertical and one mixed out-and-back case, both signs retained. Use a measured
   platform height H; in the mixed case independently measure vehicle movement
   near H/2. Keep at least 2 s stationary plateaus.
3. A metric guide or fixed-camera reference with resolution substantially better
   than 5 cm, synchronized event boundaries and stated measurement uncertainty.
   The reference serves analysis only. It must not be inferred from the same ToF
   or UKF output being evaluated.
4. An executable, frozen pressure statistic and, only if timing/bias/attitude
   support it, a separately bounded inertial calculation. All physical cases
   must traverse the same calculation without the existing UKF gate bypassing
   the vertical control. Missing inputs, reference or interpretable uncertainty
   produce UNPROVEN; a valid counterexample refutes the bounded candidate.
5. Exact request, firmware and capture-tool identity, expected-output validation
   and Controller-readable durable raw publication. Reuse #296's generic
   evidence mechanism once available; it is not a scientific dependency. Manual
   issue attachments alone are not the canonical publication path.

This document is preparation guidance, not an executable checkpoint request.
The acquisition/calculation support and exact artifact still require preparation
and independent validation before the trusted checkpoint mechanism can create
TEST_REQUIRED. Props stay removed; no motorized test follows automatically.

## Inspected primary code

- [Pinned firmware sensor logs and units](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/stabilizer.c):
  `acc.*` in g, filtered `gyro.*` in degrees/s, `baro.asl` in metres,
  pressure in mbar and temperature in Celsius.
- [Pinned UKF](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/estimator/estimator_ukf.c):
  `baroOut` and the `baroHeight` logging binding.
- Local S3 base and timing applicators at the evidence-state SHA above:
  conditional `surfaceBaroDelta`, SUSPECT baseline/restart and held decision
  snapshots. These code observations explain the columns; they are not physical
  proof of an independent estimator.
