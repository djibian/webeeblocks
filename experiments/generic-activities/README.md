# Generic activity profiles — experiment

## Question

Can WebeeBlocks separate an activity definition from the hard-coded Crazyflie challenge UI, so that the same Webots world can be reused with different briefs, toolboxes and evaluation contracts?

## Prototype

`activities.json` declares activity profiles. `activity_profile.js` validates and resolves one profile against an explicit block catalog. The resolver is deliberately independent of Webots and of the Blockly DOM: this first experiment tests the configuration boundary before changing the release-candidate interface.

The two sample activities reuse `worlds/crazyflie_runtime_obstacle.wbt` but differ in brief visibility, toolbox contents, hardware declaration, timer and evaluation contract.

## Proven by the executable test

`node experiments/generic-activities/test_activity_profile.js`

The test proves that:

- two profiles can reuse the same world;
- the current four-block Crazyflie palette can be retained unchanged for one profile;
- another profile on that same world can expose a different palette;
- the in-interface brief can be visible or completely hidden;
- parameter bounds are carried by the resolved block configuration;
- unknown blocks and bounds targeting hidden blocks fail closed.

## Explicit limits

This experiment does **not** change `blockly.html`, Webots worlds, mission runtime or the frozen `webots-ci` release candidate. It does not claim that conditional Crazyflie missions are executable: the second sample profile labels that capability as an experimental requirement.

A later experiment may connect this resolver to a disposable UI harness and prove dynamic toolbox/brief rendering. That should happen only on an experimental branch and must not be merged into `webots-ci` before the human-trial feedback and Lead arbitration.
