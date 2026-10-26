# Exact WBB layout: pupil procedures without overlaps

Baseline main 17671d18723c858ea873311a545d8c65b97b877e.
Source algorithm 032edffeff44881615e379a4ab86cc5bfd10ad79, 234 blocks / 10 variables / 4 ordinary procedures.
Only the five root x/y positions differ from the original 234 serialized WBB.
Real Chrome layout 403? verified predecessor showed a safe five-root arrangement using descendants, not just headers.
This candidate persists that arrangement in the actual .wbb so a student can click without a hidden script packing it.
Five roots: main (20,20), final (20,550), one-side (970,20), observation (2620,20), crossing (2620,740).
Program logic, conditions, comparisons, AST, sensor ambiguity, gate memory and all controls are unchanged.
Real Blockly and full R2025a 16-case qualification rerun on exact SHA/WBB; original UI test must reject overlaps without moving any root.
Horizontal scrolling is still required, and human construction/debug has not been demonstrated.
No GO, no owner PASS, no fusion and no TEST_REQUIRED.