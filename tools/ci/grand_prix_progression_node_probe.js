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
let forcedLandingError;

socket.onmessage = event => {
  for (const line of String(event.data).split(/\r?\n/)) {
    if (line.startsWith('robot:')) {
      const reply = JSON.parse(line.slice(6));
      if (reply.name !== robot)
        continue;
      if (reply.message === 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 OK')
        forcedLandings++;
      if (typeof reply.message === 'string' &&
          reply.message.startsWith('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 ERR '))
        forcedLandingError = reply.message;
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
  while (forcedLandings < expectedCount && !forcedLandingError && Date.now() < deadline)
    await delay(50);
  assert.equal(forcedLandingError, undefined, 'native forced LAND failed');
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

async function activityFive() {
  async function reachChoice() {
    await takeoff(.9);
    const front = await backend.readRange('front');
    // These intervals are based on rays from the fixed start. Course
    // identity and turn direction are never supplied to the witness.
    const lengths = [1, 1.2, 1.4, 1.6];
    const index = [1.38, 1.58, 1.78, 1.94].findIndex(bound => front < bound);
    await backend.move('forward', index < 0 ? 1.8 : lengths[index]);
    const right = await backend.readRange('right');
    const left = await backend.readRange('left');
    assert((right < .45) !== (left < .45), 'Exactly one side must see the corner');
    const turnedLeft = right < .45;
    console.log(JSON.stringify({front, left, right, turnedLeft}));
    await backend.turn(turnedLeft ? 90 : -90);
    await backend.move('forward', 1.85);
    await backend.move('forward', .51);
    const choice = {};
    for (const direction of ['front', 'back', 'left', 'right'])
      choice[direction] = await backend.readRange(direction);
    console.log(JSON.stringify({choice}));
    assert(choice.front > .11 && choice.front < .26, 'Expected the H at the choice');
    for (const direction of ['back', 'left', 'right'])
      assert(choice[direction] >= 1.99, direction + ' still sees the earlier corner');
    return turnedLeft;
  }

  const turnedLeft = await reachChoice();
  await backend.move(turnedLeft ? 'right' : 'left', .50);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  const turnedLeftAgain = await reachChoice();
  await backend.move(turnedLeftAgain ? 'left' : 'right', .50);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'not-achieved', reason: 'wrong-landing'});
  await waitForForcedLanding(1);
}

async function activitySix() {
  await takeoff(.90);
  const first = await backend.readRange('front');
  assert(first > .65 && first < 2, 'takeoff range saturated');
  console.log(JSON.stringify({first}));
  const mayBeOpen = first < 1.2;
  const distance = mayBeOpen ? (first < .8 ? .59 : first < .95 ? .74 : .89) : 1.8;
  await backend.move('forward', distance);
  const left = await backend.readRange('left');
  const right = await backend.readRange('right');
  const open = left < .45 && right < .45;
  console.log(JSON.stringify({left, right, open}));
  assert.equal(open, mayBeOpen);
  if (open) {
    await backend.vertical('down', .42);
    await backend.move('forward', .60);
    await backend.vertical('up', .42);
    const next = await backend.readRange('front');
    console.log(JSON.stringify({next}));
    assert(next > .8 && next < 1.5, 'terminal H required after clearing');
    await backend.move('forward', next < 1.12 ? .41 : next < 1.22 ? .51 : .61);
  } else {
    async function oppositeRays(expectedSide) {
      const left = await backend.readRange('left');
      const right = await backend.readRange('right');
      console.log(JSON.stringify({left, right, closedHeading:expectedSide}));
      assert.equal(left < .45, expectedSide === 'left');
      assert.equal(right < .45, expectedSide === 'right');
    }
    await backend.turn(45);
    await oppositeRays('right');
    await backend.turn(-90);
    await oppositeRays('left');
    await backend.turn(45);
    await backend.move('back', .49);
  }
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await takeoff(.90);
  await assert.rejects(async () => {
    await backend.move('forward', 1.90);
    await backend.move('forward', .30);
  }, {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'envelope-contact'});
  await waitForForcedLanding(1);
}

async function activitySeven() {
  async function range(direction = 'front') { return backend.readRange(direction); }
  async function advanceWhile(direction, distance, condition, limit) {
    let iterations = 0;
    while (await condition()) {
      assert(iterations++ < limit, 'bounded approach exhausted');
      await backend.move(direction, distance);
    }
  }
  async function observe() {
    return {front: await range(), left: await range('left'), right: await range('right')};
  }
  async function reachObstacle() {
    await advanceWhile('forward', .24, async () => await range() > .46, 14);
    let ranges = await observe();
    for (let fine = 0; fine < 14 && ranges.front > .16 &&
         ranges.left > .45 && ranges.right > .45; fine++) {
      await backend.move('forward', .05);
      ranges = await observe();
    }
    // Near a frame, one ray can see its post just before the other. Do not
    // commit to a classification until both have had a chance to see it.
    for (let fine = 0; fine < 4 && ranges.front > .16 && ranges.front < .25 &&
         (ranges.left > .45 || ranges.right > .45); fine++) {
      await backend.move('forward', .04);
      ranges = await observe();
    }
    return ranges;
  }
  async function approachEndOfLeg() {
    let obstacle = await reachObstacle();
    if (obstacle.left < .45 && obstacle.right < .45) {
      await advanceWhile('forward', .04, async () => await range() > .16, 12);
      await backend.vertical('down', .42);
      await backend.move('forward', .60);
      await backend.vertical('up', .42);
      obstacle = await reachObstacle();
    }
    console.log(JSON.stringify(obstacle));
    return obstacle;
  }
  await takeoff(.90);
  const corner = await approachEndOfLeg();
  assert((corner.left < .45) !== (corner.right < .45), 'outer corner requires one side');
  await advanceWhile('forward', .06, async () => await range() > .30, 10);
  await advanceWhile('back', .04, async () => await range() < .27, 8);
  await backend.turn(corner.right < .45 ? 90 : -90);
  const closed = await approachEndOfLeg();
  assert(closed.front < .19 && closed.left > .45 && closed.right > .45, 'closed H');
  await advanceWhile('back', .13, async () => await range() < .65, 8);
  await advanceWhile('forward', .05, async () => await range() > .71, 8);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await takeoff(.40);
  await assert.rejects(backend.move('forward', .22), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'low-outside-zone'});
  await waitForForcedLanding(1);
}
const scenarios = {'1': activityOne, '2': activityTwo, '3': activityThree, '4': activityFour, '5': activityFive, '6': activitySix, '7': activitySeven};
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
