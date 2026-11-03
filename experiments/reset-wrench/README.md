# #637 — public-API wrench feasibility laboratory (not production)

**Scope:** isolated Webots R2025a, single rigid body, mono-thread; read-only
physics plugin using public Webots/ODE functions. No Runtime/Grand Prix/CI
changes, no fix, no claims about the cause of RESET 337.

### Reproducible controls (only on independent resources)

From this directory, with the pinned Webots R2025a installed locally:

1. Build: make -C plugins/physics/reset_wrench WEBOTS_HOME="$WEBOTS_HOME"
2. Run worlds/wrench_control.wbt with environment
   WEBEEBLOCKS_WRENCH_CAPTURE=1, WEBEEBLOCKS_WRENCH_DEF=WRENCH_BODY,
   WEBEEBLOCKS_WRENCH_FILE=/absolute/unique/path/capture.csv.
   Choose a new output path for each run. The fixture applies one known
   torque and then teleports/resets a body into and out of floor contact.
3. Compare three variants, two independent controls each: the same
   world with WorldInfo.physics set to "" (OFF); plugin loaded with
   WEBEEBLOCKS_WRENCH_CAPTURE=0 (placebo); plugin loaded with capture=1.
   Pre-register six runs, exact commands/inputs and numerical tolerances.
4. Analyze: python3 analyze.py /absolute/unique/path/capture.csv --dt 0.032
   Test: python3 -m unittest discover -s . -p test_*.py
   Check controller tick markers, first actually integrated RESET step,
   ODE/output chronology, and expected free/contact residuals.

**Qualification is NOT established by these files.** In particular,
step_end precedes Webots postPhysicsStep RESET handling. MEASURED is
an aggregate residual, never proof of a stale contact, a cause or a fix;
missing/disabled phases and active damping/clamp give INDETERMINATE.
No added dCollide, dJointFeedback, setter, logging I/O or allocation per step.
Fixed 32768-frame capacity; overflow is PARTIAL_OR_UNKNOWN.
Crash may lose the in-memory trace. Keep existing P1 as fallback.

Do not acquire the historical autonomous scenario until the native six-run
control matrix and non-perturbation checks qualify the probe. Afterwards
permit at most one isolated natural acquisition, without CI reruns.
No generic recorder/replay/engine patch or product correction by default.
All FAILs and unknowns remain FAIL/UNPROVEN. No manual pupil/flight test.
