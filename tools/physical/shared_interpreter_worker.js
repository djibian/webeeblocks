#!/usr/bin/env node
'use strict';

const readline = require('readline');
const path = require('path');

const interpreterPath = path.resolve(
  __dirname,
  '../../plugins/robot_windows/blockly/webeeblocks/interpreter.js'
);
const interpreter = require(interpreterPath);

const rl = readline.createInterface({input: process.stdin, crlfDelay: Infinity});
const pending = new Map();
let nextId = 1;
let started = false;
let currentContext = null;

function emit(message) {
  process.stdout.write(JSON.stringify(message) + '\n');
}

function fail(message) {
  throw new Error('trusted shared interpreter worker: ' + message);
}

function exactContext(expectedRole) {
  const context = currentContext;
  if (!context || context.role !== expectedRole || !Array.isArray(context.path) || !context.node) {
    fail('backend request has no exact interpreter context');
  }
  return context;
}

function request(event, payload, expectedRole) {
  const context = exactContext(expectedRole);
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, {resolve, reject});
    emit(Object.assign({
      event,
      id,
      path: context.path,
      node: context.node,
    }, payload || {}));
  });
}

const backend = {
  takeoff: height_m => request('action', {kind: 'takeoff', height_m}, 'statement'),
  land: () => request('action', {kind: 'land'}, 'statement'),
  move: (direction, distance_m) => request('action', {kind: 'move', direction, distance_m}, 'statement'),
  vertical: (direction, distance_m) => request('action', {kind: 'vertical', direction, distance_m}, 'statement'),
  turn: angle_deg => request('action', {kind: 'turn', angle_deg}, 'statement'),
  wait: seconds => request('action', {kind: 'wait', seconds}, 'statement'),
  setSpeed: speed_m_s => request('action', {kind: 'set_speed', speed_m_s}, 'statement'),
  setLight: color => request('action', {kind: 'set_light', color}, 'statement'),
  readRange: direction => request('range', {direction}, 'expression'),
};

function settleResponse(message) {
  if (!Number.isInteger(message.id) || !pending.has(message.id)) {
    fail('response id does not match a pending backend request');
  }
  const entry = pending.get(message.id);
  pending.delete(message.id);
  if (message.ok === true && Object.prototype.hasOwnProperty.call(message, 'value')) {
    entry.resolve(message.value);
    return;
  }
  if (message.ok === true) {
    entry.resolve(undefined);
    return;
  }
  if (message.ok === false && typeof message.error === 'string' && message.error) {
    entry.reject(new Error(message.error));
    return;
  }
  fail('backend response is malformed');
}

async function runStart(astBinding) {
  if (started) fail('start is one-shot');
  if (typeof astBinding !== 'string' || !astBinding.trim() || astBinding !== astBinding.trim()) {
    fail('exact canonical ast binding is required');
  }
  let ast;
  try {
    ast = JSON.parse(astBinding);
  } catch (error) {
    fail('ast binding is not valid JSON');
  }
  if (JSON.stringify(ast) !== astBinding) {
    fail('ast binding is not exact canonical JSON');
  }
  started = true;
  try {
    const result = await interpreter.run(ast, backend, {
      maxSteps: 1000,
      hooks: {
        beforeStep: context => { currentContext = context; },
      },
    });
    currentContext = null;
    emit({event: 'done', remainingBudget: result.remainingBudget, variables: result.variables});
  } catch (error) {
    currentContext = null;
    emit({event: 'error', error: String(error && error.message ? error.message : error)});
  }
}

rl.on('line', line => {
  try {
    const message = JSON.parse(line);
    if (!message || typeof message !== 'object' || Array.isArray(message)) {
      fail('protocol message must be an object');
    }
    if (message.type === 'start') {
      void runStart(message.astBinding);
      return;
    }
    if (message.type === 'response') {
      settleResponse(message);
      return;
    }
    fail('unsupported protocol message');
  } catch (error) {
    emit({event: 'error', error: String(error && error.message ? error.message : error)});
    process.exitCode = 1;
    rl.close();
  }
});

rl.on('close', () => {
  for (const entry of pending.values()) {
    entry.reject(new Error('trusted interpreter worker input closed'));
  }
  pending.clear();
});
