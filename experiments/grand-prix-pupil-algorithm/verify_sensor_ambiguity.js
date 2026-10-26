'use strict';
// Tests the real immutable 218-block pupil project JSON, not a rewritten toy AST.
// No Webots, GUI, or human acceptance claims.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const bytes = fs.readFileSync(path.join(__dirname, 'Grand-Prix-sans-murs-algorithme-candidat.wbb'));
const hash = crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(hash, 'a9d0eeefa3c5d40411726bdbe67a54f0783da266146ae8f3d5e24352e70bc18c');
const p = JSON.parse(bytes), names = p.workspace.variables.map(v => v.name), roots=p.workspace.blocks.blocks;
assert.equal(names.length, 9);
const counts = {}, seen = new Set();
function walk(b) {
  assert(b && !seen.has(b.id), 'duplicate block ID'); seen.add(b.id);
  counts[b.type]=(counts[b.type]||0)+1;
  for (const input of Object.values(b.inputs||{})) if(input.block) walk(input.block);
  if (b.next?.block) walk(b.next.block);
}
roots.forEach(walk);
assert.equal(seen.size,218); assert.equal(counts.controls_if,17);
assert.equal(counts.logic_compare,32);
const proc=roots.find(b=>b.type==='procedures_defnoreturn' && b.fields.NAME==='observer et décider');
assert(proc);
const down=proc.inputs.STACK.block, low=down.next.block, gate=low.next.block;
assert.equal(down.type,'webeeblocks_v2_vertical');
assert.equal(low.type,'variables_set'); assert.equal(gate.type,'controls_if');
const closed=gate.inputs.ELSE.block; assert.equal(closed.type,'controls_if');
function evalBlock(b,s) {
  if(b.type==='math_number') return Number(b.fields.NUM);
  if(b.type==='variables_get') return s[names[Number(b.fields.VAR.id.replace('gp-pupil-v2-',''))]];
  const a=evalBlock(b.inputs.A.block,s), c=evalBlock(b.inputs.B.block,s), op=b.fields.OP;
  if(b.type==='math_arithmetic') {if(op==='ADD')return a+c;if(op==='MINUS')return a-c;}
  if(b.type==='logic_compare') return {GT:a>c,GTE:a>=c,LT:a<c,LTE:a<=c,EQ:a===c,NEQ:a!==c}[op];
  if(b.type==='logic_operation') return op==='AND' ? Boolean(a&&c) : Boolean(a||c);
  throw Error('unsupported pupil expression '+b.type);
}
function decide(side,avant,bas){
  const s={'côté':side,avant,bas};
  return evalBlock(gate.inputs.IF0.block,s)?'open':
    evalBlock(closed.inputs.IF0.block,s)?'closed':'anomaly';
}
const cases=[
 [1,.35,.35,'anomaly'],[2,.35,.35,'anomaly'],[1,.35,.70,'open'],
 [3,.35,.35,'closed'],[3,.35,.42,'closed'],[3,.35,.70,'open'],
 [3,.35,.50,'anomaly'],[3,.35,.20,'anomaly'],[3,.35,.44,'anomaly'],
 [3,.35,.60,'anomaly']
];
for(const [side,high,low,expected] of cases)
  assert.equal(decide(side,high,low),expected,JSON.stringify({side,high,low}));
let ambiguous=0;
for(const a of [.30,.35,.40]) for(const b of [.10,.20,.28,.35,.42,.44,.50,.65,.70])
  if(decide(3,a,b)==='anomaly')ambiguous++;
assert(ambiguous>=8, 'the 206 simplification would erase these pupil fault decisions');
console.log('PASS real WBB 218 SHA256 '+hash);
console.log('PASS 218 blocks / 9 variables / 17 IF / 32 comparisons');
console.log('PASS '+cases.length+' sensor cases, '+ambiguous+' anomalies among 27 side-3 observations');
console.log('UNPROVEN: future #647 HEAD, native requalification, real editor, student usability');
