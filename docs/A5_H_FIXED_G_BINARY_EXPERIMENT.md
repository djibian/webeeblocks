# Activity 5 — independent H-fixed / G-binary first hypothesis

**NOT QUALIFIED — source-only Draft experiment, not a pupil activity, GO, or native PASS.**

The approved activity 5 introduces repeated observation and then one useful state
variable. Historical #980 and #1025 show that a second L or a late detour can
reveal the initial destination clue without stored state. The next design must
separate the information roles rather than hide evidence or enforce Blockly AST
syntax.

## Physical proposal (first of two independent factors)

H is an identical, real L-shaped initial cue in BOTH experimental scenes:
arm (0.00,+0.58), tip (+0.20,+0.78), height 1.10 m.
It determines the **future landing destination** only. Two identical visible pads
at (4.15,+0.62) and (4.15,-0.62) avoid giving the destination away locally.
The starting point (0,0) and common approach marker (2.50,0) are identical.

G lies downstream around x=3.10, out of the 2 m frontal sensor range at
the start. Its 1.10 m tall collision-box walls leave a 0.62 m-class aperture
around y=+0.60 (G-left) or y=-0.60 (G-right), with common side boundaries
at y=±1.45. A physical side arm at x=2.45,y=-0.58 / +0.58 should make
the G variant observable from the approach via the **left** range sensor
without changing the original H measurement. The chosen aperture is independent
of the initial H; no virtual labels or hidden course metadata reach Blockly.

The actual aperture clearances, sensor readings and achievable trajectories are
**proposals** until measured. The authored source WBOs do not create a valid
activity or independently validate collision avoidance. The experimental
classroom Floor must be enlarged by an isolated CI world composer before
motorized trials, not by changing the official Grand Prix world.

## Native R2025a falsification checkpoints, in order

1. Embed each WBO in an isolated original-Crazyflie Webots R2025a world and
   attest its real Solids and bounding boxes. Keep H and pads byte-identical.
2. From the identical start (0,0,z≈0.50), require equal front/left sensor
   observations across both G variants and a valid initial H reading. Refuse
   a gate already visible or a missing/nonfinite native sensor.
3. Near x≈2.50,y=0, require a real **left** range difference (G-right physical
   arm versus G-left boundary), then compare the front rays from positions
   (2.50,+0.80) and (2.50,-0.80). A G-fixed blind choice must fail at one gate.
4. Drive actual PID paths through both apertures, with native continuous
   contact/swept-geometry evidence, correct Floor landing and negative oracles.
   Test out-of-corridor, high-flight bypass, no sensing and return/backtracking.
5. Only after the H-fixed/G-variable native pair passes, design an H-near/H-far
   pair with G fixed, then compose the **four variants** H×G. Compare strategies
   with stored state, branch duplication, late clue re-reading and return.
   Build and reopen a single actual **Blockly** .wbb across all variants.

**Scientific limitation:** with finitely many variants, control-flow branching
can carry a remembered choice without a variable; functional usefulness means
reducing duplication and sharing a reactive loop, not universal necessity
of a specific AST block. The native tests and the teacher's 4e/3e acceptance
remain separate. This Draft changes no activity 8 world, oracle, performance,
physical firmware, or classroom published starter.
