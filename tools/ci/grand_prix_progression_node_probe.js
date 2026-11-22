// Native Grand Prix lesson missions and counterexamples through the ordinary WWI backend.
'use strict';
const assert = require('node:assert/strict');
const {setTimeout: delay} = require('node:timers/promises');
const Backend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const fs = require('node:fs');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const robot = 'Crazyflie WebeeBlocks';
const rebound = process.env.WEBEEBLOCKS_A7_V5_CASE;
const events = process.env.WEBEEBLOCKS_A7_V5_EVENTS;
const socket = new WebSocket('ws://127.0.0.1:' + Number(process.argv[2]) + '/');
const send = payload => {
  socket.send('robot:' + robot + ':' + payload);
  if (rebound) console.log('A7_V5_WWI > ' + payload);
};
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
      if (rebound) console.log('A7_V5_WWI < ' + reply.message);
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
  // At the first native low-altitude landing sample, the .62-m final MOVE
  // left x=1.741255 versus the fixed x=1.800-m tile centre (#1076).
  // Compensate that measured ~.059-m undertravel; keep the 5-cm footprint oracle.
  await backend.move('forward', .68);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await takeoff(.4);
  await assert.rejects(backend.move('forward', .6), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'low-outside-zone'});
  await waitForForcedLanding(1);

  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.88);
  await backend.stopSimulation();
  await assert.rejects(backend.move('forward', .2), {code: 'USER_STOPPED'});
  await waitForForcedLanding(2);

  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.88);
  await assert.rejects(backend.move('forward', 1.1), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'envelope-contact'});
  await waitForForcedLanding(3);
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

  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.88);
  await backend.stopSimulation();
  await assert.rejects(backend.move('forward', .2), {code: 'USER_STOPPED'});
  await waitForForcedLanding(2);
}

async function activityFour() {
  const variant = Number(process.argv[4]);
  assert([1, 2, 3].includes(variant), 'A4 variant missing');

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
  }

  async function completeLanding() {
    await backend.land();
    await backend.completeActivityMission(evaluation);
    await outcome({status: 'achieved'});
  }

  async function rejectWrongPad() {
    // The whole-footprint oracle can interrupt the explicit LAND before ACK.
    // Its exact published refusal and the independent LAND are both required.
    try {
      await backend.land();
    } catch (error) {
      assert.equal(error.code, 'TIME_LIMIT');
    }
    await outcome({status: 'not-achieved', reason: 'low-outside-zone'});
    await waitForForcedLanding(1);
  }

  async function freshAttempt() {
    await backend.resetSimulation();
    await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  }

  await approachLanding('left');
  await completeLanding();

  await freshAttempt();
  await approachLanding('right');
  await rejectWrongPad();

  // STOP must revoke subsequent actuation and the native pilot must LAND
  // independently, even when the previous attempt has already failed.
  await freshAttempt();
  await takeoff(.9);
  await backend.stopSimulation();
  await assert.rejects(backend.move('forward', .2), {code: 'USER_STOPPED'});
  await waitForForcedLanding(2);

  // Reuse V1's successful distance blindly. The policy receives no variant.
  await freshAttempt();
  console.log(JSON.stringify({event: 'A4_FIXED', distance: .30, side: 'left'}));
  await takeoff(.9);
  await backend.move('forward', .30);
  const moveLeft = backend.move('left', .50);
  if (variant === 1) {
    await moveLeft;
    await completeLanding();
  } else {
    // At .30 m, V2/V3 are still in the narrow leg, before the widened arrival.
    await assert.rejects(moveLeft, {code: 'TIME_LIMIT'});
    await outcome({status: 'not-achieved', reason: 'course-boundary'});
    await waitForForcedLanding(3);
  }

  const file = process.argv[5];
  if (file) {
    await freshAttempt();
    const {reopen} = require('./grand_prix_a4_pupil');
    const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
    const {ast, sha256, maxSteps} = await reopen(file);
    console.log(JSON.stringify({event: 'A4_WBB_REOPENED', sha256}));
    await Interpreter.run(ast, backend, {maxSteps, hooks: {onSensor: sample => {
      console.log(JSON.stringify({event: 'A4_WBB_SENSOR', direction: sample.direction, value: sample.value}));
    }}});
    await backend.completeActivityMission(evaluation);
    await outcome({status: 'achieved'});
  }
}

async function activityFive() {
  async function ranges() {
    const readings = {};
    for (const direction of ['front', 'back', 'left', 'right'])
      readings[direction] = await backend.readRange(direction);
    return readings;
  }

  async function reachChoice(lastMove = .51) {
    await takeoff(.9);
    const front = await backend.readRange('front');
    // These intervals are based on rays from the fixed start. Course
    // identity and turn direction are never supplied to the witness.
    await backend.move('forward', front < 1.38 ? 1 : front < 1.78 ? 1.4 : 1.8);
    const right = await backend.readRange('right');
    const left = await backend.readRange('left');
    assert((right < .45) !== (left < .45), 'Exactly one side must see the corner');
    const turnedLeft = right < .45;
    console.log(JSON.stringify({front, left, right, turnedLeft}));
    await backend.turn(turnedLeft ? 90 : -90);
    await backend.move('forward', 1.85);
    await backend.move('forward', lastMove);
    if (lastMove === .51) {
      const choice = await ranges();
      console.log(JSON.stringify({choice}));
      assert(choice.front > .11 && choice.front < .26, 'Expected the H at the choice');
      for (const direction of ['back', 'left', 'right'])
        assert(choice[direction] >= 1.99, direction + ' still sees the earlier corner');
    }
    return turnedLeft;
  }

  const turnedLeft = await reachChoice();
  await backend.move(turnedLeft ? 'right' : 'left', .50);
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  const turnedLeftAgain = await reachChoice();
  const wrongSide = turnedLeftAgain ? 'left' : 'right';
  await backend.move(wrongSide, .50);
  console.log(JSON.stringify({event: 'A5_WRONG_PAD', side: wrongSide}));
  // The other visible pad is not a safe descent exception.  A native
  // failure may interrupt LAND before the backend returns normally.
  try {
    await backend.land();
  } catch (error) {
    assert.equal(error.code, 'TIME_LIMIT');
  }
  await outcome({status: 'not-achieved', reason: 'low-outside-zone'});
  await waitForForcedLanding(1);

  // Refute any attempt to continue commanding the vehicle after STOP.
  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.9);
  await backend.stopSimulation();
  await assert.rejects(backend.move('forward', .2), {code: 'USER_STOPPED'});
  await waitForForcedLanding(2);

  const file = process.argv[4];
  if (file) {
    await backend.resetSimulation();
    await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
    await require('./grand_prix_a5_wbb').run(file, backend);
    await backend.completeActivityMission(evaluation);
    await outcome({status: 'achieved'});

    await backend.resetSimulation();
    await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
    // The choice inspection does not use the turn result from the approach.
    await reachChoice(.41);
    let yaw = 0;
    for (const target of [0, 8, 12, -8, -12]) {
      if (target !== yaw)
        await backend.turn(target - yaw);
      yaw = target;
      const readings = await ranges();
      console.log(JSON.stringify({event: 'A5_LATE_SCAN', alongCommanded: 2.26,
        yawCommanded: yaw, readings}));
      assert(readings.back >= 1.999, 'Late rear scan recovers the turn cue');
    }
    await outcome({status: 'not-achieved', reason: 'time-limit'});
    await waitForForcedLanding(3);
    await assert.rejects(backend.move('forward', .2), {code: 'TIME_LIMIT'});
  }
}

async function activitySix() {
  const A6Wbb = require('../grand_prix/witness_workspace_a6.js');
  // World index belongs to the test harness only, never to the pupil .wbb.
  const variant=Number(process.argv[4]);
  assert(Number.isInteger(variant)&&variant>=1&&variant<=5);
  const witness=A6Wbb.build();
  assert.equal(A6Wbb.build().sha256,witness.sha256,'WBB bytes must be reproducible');
  if(process.env.WEBEEBLOCKS_A6_WBB_OUT)
    fs.writeFileSync(process.env.WEBEEBLOCKS_A6_WBB_OUT,witness.content);
  console.log(JSON.stringify({event:'A6_WBB',sha256:witness.sha256,
    bytes:Buffer.byteLength(witness.content)}));
  const observations=[];
  await Interpreter.run(witness.ast,backend,{maxSteps:20000,hooks:{onSensor:sample=>{
    observations.push({direction:sample.direction,value:sample.value});
    console.log(JSON.stringify({event:'A6_SENSOR',direction:sample.direction,value:sample.value}));
  }}});
  const front=observations.filter(x=>x.direction==='front');
  const left=observations.find(x=>x.direction==='left');
  const right=observations.find(x=>x.direction==='right');
  assert(front.length>=1&&front[0].value>.65&&front[0].value<1.75);
  assert(left&&right,'both lateral sensors required, even when H is closed');
  if(variant<=3){
    assert(left.value>.20&&left.value<.45&&right.value>.20&&right.value<.45,
      'open H must expose both physical uprights');
    assert.equal(front.length,2,'post-H front must detect the terminal H');
  }else{
    assert(left.value>1.9&&right.value>1.9,'closed H lateral contrast missing');
    assert.equal(front.length,1,'closed H must not be crossed');
  }
  await backend.completeActivityMission(evaluation);
  await outcome({status:'achieved'});

  await backend.resetSimulation();
  await takeoff(.90);
  // Same mandatory independent envelope-contact refusal and native LAND;
  // slower permitted approach isolates impact dynamics from LAND handling.
  await backend.setSpeed(.14);
  const negativeFirst = await backend.readRange('front');
  assert(negativeFirst > .65 && negativeFirst < 1.75,
    'negative obstacle lacks sensor margin');
  await backend.move('forward', negativeFirst - .40);
  const negativeNear = await backend.readRange('front');
  assert(negativeNear > .24 && negativeNear < .57, 'negative standoff lost');
  console.log(JSON.stringify({negativeFirst, negativeNear, speed:.14}));
  // The strict 0.60 m V5 falsifier remains the DEFAULT and mandatory.
  // A separately labeled 0.40 m diagnostic may test shallower penetration;
  // it cannot replace or override the strict safety gate.
  const contactDiagnostic = process.env.WEBEEBLOCKS_A6_SHALLOW_CONTACT_DIAGNOSTIC;
  assert(contactDiagnostic === undefined || contactDiagnostic === '1',
    'unrecognized A6 diagnostic override');
  const contactAdvance = contactDiagnostic === '1' ? .40 : .60;
  console.log(JSON.stringify({event:'A6_NEGATIVE_CONTACT',advance:contactAdvance,
    shallowDiagnostic:contactDiagnostic === '1'}));
  await assert.rejects(backend.move('forward', contactAdvance), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'envelope-contact'});
  await waitForForcedLanding(1);

  // Recovery must be complete BEFORE RESET; the new incarnation cannot
  // inherit the prior negative. STOP must still cause its own native LAND.
  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation),
    {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.9);
  await backend.stopSimulation();
  await assert.rejects(backend.move('forward', .2), {code: 'USER_STOPPED'});
  await waitForForcedLanding(2);
}

async function reboundLanding() {
  assert(['stop', 'liveness'].includes(rebound) && events && Number(process.argv[4]) === 5);
  const interrupted = assert.rejects(backend.land(), {
    code: rebound === 'stop' ? 'USER_STOPPED' : 'TIME_LIMIT'
  });
  // Attach the rejection handler while waiting for the 8-ms native witness.
  // Await the same promise below so an early or unrelated result still fails.
  interrupted.catch(() => {});
  if (rebound === 'stop') {
    const marker = events + '/stop-request';
    const deadline = Date.now() + 35000;
    while (!fs.existsSync(marker) && Date.now() < deadline)
      await delay(2);
    assert(fs.existsSync(marker), 'first native separation after motor latch absent');
    const observedMs = Number(fs.readFileSync(marker, 'utf8'));
    assert(Number.isSafeInteger(observedMs) && observedMs > 0);
    const id = backend.nextId;
    const stopped = backend.stopSimulation();
    fs.writeFileSync(events + '/stop-sent.tmp', JSON.stringify({
      id, observed_ms: observedMs, wall_monotonic_ns: process.hrtime.bigint().toString()
    }));
    fs.renameSync(events + '/stop-sent.tmp', events + '/stop-sent');
    await stopped;
  }
  await interrupted;
  assert.equal(forcedLandings, 0, 'independent LAND already ACKed before RESET probe');
  // Use the actual WWI request without canceling the independent LAND from JS.
  await assert.rejects(backend._request(['RESET']), error =>
    ['LANDING_UNCONFIRMED', 'TIME_LIMIT'].includes(error.code));
  await waitForForcedLanding(1);
  await backend.resetSimulation();
  await backend._waitForAdmission(backend.timeObservationEpoch);
  console.log('A7_V5_WWI_COMPLETE ' + rebound);
}

async function activitySeven() {
  const variant = Number(process.argv[4]);
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
  async function approachClosedH() {
    const corner = await approachEndOfLeg();
    assert((corner.left < .45) !== (corner.right < .45), 'outer corner requires one side');
    await advanceWhile('forward', .06, async () => await range() > .30, 10);
    await advanceWhile('back', .04, async () => await range() < .27, 8);
    await backend.turn(corner.right < .45 ? 90 : -90);
    const closed = await approachEndOfLeg();
    assert(closed.front < .19 && closed.left > .45 && closed.right > .45, 'closed H');
    return closed;
  }
  await takeoff(.90);
  await approachClosedH();
  await advanceWhile('back', .13, async () => await range() < .65, 8);
  await advanceWhile('forward', .05, async () => await range() > .71, 8);
  if (rebound) return reboundLanding();
  await backend.land();
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});

  await backend.resetSimulation();
  await takeoff(.40);
  await assert.rejects(backend.move('forward', .22), {code: 'TIME_LIMIT'});
  await outcome({status: 'not-achieved', reason: 'low-outside-zone'});
  await waitForForcedLanding(1);

  // A7 must independently fence commands after STOP, then acknowledge LAND.
  // A fresh RESET must invalidate the negative result of attempt 2.
  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.90);
  await backend.stopSimulation();
  await assert.rejects(backend.move('forward', .20), {code: 'USER_STOPPED'});
  await waitForForcedLanding(2);
  // Independent product attempt #4: real Blockly 13.2.1 -> saved .wbb ->
  // disk Open -> AST/preflight -> shared interpreter -> same native oracle.
  // The preceding WWI-command attempt/negatives never substitute for this.
  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  const A7Wbb = require('../grand_prix/witness_workspace_a7.js');
  const crypto = require('node:crypto');
  const witness = A7Wbb.build();
  assert.equal(witness.sha256, 'ba575b02048d9f3b1bd2a3e25cd84035839c8eee60b397faae36f78b105e4c75',
    'historical A7 .wbb bytes changed');
  assert.equal(A7Wbb.build().sha256, witness.sha256, 'A7 source file not reproducible');
  const file = process.env.WEBEEBLOCKS_A7_WBB_OUT;
  assert(file, 'A7 native product witness path required');
  fs.writeFileSync(file, witness.content);
  const savedText = fs.readFileSync(file, 'utf8');
  assert.equal(crypto.createHash('sha256').update(savedText).digest('hex'), witness.sha256);
  const result = await A7Wbb.runSaved(savedText, backend);
  assert.equal(result.sha256, witness.sha256, 'A7 Open/execute SHA mismatch');
  await backend.completeActivityMission(evaluation);
  await outcome({status: 'achieved'});
  console.log('A7_WBB_PRODUCT_PASS ' + JSON.stringify(result));

  if (![2, 3, 7].includes(variant)) return;
  await backend.resetSimulation();
  await assert.rejects(backend.readActivityOutcome(evaluation), {code: 'OUTCOME_UNAVAILABLE'});
  await takeoff(.90);
  if (variant === 7) {
    await outcome({status: 'not-achieved', reason: 'time-limit'});
  } else {
    const obstacle = variant === 2 ? await approachClosedH() : await reachObstacle();
    assert(obstacle.front > .085 && obstacle.front < .26, 'controlled contact approach');
    if (variant === 3) {
      assert(obstacle.left < .45 && obstacle.right < .45, 'open H counterexample');
    }
    console.log('A7_CONTACT_PRE ' + JSON.stringify(obstacle));
    await backend.setSpeed(.14);
    await assert.rejects(backend.move('forward', .60), {code: 'TIME_LIMIT'});
    await outcome({status: 'not-achieved', reason: 'envelope-contact'});
  }
  await waitForForcedLanding(3);
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
