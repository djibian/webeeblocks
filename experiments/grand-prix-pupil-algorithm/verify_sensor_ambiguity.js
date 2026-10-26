'use strict';
// Tests the real immutable 218-block pupil project JSON, not a rewritten toy AST.
// No Webots, GUI, or human acceptance claims.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const bytes = fs.readFileSync(path.join(__dirname, 'Grand-Prix-sans-murs-algorithme-candidat.wbb'));
const hash = crypto.createHash('sha256').update(bytes).digest('hex');
// Candidate identity binds to the committed deterministic pupil generator;
// the native evidence additionally publishes the checked-out Git blob and SHA256.
const p = JSON.parse(bytes);
assert.deepStrictEqual(p, require('./build').build(), 'sensor test must use the exact real generated pupil project');
const names = p.workspace.variables.map(v => v.name), roots=p.workspace.blocks.blocks;
assert.equal(names.length, 11);
const counts = {}, seen = new Set();
function walk(b) {
  assert(b && !seen.has(b.id), 'duplicate block ID'); seen.add(b.id);
  counts[b.type]=(counts[b.type]||0)+1;
  for (const input of Object.values(b.inputs||{})) if(input.block) walk(input.block);
  if (b.next?.block) walk(b.next.block);
}
roots.forEach(walk);
assert.equal(seen.size,232); assert.equal(counts.controls_if,17);
assert.equal(counts.logic_compare,34);
assert.equal(counts.procedures_callnoreturn,4);
assert.equal(counts.procedures_defnoreturn,4);
const proc=roots.find(b=>b.type==='procedures_defnoreturn' && b.fields.NAME==='observer et décider');
assert(proc);
const down=proc.inputs.STACK.block, low=down.next.block,
  delta=low.next.block, gate=delta.next.block;
assert.equal(down.type,'webeeblocks_v2_vertical');
assert.equal(low.type,'variables_set'); assert.equal(delta.type,'variables_set');
assert.equal(delta.fields.VAR.id,'gp-pupil-v2-10');
assert.equal(delta.inputs.VALUE.block.type,'math_arithmetic');
assert.equal(delta.inputs.VALUE.block.fields.OP,'MINUS');
assert.equal(gate.type,'controls_if');
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
function decide(side,avant,bas,passed=0){
  const s={'côté':side,avant,bas,'H passé':passed};
  s['écart']=evalBlock(delta.inputs.VALUE.block,s);
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
console.log('PASS real WBB 232 classroom SHA256 '+hash);
assert.equal(decide(3,.35,.70,1),'anomaly', 'a repeated open echo on final side must not count a new H');
console.log('PASS 232 classroom blocks / 11 variables / 17 IF / 34 comparisons');
console.log('PASS '+cases.length+' sensor cases, '+ambiguous+' anomalies among 27 side-3 observations');

// Numeric boundary regression: compare conditions taken from TWO committed,
// real pupil-editable WBB graphs, not an equivalent-looking hand-written rule.
// This test establishes a scope difference, not which classroom policy is best.
const refProject=JSON.parse(fs.readFileSync(path.join(__dirname,'GP232_reference_main17671.wbb')));
const referenceNames=refProject.workspace.variables.map(v=>v.name);
const refRoots=refProject.workspace.blocks.blocks;
const refObserver=refRoots.find(b=>b.type==='procedures_defnoreturn' &&
                                  b.fields.NAME==='observer et décider');
assert(refObserver,'missing original reference observer');
let refGate=refObserver.inputs.STACK.block;
while(refGate && refGate.type!=='controls_if')refGate=refGate.next?.block;
assert(refGate && refGate.inputs.ELSE?.block?.type==='controls_if',
       'cannot inspect original pupil open/closed conditions');
assert.equal(referenceNames.length,10,'comparison must use the original 10-variable WBB');
// Evaluation is restricted to sensor arithmetic/boolean expressions present
// in the Blockly decision branch; no fabricated flight/mission outcome.
function evalReference(b,s) {
  if(b.type==='math_number')return Number(b.fields.NUM);
  if(b.type==='variables_get')
    return s[referenceNames[Number(b.fields.VAR.id.replace('gp-pupil-v2-',''))]];
  const left=evalReference(b.inputs.A.block,s), right=evalReference(b.inputs.B.block,s);
  if(b.type==='math_arithmetic'){
    if(b.fields.OP==='ADD')return left+right;
    if(b.fields.OP==='MINUS')return left-right;
  }
  if(b.type==='logic_operation'){
    if(b.fields.OP==='AND')return Boolean(left&&right);
    if(b.fields.OP==='OR')return Boolean(left||right);
  }
  if(b.type==='logic_compare'){
    const op=b.fields.OP;
    if(op==='GT')return left>right;
    if(op==='GTE')return left>=right;
    if(op==='LT')return left<right;
    if(op==='LTE')return left<=right;
    if(op==='EQ')return left===right;
    if(op==='NEQ')return left!==right;
  }
  throw Error('unsupported reference WBB expression '+b.type+' '+b.fields.OP);
}
function refDecide(side,avant,bas,passed=0) {
  const s={'côté':side,avant,bas,'H passé':passed};
  return evalReference(refGate.inputs.IF0.block,s)?'open':
         evalReference(refGate.inputs.ELSE.block.inputs.IF0.block,s)?'closed':'anomaly';
}
const exactBoundaryCases=[
  // IEEE-754: 0.55 - 0.25 is slightly greater than literal 0.30.
  [3,.25,.55,'anomaly','open'],
  // A +/-0.08 absolute band and a subtraction-first band disagree at equality.
  [3,.35,.43,'closed','anomaly'],
  [3,.27,.19,'closed','anomaly'],
  // Controls: non-boundary ambiguity, open, and plausibly closed stay stable.
  [3,.35,.50,'anomaly','anomaly'],
  [1,.35,.70,'open','open'],
  [3,.35,.35,'closed','closed']
];
for(const [side,avant,bas,oldExpected,newExpected] of exactBoundaryCases) {
  assert.equal(refDecide(side,avant,bas),oldExpected,
    'reference WBB threshold changed: '+JSON.stringify({side,avant,bas}));
  assert.equal(decide(side,avant,bas),newExpected,
    'contrast WBB threshold changed: '+JSON.stringify({side,avant,bas}));
}
console.log('PASS real reference/contrast WBB boundary regression '+exactBoundaryCases.length+' cases; 3 semantic differences');
console.log('UNPROVEN: physical sensor quantization, ideal threshold policy and classroom benefit');


// CENTIMETRE_BOUNDARY_MATRIX_V1. Synthetic values, not asserted Webots resolution.
// Evaluate branches extracted from two exact, pupil-editable .wbb files.
let grid=0, openDifference=0, closedDifference=0;
for(const side of [1,3]) for(let hc=20;hc<=50;hc++) for(let lc=15;lc<=95;lc++){
  const high=hc/100, low=lc/100, old=refDecide(side,high,low,0),
        modern=decide(side,high,low,0);
  grid++;
  assert.notEqual(decide(side,high,low,1),'open',
    'an already confirmed H must not enter another open-passage branch');
  if(old===modern)continue;
  assert([30,8,-8].includes(lc-hc),
    'unexplained non-boundary decision difference '+JSON.stringify({side,hc,lc,old,modern}));
  if(old==='anomaly'&&modern==='open') openDifference++;
  else if(old==='closed'&&modern==='anomaly') closedDifference++;
  else assert.fail('unanticipated direction of classification change '+JSON.stringify({side,hc,lc,old,modern}));
}
assert.equal(grid,5022);
assert.equal(openDifference,20);
assert.equal(closedDifference,34);
const ulpNeighbor=(n,offset)=>{
  assert(n>0&&Number.isFinite(n)&&[-1,0,1].includes(offset));
  if(!offset)return n;
  const bytes=Buffer.alloc(8);
  bytes.writeDoubleBE(n);
  bytes.writeBigUInt64BE(bytes.readBigUInt64BE()+BigInt(offset));
  return bytes.readDoubleBE();
};
let ulp=0, ulpDisagreement=0;
for(const [h,l] of [[0.25,0.55],[0.35,0.43],[0.27,0.19]])
  for(const ah of [-1,0,1]) for(const al of [-1,0,1]){
    const high=ulpNeighbor(h,ah),low=ulpNeighbor(l,al);
    const before=refDecide(3,high,low),after=decide(3,high,low);
    ulp++;
    assert.notEqual(decide(3,high,low,1),'open');
    if(before!==after){
      ulpDisagreement++;
      const delta=low-high;
      assert(Math.abs(delta-0.30)<5e-15||Math.abs(Math.abs(delta)-0.08)<5e-15,
        'floating-point disagreement unexpectedly far from threshold');
    }
  }
assert.equal(ulp,27);
assert(ulpDisagreement>0);
console.log('PASS two authentic WBB graphs: 5022 centimetry synthetic cases; 20 anomaly-to-open + 34 closed-to-anomaly differences, threshold-only; 27 ULP probes');
console.log('UNPROVEN: physical sensor quantization, full interpreter input replay or pupil usability');

console.log('UNPROVEN: exact native campaign, real OS picker and independent pupil usability');
