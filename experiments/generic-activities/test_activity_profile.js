const fs = require('fs');
const path = require('path');
const assert = require('assert');
const profiles = require('./activity_profile.js');

const document = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'activities.json'), 'utf8')
);

const catalog = {
  webeeblocks_takeoff: {category: 'Crazyflie'},
  webeeblocks_forward: {category: 'Crazyflie'},
  webeeblocks_turn: {category: 'Crazyflie'},
  webeeblocks_land: {category: 'Crazyflie'},
  controls_if: {category: 'Control'},
  logic_compare: {category: 'Control'}
};

function run() {
  const timeTrial = profiles.resolveById(document, 'obstacle-time-trial-v0', catalog);
  const algorithm = profiles.resolveById(document, 'obstacle-algorithm-preview', catalog);

  assert.strictEqual(timeTrial.world, algorithm.world,
    'two profiles should be able to reuse the same world');

  assert.deepStrictEqual(
    timeTrial.toolbox.map(block => block.type),
    [
      'webeeblocks_takeoff',
      'webeeblocks_forward',
      'webeeblocks_turn',
      'webeeblocks_land'
    ],
    'time-trial profile must preserve the current four-block palette'
  );

  assert.deepStrictEqual(
    algorithm.toolbox.map(block => block.type),
    [
      'webeeblocks_takeoff',
      'webeeblocks_forward',
      'webeeblocks_turn',
      'webeeblocks_land',
      'controls_if',
      'logic_compare'
    ],
    'another profile on the same world must be able to expose a different palette'
  );

  assert.strictEqual(timeTrial.brief.visible, true,
    'activity may expose an in-UI brief');
  assert.deepStrictEqual(algorithm.brief, {visible: false},
    'activity may hide the in-UI brief completely');

  assert.deepStrictEqual(
    timeTrial.toolbox.find(block => block.type === 'webeeblocks_forward')
      .parameterBounds.DISTANCE,
    {min: 0.1, max: 2.0, step: 0.1},
    'parameter bounds must travel with the resolved block definition'
  );

  assert.strictEqual(timeTrial.timer.enabled, true);
  assert.strictEqual(algorithm.timer.enabled, false);
  assert.strictEqual(timeTrial.evaluation.type, 'ordered-gates-no-collision');
  assert.strictEqual(algorithm.evaluation.type, 'teacher-defined');

  const bad = JSON.parse(JSON.stringify(document.activities[0]));
  bad.id = 'bad-unknown-block';
  bad.toolbox.push('future_block_not_in_catalog');
  assert.throws(
    () => profiles.resolveProfile(bad, catalog),
    /unknown block type/,
    'a profile must fail closed when it asks for an unknown block'
  );

  const badBounds = JSON.parse(JSON.stringify(document.activities[0]));
  badBounds.id = 'bad-hidden-bounds';
  badBounds.toolbox = badBounds.toolbox.filter(type => type !== 'webeeblocks_turn');
  assert.throws(
    () => profiles.resolveProfile(badBounds, catalog),
    /parameter bounds declared for hidden block/,
    'bounds must not silently target a block hidden by the activity'
  );

  console.log('PASS generic activity profile prototype');
  console.log('same world:', timeTrial.world);
  console.log('time-trial blocks:', timeTrial.toolbox.length);
  console.log('algorithm-preview blocks:', algorithm.toolbox.length);
}

run();
