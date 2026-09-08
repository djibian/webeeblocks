# S3 veto discriminator — props-off, reason split only

## Purpose

Checkpoint #180 refuted the S3 terrain classifier because `surfReason=3` (`VERTICAL_VETO`) dominated the terrain SUSPECT interval even though the local-range candidate reached the expected surface-step magnitude. The existing reason code aggregates two already-present cues:

`abs(vz) >= 0.08 m/s || abs(surfaceBaroDelta) >= 0.08 m`.

The retained archive cannot currently be consumed through the available machine path. This discriminator therefore changes **observability only** so that one later props-off trace can identify which existing cue vetoes terrain.

## Exact instrumentation change

Apply the existing `apply_surface_offset_s3.py` first to the exact Crazyflie firmware 2026.08 source boundary, then apply `apply_surface_offset_s3_veto_discriminator.py`.

The overlay preserves the exact commit predicate and every existing numerical constant. It only emits distinct `sensorFilter.surfReason` values:

- `6` — `VZ_VETO`: `abs(vz) >= 0.08 m/s` only;
- `7` — `BARO_VETO`: `abs(surfaceBaroDelta) >= 0.08 m` only;
- `8` — `BOTH_VETO`: both predicates true.

Legacy reason `3` remains defined for provenance but is no longer emitted by the split instrumentation. Existing reason codes `0`, `1`, `2`, `4`, and `5` retain their meanings.

## Frozen boundaries

Do not change `qualityGateTof=20`, `baroNoise=6.25`, `surfaceOffsetS3=1`, `S3_VZ_VERTICAL_VETO_MPS=0.08`, `S3_BARO_VERTICAL_VETO_M=0.08`, any settle/persistence/window constant, estimator state dimension, local-range Flow path, controller, Runtime v2, or deck cue set. Do not add `rangeUp`. Props remain removed. No motorized test follows automatically.

## Smallest physical discriminator

Only after the globally serialized human-checkpoint slot is free, repeat the already established props-off geometry with the instrumented reason codes:

1. stationary calibration >=10 s;
2. S3-A: fixed-world-height floor -> raised platform -> floor;
3. S3-B: flat-floor true vertical motion;
4. S3-C: slow flat-floor true vertical motion.

Keep the existing 20 ms logging surface, including `stateEstimate.vz`, `sensorFilter.surfBaroD`, `surfState`, `surfReason`, `surfCand`, `surfOffset`, raw/local range, ToF diagnostics and the existing provenance/configuration evidence.

## Pre-registered decision table

- Terrain S3-A dominated by `VZ_VETO`, while S3-B/S3-C also require VZ veto: the current UKF vertical-velocity estimate is not a discriminating terrain cue at the commit boundary. Do not tune its threshold from the outcome; redesign the classifier evidence before another terrain candidate.
- Terrain S3-A dominated by `BARO_VETO`, while S3-B/S3-C correctly require barometer veto: the raw-relative-barometer delta is not discriminating enough in the present temporal alignment. Do not tune its threshold from the outcome; redesign timing/evidence semantics before another candidate.
- Terrain S3-A dominated by `BOTH_VETO`: both current cues confound the terrain transition; no threshold sweep is justified.
- S3-A reaches commit eligibility without any of `6/7/8` yet still does not commit: investigate the next existing commit predicate from the same trace before changing estimator structure.
- Any S3-B/S3-C false terrain commit remains an immediate refutation.

## Status

`Lab only`. This branch is experimental evidence preparation and is not a product Runtime change. It does not authorize flight or a checkpoint while another `TEST_REQUIRED` is open.
