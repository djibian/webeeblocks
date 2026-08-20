# Generic activity profiles — experiment

## Question

Can WebeeBlocks separate an activity definition from the hard-coded Crazyflie challenge UI, so that the same Webots world can be reused with different briefs, toolboxes and evaluation contracts?

## Prototype

`activities.json` declares activity profiles. `activity_profile.js` validates and resolves one profile against an explicit block catalog. The resolver is deliberately independent of Webots and of the release-candidate Blockly DOM.

The two sample activities reuse `worlds/crazyflie_runtime_obstacle.wbt` but differ in brief visibility, toolbox contents, hardware declaration, timer and evaluation contract. The preview profile also deliberately narrows the real numeric ranges (`forward` max 1.5 m, `turn` max +90°) so the UI experiment can prove that profile bounds are actually applied rather than merely carried as metadata.

## Executable proof 1 — pure resolver

```bash
node experiments/generic-activities/test_activity_profile.js
```

This proves that:

- two profiles can reuse the same world;
- the current four-block Crazyflie palette can be retained unchanged for one profile;
- another profile on that same world can expose a different palette;
- the in-interface brief can be visible or completely hidden;
- parameter bounds are carried by the resolved block configuration;
- the same registered block can receive different bounds in different profiles;
- unknown blocks and bounds targeting hidden blocks fail closed.

## Executable proof 2 — disposable real-Blockly harness

`ui_harness.html` loads the **actual Blockly 2020 build and actual Crazyflie block definitions from this repository**. It does not import or modify the frozen `blockly.html` product page.

Serve the repository root and open:

```text
experiments/generic-activities/ui_harness.html
```

or, on a machine with Chrome/Chromium available:

```bash
python3 experiments/generic-activities/run_ui_harness.py
```

The harness switches profiles at runtime and fails closed unless it can prove all of the following against real Blockly objects:

- every profile-exposed block type is actually registered by the loaded Blockly build;
- the real flyout contents equal the selected profile toolbox;
- the visible challenge brief appears for the time-trial profile and is fully hidden for the preview profile;
- both profiles still point to the exact same Webots world;
- profile-specific bounds are applied through the real `Blockly.FieldNumber.setConstraints()` API;
- the preview profile really clamps a `turn` value of +135° to its declared +90° maximum;
- unsupported evaluation/timer contracts are rejected by the harness rather than silently treated as executable.

The harness then switches back to the time-trial profile and verifies that its brief and toolbox are restored.

## Explicit limits

This experiment does **not** change `blockly.html`, Webots worlds, mission runtime or the frozen `webots-ci` release candidate. It does not claim that conditional Crazyflie missions are executable: the second sample profile labels that capability as an experimental requirement.

`hardware`, `timer` and `evaluation` are still declarative contracts, not a generic runtime implementation. The browser harness validates only the two contract forms it explicitly knows how to represent and deliberately rejects unknown ones.

This draft must not be merged into `webots-ci` before human-trial feedback and Lead arbitration.
