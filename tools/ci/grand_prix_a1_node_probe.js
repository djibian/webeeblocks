// Native A1 mission and counterexamples through the ordinary WWI backend.
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

socket.onmessage = event => {
  for (const line of String(event.data).split(/\r?\n/)) {
    if (line.startsWith('robot:')) {
      const reply = JSON.parse(line.slice(6));
      if (reply.name === robot)
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

async function outcome(expected) {
  const deadline = Date.now() + 15000;
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

socket.onopen = async () => {
  try {
    send('init robot window');
    await backend.waitUntilReady();

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

    await backend.resetSimulation();
    await approachLastLeg();
    await assert.rejects(backend.move('forward', 1.6), {code: 'TIME_LIMIT'});
    await outcome({status: 'not-achieved', reason: 'envelope-contact'});

    await backend.resetSimulation();
    await takeoff(.9);
    await backend.stopSimulation();
    await assert.rejects(backend.move('forward', .2), {code: 'USER_STOPPED'});

    await backend.resetSimulation();
    await takeoff(.9);
    await outcome({status: 'not-achieved', reason: 'time-limit'});
    await assert.rejects(backend.move('forward', .2), {code: 'TIME_LIMIT'});
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  } finally {
    socket.close();
  }
};
