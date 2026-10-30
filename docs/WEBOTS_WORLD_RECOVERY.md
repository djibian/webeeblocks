# Webots R2025a — separate world reload recovery (#637)

A failed strict RESET is still a failure. **Reconstruire** persists the
unsaved Blockly workspace and activity ID to browser localStorage, then
revokes old WWI commands and invokes the official Webots world reload via
the native Supervisor. The old process cannot acknowledge reconstruction.

A new Robot Window restores the program, verifies two nonce-correlated
**unchanged strict RESETs** bracketing scene restoration and independent
scene acknowledgements, checks the Blockly serialization unchanged,
clears its checkpoint and allows an **explicit** new execution. All
remaining errors leave Run locked. No .wbb disk file is modified.
After restart the lost in-memory Save file handle requires
**Enregistrer sous** to persist recovered unsaved changes.

Strict RESET remains 5s/250ms; existing collision negatives and LAND
rules remain. The new native CI test forces the separate recovery path
after a *real* unsafe/collision program; it does not claim to reproduce
the historical intermittent RESET_TIMEOUT. It must demonstrate a new
world, postconditions, restored Blockly and an actual second colliding
Blockly execution. Failure to preserve browser localStorage origin is
a refutation, not a reason to relax the gate. Windows remains separately
unproven by a Linux run. #637/#665 stay open.

Debt is locally removable: delete RELOAD_WORLD, correlated recovery
RESET extension, checkpoint/UI code and recovery-only test after a
future official Webots release makes the original strict RESET reliable.
No Webots or physical backend is modified. V5 exact-HEAD CI, independent
review and explicit owner permission are prerequisites to merge.
