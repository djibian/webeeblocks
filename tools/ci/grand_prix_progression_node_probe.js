// Native Grand Prix lesson missions and counterexamples through the ordinary WWI backend.
'use strict';
const assert = require('node:assert/strict');
const {setTimeout: delay} = require('node:timers/promises');
const Backend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const robot = 'Crazyflie WebeeBlocks';
const socket = new WebSocket('ws://127.0.0.1:' + Number(process.argv[2]) + '/');
const send = payload => socket.send('robot:' + robot + ':' + payload);
const backend = new Backend({send}, {
  simulationStop: true, simulationReset: true, simulationAdmission: true,
  routeTakeoffTimeoutMs: 90000
});
const evaluation = {type: 'mission-state-v1', oracle: 'grand-prix-route-v2'};
let forcedLandings = 0;

socket.onmessage = event => {
  for (const line of String(event.data).split(/\r?\n/)) {
    if (line.startsWith('robot:')) {
      const reply = JSON.parse(line.slice(6));
      if (reply.name !== robot)
        continue;
      if (reply.message === 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 OK')
        forcedLandings++;
      backend.handleMessage(reply.message);
    }
  }
};
socket.onerror = () => {
  console.error('Real Webots WWI connection failed');
  process.exit(1);
};

async function takeoff(height) {
  await backend.takeoff(height);
  await backend.setSpeed(.2);
}

async function approachLastLeg() {
  await takeoff(.9);
  await backend.move('forward', 1.4);
  await backend.turn(90);
  await backend.move('forward', 1.8);
  await backend.turn(-90);
}

// RESET is explicitly fenced until the independent forced LAND has finished.
async function waitForForcedLanding(expectedCount) {
  const deadline = Date.now() + 35000;
  while (forcedLandings < expectedCount && Date.now() < deadline)
    await delay(50);
  assert.equal(forcedLandings, expectedCount, 'native forced LAND did not complete');
}

async function outcome(expected) {
  const deadline = Date.now() + (expected.reason === 'time-limit' ? 240000 : 15000);
  while (Date.now() < deadline) {
    try {
      const actual = await backend.readActivityOutcome(evaluation);
      assert.deepEqual(actual, expected);
      console.log(JSON.stringify(actual));
      return;
    } catch (error) {
      if (error.code !== 'OUTCOME_UNAVAILABLE')
        throw error;
      await delay(50);
    }
  }
  assert.fail('Native mission outcome unavailable');
}

async function activityOne() {
  await approachLastLeg();
  await backend.move('forward', .9);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.4);
  await assert.rejects(backend.move('forward', .8), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'low-outside-zone'});
  await waitForForcedLanding(1);

  await backend.resetSimulation();
  await approachLastLeg();
  await assert.rejects(backend.move('forward', 1.6), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'envelope-contact'});
  await waitForForcedLanding(2);

  await backend.resetSimulation();
  await takeoff(.9);
  await backend.stopSimulation();
  await assert.rejects(backend.move('forward', .2), {code: 'USER_STOPPED'});
  await waitForForcedLanding(3);

  await backend.resetSimulation();
  await takeoff(.9);
  await outcome({status: 'not-achieved', reason: 'time-limit'});
  await waitForForcedLanding(4);
  await assert.rejects(backend.move('forward', .2), {code: 'TIME_LIMIT'});
}

async function activityTwo() {
  await takeoff(.88);
  await backend.move('forward', .44);
  await backend.vertical('down', .41);
  await backend.move('forward', .74);
  await backend.vertical('up', .41);
  await backend.move('forward', .62);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await takeoff(.4);
  await assert.rejects(backend.move('forward', .6), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'low-outside-zone'});
  await waitForForcedLanding(1);

  await backend.resetSimulation();
  await takeoff(.88);
  await assert.rejects(backend.move('forward', 1.1), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'envelope-contact'});
  await waitForForcedLanding(2);
}

async function activityThree() {
  await takeoff(.88);
  async function traverseGate() {
    await backend.turn(90);
    await backend.move('forward', .44);
    await backend.vertical('down', .41);
    await backend.move('forward', .74);
    await backend.vertical('up', .41);
  }
  for (let leg = 0; leg < 2; leg++) {
    await traverseGate();
    await backend.move('forward', .32);
  }
  await traverseGate();
  await backend.move('forward', .10);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await takeoff(.88);
  await backend.turn(-90);
  await assert.rejects(backend.move('forward', .6), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'course-boundary'});
  await waitForForcedLanding(1);
}

async function activityFour() {
  async function approachLanding(side) {
    await takeoff(.9);
    // The same policy runs unchanged. Only the standard forward range is
    // available to it, with no course identity or host coordinates.
    const front = await backend.readRange('front');
    assert(Number.isFinite(front) && front > .8 && front < 1.9, 'H must be observable');
    const distance = front < 1.16 ? .30 : front < 1.56 ? .70 : 1.10;
    console.log(JSON.stringify({front, distance, side}));
    await backend.move('forward', distance);
    await backend.move(side, .50);
    await backend.land();
    await backend.completeActivityMission(evaluation);
  }

  await approachLanding('left');
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await approachLanding('right');
  await outcome({status: 'not-achieved', reason: 'wrong-landing'});
  await waitForForcedLanding(1);
}

const scenarios = {'1': activityOne, '2': activityTwo, '3': activityThree, '4': activityFour};
const scenario = Object.hasOwn(scenarios, process.argv[3]) && scenarios[process.argv[3]];
assert.equal(typeof scenario, 'function', 'Pass the bounded native activity number');
socket.onopen = async () => {
  try {
    send('init robot window');
    await backend.waitUntilReady();
    await scenario();
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  } finally {
    socket.close();
  }
};
