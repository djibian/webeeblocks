# #637 — public-API wrench feasibility laboratory (not production)
Only an **independent** mono-thread Webots R2025a installation is eligible.
Read-only public Webots/ODE single-body probe; no product change or causal claim.
### Six native controls (not performed by this prototype)
1. Build: `make -C plugins/physics/reset_wrench WEBOTS_HOME="$WEBOTS_HOME"`.
2. World: `worlds/wrench_control.wbt`. Set `WRENCH_FIXTURE_MODE=free`
   or `reset_contact`; repeat each with physics OFF (`WorldInfo.physics ""`),
   placebo (physics plugin loaded, `WEBEEBLOCKS_WRENCH_CAPTURE=0`), and
   active (`WEBEEBLOCKS_WRENCH_CAPTURE=1`). Set `WEBEEBLOCKS_WRENCH_DEF=WRENCH_BODY`
   and unique absolute `WEBEEBLOCKS_WRENCH_FILE` for active captures.
3. Pre-register tolerance/frames; compare per-tick `WRENCH_WITNESS` Supervisor
   states across modes; align them with plugin pre/step_end including RESET.
4. `python3 analyze.py CAPTURE.csv --dt 0.032`; offline regression:
   `python3 -m unittest discover -s . -p test_*.py`.
Step_end precedes Webots RESET postPhysicsStep; a RESET phase can be
`INDETERMINATE`. `MEASURED` is only an aggregate force/torque residual, never
proof of stale contacts or a fix. No per-step I/O/ODE setter/collision call.
Fixed 32768-frame buffer; overflow or malformed capture is `PARTIAL_OR_UNKNOWN`.
Crash can lose memory trace. Keep P1; never weaken safety/RESET oracles.
**Stop** unless six native checks, phasing and OFF/placebo/ON non-perturbation
qualify the probe. Then at most one natural isolated autonomous acquisition.
No runner/GPU/cache sharing, CI, PR, deep recorder, engine fork or auto-fix.
