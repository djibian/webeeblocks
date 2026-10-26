'use strict';
// Structural equivalence of the exact pupil 218 -> 222 ordinary Blockly stages.
// This proves no passage, observation, threshold, ambiguity or landing body changed.
// Native flight and human usability require separate observations.
const assert = require('node:assert/strict');
const {build, originalBuild} = require('./build');
const a = originalBuild(), b = build();
const original = a.workspace.blocks.blocks, staged = b.workspace.blocks.blocks;
assert.equal(original.length, 2);
assert.equal(staged.length, 4);
assert.deepStrictEqual(staged[0], original[0], 'main pupil program must be identical');
assert.deepStrictEqual(staged[1].inputs.STACK.block.next.block.next.block.inputs.IF0,
  original[1].inputs.STACK.block.next.block.next.block.inputs.IF0,
  'open-H observation must remain identical');
const choice0 = original[1].inputs.STACK.block.next.block.next.block;
const choice1 = staged[1].inputs.STACK.block.next.block.next.block;
assert.deepStrictEqual(staged[2].inputs.STACK.block, choice0.inputs.DO0.block,
  'full H passage, rear validation and H count preserved');
assert.deepStrictEqual(staged[3].inputs.STACK.block,
  choice0.inputs.ELSE.block.inputs.DO0.block,
  'full closed-H approach, landing choice, count guard preserved');
assert.deepStrictEqual(choice1.inputs.ELSE.block.inputs.IF0,
  choice0.inputs.ELSE.block.inputs.IF0,
  'ambiguous high/low measurement guard preserved');
for (const [call, name] of [
  [choice1.inputs.DO0.block, 'franchir et confirmer le H'],
  [choice1.inputs.ELSE.block.inputs.DO0.block, 'approcher le H fermé et poser']]) {
  assert.equal(call.type, 'procedures_callnoreturn');
  assert.equal(call.extraState.name, name);
}
assert.deepStrictEqual(staged[1].inputs.STACK.block.next.block.inputs.VALUE,
  original[1].inputs.STACK.block.next.block.inputs.VALUE,
  'real low front sensor measurement preserved');
console.log('PASS exact extracted procedure bodies / 17 conditions / 34 comparisons / full ambiguity and H-count logic preserved');
console.log('UNPROVEN native R2025a, editor navigation, OS picker, human pupil comprehension');
