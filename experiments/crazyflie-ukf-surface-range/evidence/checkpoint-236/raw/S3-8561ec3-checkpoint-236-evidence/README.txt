Checkpoint #236 — s3-props-off — target 8561ec3e9609acc40677b88d98eada3aae0ad954

VALID:
- calibration: 22:16:14 / 22:16:15
- S3-A repeat 1: 22:20:53
- S3-A repeat 2: 22:26:25
- S3-B: 22:28:49 / 22:28:50
- S3-C valid slow: 22:38:15
- S3-A repeat 3: 22:43:38 / 22:43:39

EXCLUDED FROM VERDICT:
- 22:35:57 pair: operator error; intended S3-C was performed rapidly rather than over 4–6 s.
- original/S3-8561ec3-results.tar.gz: initial pre-recalibration batch retained for audit; estimator was already divergent/NaN and the batch is not decision evidence.

Parameters for valid runs: stabilizer.estimator=3, ukf.qualityGateTof=20, ukf.baroNoise=6.25, ukf.surfaceOffsetS3=1; resetEstimation pulsed before valid scenarios. Props removed throughout. No threshold retuning and no motorized test.
