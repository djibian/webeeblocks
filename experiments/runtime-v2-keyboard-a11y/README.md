# Runtime v2 keyboard/accessibility experiment

## Question

With the current Runtime v2 Robot Window and pinned Blockly 13.2.1, can a user reach Blockly with real keyboard events and obtain useful navigation/accessibility semantics **without any WebeeBlocks product change**?

## Scope

This experiment starts from the current `webots-ci` product after #62. It keeps the current renderer unchanged and runs the real `blockly_v2` Robot Window through Webots R2025a.

The probe uses Chrome DevTools Protocol only as test instrumentation to inject real keyboard events and inspect focus/ARIA state. The Robot Window, Blockly workspace, activity profile, AST/runtime code and Webots controller are the product versions from `webots-ci`.

The experiment first runs with Blockly exactly as productized. If keyboard-only toolbox focus is not obtainable, it calls only Blockly core `Blockly.ShortcutItems.registerNavigationShortcuts()` and repeats the same probe. This is a discriminating experiment, not a proposed product fix.

## Evidence collected

- pinned runtime `Blockly.VERSION`;
- active-element/focus path after Tab navigation;
- toolbox/category focus observation;
- Blockly keyboard accessibility mode;
- registered shortcut names;
- count of DOM nodes exposing ARIA roles/labels;
- whether the same probe improves after `registerNavigationShortcuts()`.

## Non-goals

- no renderer comparison (Thrasos/Zelos comes later);
- no product accessibility patch;
- no new block, activity, AST, backend, PID/STOP or world;
- no Runtime v1 change;
- no physical Crazyflie;
- no merge to `main`.

## Interpretation

A green gate proves only the observed keyboard/ARIA contract exercised by this probe. If both native and `registerNavigationShortcuts()` paths fail to provide useful toolbox focus, the experiment should remain red/UNPROVEN and the next step belongs to Lab/Verification rather than adding arbitrary shortcuts.
