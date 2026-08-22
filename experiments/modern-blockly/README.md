# Modern Blockly foundation experiment (#55)

Status: isolated experiment only. This branch must not modify `webots-ci` or `main`.

## Gate
Runtime v2 Webots/WWI #53 is technically converged and merged. Verification proved the causal Runtime v2 chain on head `914d7944…`; the local Ubuntu/Webots baseline remains a promotion gate only.

## Fixed semantic boundary
`activity -> Blockly -> webeeblocks-ast-v1 -> preflight -> interpreter -> backend`

Runtime v2 must not reintroduce Python generation.

## Baseline dependency hypothesis
Start with pinned `blockly@13.2.1` from npm and a reproducible local bundle/build suitable for a Webots Robot Window. Do not rely on CDN/network access at runtime.

## Small discriminating matrix
Use one identical reactive Crazyflie program and one identical activity profile for every variant.

1. Dependency/build: prove a pinned npm dependency can be bundled into a self-contained Robot Window asset and initialized offline.
2. Semantic equivalence: compile the same acceptance workspace and require the same `webeeblocks-ast-v1` semantics as the current Runtime v2 fixture.
3. Activity toolbox: generate visible toolbox and numeric/dropdown constraints from the same resolved activity profile; forbidden blocks/capabilities remain fail-closed in preflight.
4. Serialization: JSON workspace save/load is canonical for new v2 projects. Import one historical XML fixture, compile it to the same AST, then save it as JSON and re-load with identical AST.
5. Accessibility/keyboard: exercise keyboard-only block navigation/editing and record focus/operation failures; do not add the legacy keyboard-navigation plugin unless a demonstrated gap requires it.
6. Renderer A/B: run the exact same workspace under `thrasos` and `zelos`. Compare block density/readability at the same viewport, field editing, mouse manipulation, keyboard focus/navigation, and any clipping/Robot Window rendering defects. Renderer choice must not change AST.

## Pre-registered decision rules
- Prefer the smallest reproducible dependency/build that works offline in the Robot Window and is maintainable through npm version pinning.
- Reject any variant that changes AST semantics, weakens profile/preflight enforcement, or requires Python generation.
- Prefer JSON for new Runtime v2 saves; keep XML only as an import/migration compatibility path.
- Prefer Thrasos by default because Blockly documents it as the recommended renderer; choose Zelos only if the same-program school-use comparison demonstrates a concrete usability advantage without regressions.
- Accessibility failures are blocking evidence for the tested interaction, not a reason to disable accessibility features.

## Non-goals
No new drone capabilities, teacher authoring UI, physical Crazyflie work, Runtime v1 removal, broad visual redesign, or product merge.

## Stop criterion
Freeze the experiment once the six questions above have discriminating evidence. Product promotion remains blocked until Emmanuel's local Runtime v2 baseline validation is satisfactory.