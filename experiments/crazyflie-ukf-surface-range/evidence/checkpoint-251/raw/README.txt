WebeeBlocks #251 — X3 timing provenance evidence bundle
=======================================================

Target SHA:
6562ad827bf0c8bf2c9b609edad36f3e15652133

Profile:
s3-props-off

Checkpoint artifact:
experimental-s3-surface-offset-2026-08
Artifact ID: 10089812000
Artifact digest:
sha256:c7b9b9143118fb7572e7b23a7f61e9936f220a1eb5f56e98ea39852f52c39cc3

Configuration:
stabilizer.estimator = 3
ukf.qualityGateTof   = 20
ukf.baroNoise        = 6.25
ukf.surfaceOffsetS3  = 1
Props removed throughout.

Evidence retained:
- 00_precheck_excluded/: first stationary precheck, excluded because estimator had already drifted before usable calibration.
- 01_calibration_valid/: fresh-reset stationary validation; z stable about 0.727–0.738 m, vz about -0.019 to +0.009 m/s, innoChTof < 20, no NaN.
- A1/: complete terrain traversal. lateElig never reached; SUSPECT entry provenance usable.
- A2/: complete terrain traversal. lateElig never reached; SUSPECT entry provenance usable.
- A3/: complete terrain traversal. lateElig reached; decision provenance (*D) populated. First surface transition committed surfOffset about +0.201 m; return transition later remained vetoed.

Key X3 observations:
A1 entry/restart:
  tofAge0 1/0 ms; baroAge0 17/13 ms; baroLag0 33/25; baroSeen0=1; vz0 about -0.074/-0.113 m/s.
  lateElig=0 throughout; baroSeenD remains unset.

A2 entry/restart:
  tofAge0 0/0 ms; baroAge0 16/7 ms; baroLag0 31/13; baroSeen0=1; vz0 about -0.087/-0.144 m/s.
  lateElig=0 throughout; baroSeenD remains unset.

A3:
  first SUSPECT entry: tofAge0=0 ms; baroAge0=16 ms; baroLag0=31; baroSeen0=1; vz0 about -0.052 m/s.
  first late-decision snapshots: tofAgeD 0–1 ms; baroAgeD 7–8 ms; baroLagD 13–15; baroSeenD=1; vzDec about +0.054 to +0.058 m/s.
  second SUSPECT entry: tofAge0=1 ms; baroAge0=17 ms; baroLag0=33; baroSeen0=1; vz0 about +0.0067 m/s.
  second late-decision interval: tofAgeD 0–1 ms; baroAgeD 1–20 ms; baroLagD 1–39; baroSeenD=1; vzDec eventually falls to about -0.183 m/s.

Observer note:
Some NOW samples in A2/A3 report tofAge=4294967295, consistent with a -1 ms unsigned wraparound. This is retained as an observer-timestamp anomaly and was not used to retune or alter the classifier.

Interpretation:
The checkpoint is PASS informational: all three terrain repetitions are retained; required provenance is observable; A3 exercises the late-decision path and populates *D snapshots. This does NOT validate the classifier and does not authorize threshold retuning, motorized testing, estimator changes, new cues, or Runtime/controller changes.
