#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const {StringDecoder} = require('string_decoder');
const Interpreter = require(path.resolve(
  __dirname,
  '../../plugins/robot_windows/blockly/webeeblocks/interpreter.js'
));

const MAX_PROTOCOL_BYTES = 1024 * 1024;
const decoder = new StringDecoder('utf8');
let inputBuffer = '';

function readLineSync() {
  while (true) {
    const newline = inputBuffer.indexOf('\n');
    if (newline >= 0) {
      const line = inputBuffer.slice(0, newline);
      inputBuffer = inputBuffer.slice(newline + 1);
      return line;
    }
    const bytes = Buffer.alloc(4096);
    const count = fs.readSync(0, bytes, 0, bytes.length, null);
    if (count === 0) {
      inputBuffer += decoder.end();
      if (inputBuffer.length) {
        const line = inputBuffer;
        inputBuffer = '';
        return line;
      }
      throw new Error('shared interpreter input closed');
    }
    inputBuffer += decoder.write(bytes.subarray(0, count));
    if (Buffer.byteLength(inputBuffer, 'utf8') > MAX_PROTOCOL_BYTES)
      throw new Error('shared interpreter message too large');
  }
}

function send(message) {
  const encoded = JSON.stringify(message);
  if (Buffer.byteLength(encoded, 'utf8') > MAX_PROTOCOL_BYTES)
    throw new Error('shared interpreter message too large');
  process.stdout.write(encoded + '\n');
}

function exactKeys(value, expected) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const keys = Object.keys(value).sort();
  const wanted = expected.slice().sort();
  return keys.length === wanted.length && keys.every((key, index) => key === wanted[index]);
}

let nextCallId = 1;
async function rpc(method, args) {
  const id = nextCallId++;
  send({type: 'call', id, method, args});
  const response = JSON.parse(readLineSync());
  const expected = response && response.ok === true
    ? ['type', 'id', 'ok', 'value']
    : ['type', 'id', 'ok'];
  if (!exactKeys(response, expected))
    throw new Error('malformed shared interpreter backend response');
  if (response.type !== 'return' || response.id !== id || typeof response.ok !== 'boolean')
    throw new Error('mismatched shared interpreter backend response');
  if (!response.ok) throw new Error('physical backend call failed closed');
  return response.value;
}

(async function main() {
  try {
    if (process.argv.length !== 2)
      throw new Error('shared interpreter worker accepts no arguments');
    const startup = JSON.parse(readLineSync());
    if (
      !exactKeys(startup, ['op', 'astBinding']) ||
      (startup.op !== 'run-bound-program' && startup.op !== 'validate-bound-program')
    )
      throw new Error('malformed shared interpreter startup');
    if (typeof startup.astBinding !== 'string' || !startup.astBinding.trim() || startup.astBinding !== startup.astBinding.trim())
      throw new Error('exact AST binding is unavailable');
    const ast = JSON.parse(startup.astBinding);
    Interpreter.validateProgram(ast);

    if (startup.op === 'validate-bound-program') {
      send({type: 'validated', ok: true});
      return;
    }

    const backend = {
      takeoff: (height) => rpc('takeoff', [height]),
      land: () => rpc('land', []),
      move: (direction, distance) => rpc('move', [direction, distance]),
      vertical: (direction, distance) => rpc('vertical', [direction, distance]),
      turn: (angle) => rpc('turn', [angle]),
      wait: (seconds) => rpc('wait', [seconds]),
      setSpeed: (speed) => rpc('setSpeed', [speed]),
      setLight: (color) => rpc('setLight', [color]),
      readRange: (direction) => rpc('readRange', [direction])
    };
    const result = await Interpreter.run(ast, backend);
    send({type: 'done', ok: true, result});
  } catch (_error) {
    try {
      send({type: 'done', ok: false, error: 'shared interpreter failed closed'});
    } catch (_sendError) {
      // The parent will fail closed if the protocol is no longer writable.
    }
    process.exitCode = 1;
  }
})();
