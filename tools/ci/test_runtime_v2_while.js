'use strict';
const assert = require('assert');
const Blockly = require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require('../../plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js');
delete global.Blockly;
const Compiler = require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const Contract = require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const Observer = require('../../plugins/robot_windows/blockly/webeeblocks/execution_observer');
const Physical = require('../../plugins/robot_windows/blockly/webeeblocks/physical_capability_contract');

const number = value => ({kind:'number',value});
const range = {kind:'range',direction:'front',unit:'m'};
const compare = {kind:'compare',op:'LT',left:range,right:number(0.5)};
const program = loop => ({version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:0.5},loop,{kind:'land'}]});
const loop = (mode='WHILE', condition=compare, body=[{kind:'move',direction:'forward',distance_m:0.1}], max_iterations=3) => ({kind:'while',mode,condition,body,max_iterations});
function backend(values) {
  const effects=[];
  return {effects,capabilities:{conditionalLoops:true},takeoff:async()=>effects.push('takeoff'),land:async()=>effects.push('land'),move:async()=>effects.push('move'),readRange:async()=>values.shift()};
}

async function prove() {
  // Pupil-facing UNTIL has no editable limit, but its AST remains guarded.
  const studentWs=new Blockly.Workspace();
  const studentUntil=studentWs.newBlock('webeeblocks_v2_until');
  const studentCompare=studentWs.newBlock('logic_compare');
  const studentA=studentWs.newBlock('math_number'), studentB=studentWs.newBlock('math_number');
  studentA.setFieldValue('1','NUM');studentB.setFieldValue('2','NUM');
  studentCompare.setFieldValue('LT','OP');
  studentCompare.getInput('A').connection.connect(studentA.outputConnection);
  studentCompare.getInput('B').connection.connect(studentB.outputConnection);
  studentUntil.getInput('BOOL').connection.connect(studentCompare.outputConnection);
  assert.strictEqual(studentUntil.getField('MAX_ITERATIONS'),null);
  const expected=loop('UNTIL',{kind:'compare',op:'LT',left:number(1),right:number(2)},[],25);
  assert.deepStrictEqual(Compiler.compileStatement(studentUntil),expected);
  assert(Interpreter.validateExecutionBudget(program(expected),5000)>0);
  const savedStudent=Blockly.serialization.workspaces.save(studentWs);
  const loadedStudent=new Blockly.Workspace();
  Blockly.serialization.workspaces.load(savedStudent,loadedStudent);
  assert.deepStrictEqual(Compiler.compileStatement(loadedStudent.getTopBlocks(true)[0]),expected);
  loadedStudent.dispose();studentWs.dispose();
  Compiler.installConditionalLoopBounds(Blockly);
  Compiler.installConditionalLoopBounds(Blockly); // repeated loads must not duplicate the field
  const ws = new Blockly.Workspace();
  const block=ws.newBlock('controls_whileUntil'), condition=ws.newBlock('logic_compare');
  const a=ws.newBlock('math_number'), b=ws.newBlock('math_number');
  a.setFieldValue('1','NUM'); b.setFieldValue('2','NUM');
  condition.setFieldValue('LT','OP');
  condition.getInput('A').connection.connect(a.outputConnection);
  condition.getInput('B').connection.connect(b.outputConnection);
  block.getInput('BOOL').connection.connect(condition.outputConnection);
  const compiled=Compiler.compileStatement(block);
  assert.deepStrictEqual(compiled,loop('WHILE',{kind:'compare',op:'LT',left:number(1),right:number(2)},[],100));
  block.setFieldValue('UNTIL','MODE'); assert.strictEqual(Compiler.compileStatement(block).mode,'UNTIL');
  assert.strictEqual(block.getFieldValue('MAX_ITERATIONS'),100);
  block.setFieldValue('20','MAX_ITERATIONS');
  assert.strictEqual(Compiler.compileStatement(block).max_iterations,20);
  const saved=Blockly.serialization.workspaces.save(ws);
  const copy=new Blockly.Workspace();
  Blockly.serialization.workspaces.load(saved,copy);
  assert.strictEqual(Compiler.compileStatement(copy.getTopBlocks(true)[0]).max_iterations,20);
  copy.dispose();
  delete saved.blocks.blocks[0].fields.MAX_ITERATIONS;
  const legacy=new Blockly.Workspace();
  Blockly.serialization.workspaces.load(saved,legacy);
  assert.strictEqual(Compiler.compileStatement(legacy.getTopBlocks(true)[0]).max_iterations,100);
  legacy.dispose();
  const getter=block.getFieldValue.bind(block);
  block.getFieldValue=name=>name==='MAX_ITERATIONS'?1.5:getter(name);
  assert.throws(()=>Compiler.compileStatement(block),/invalid conditional loop limit/);
  block.getFieldValue=getter;
  const mapped=Observer.buildSourceMap({getTopBlocks:()=>[block]});
  assert.strictEqual(mapped['program/0/condition/left'],a.id);
  assert.strictEqual(mapped['program/0/condition'],condition.id);
  ws.dispose();

  const normal=backend([0.2,0.3,0.8]);
  const paths=[];
  await Interpreter.run(program(loop()),normal,{hooks:{onSensor:async c=>paths.push(c.path)}});
  assert.deepStrictEqual(normal.effects,['takeoff','move','move','land']);
  assert.deepStrictEqual(paths,Array(3).fill(['program',1,'condition','left']));
  const until=backend([0.8,0.2]);
  await Interpreter.run(program(loop('UNTIL')),until);
  assert.deepStrictEqual(until.effects,['takeoff','move','land']);
  const zero=backend([0.8]); await Interpreter.run(program(loop()),zero);
  assert.deepStrictEqual(zero.effects,['takeoff','land']);

  const unending=backend([0.2,0.2,0.2,0.2]);
  await assert.rejects(()=>Interpreter.run(program(loop()),unending),/iteration limit exceeded/);
  assert.deepStrictEqual(unending.effects,['takeoff','move','move','move'],'guard exhaustion must not land normally or become success');
  const empty=backend([]);
  await assert.rejects(()=>Interpreter.run(program(loop('WHILE',number(1),[],100)),empty,{maxSteps:4}),/exceeds runtime budget before takeoff/);
  assert.deepStrictEqual(empty.effects,[]);
  const invalid=backend([NaN]);
  await assert.rejects(()=>Interpreter.run(program(loop()),invalid),/must be finite/);
  assert.deepStrictEqual(invalid.effects,['takeoff']);

  const variable={id:'after-loop',name:'compteur'};
  const assignedOnlyInside=program(loop('WHILE',number(0),[{kind:'set_variable',variable,value:number(1)}]));
  assignedOnlyInside.program.splice(2,0,{kind:'set_variable',variable:{id:'read',name:'lecture'},value:{kind:'variable_get',variable}});
  assert.throws(()=>Interpreter.validateProgram(assignedOnlyInside),/before assignment/);
  assert.throws(()=>Interpreter.validateProgram(program(loop('WHILE',number(0),[{kind:'land'}]))),/top-level/);
  for(const limit of [0,101,Infinity,1.5]) assert.throws(()=>Interpreter.validateProgram(program(loop('WHILE',compare,[],limit))),/iteration limit/);
  const inaccessible=backend([]); delete inaccessible.capabilities.conditionalLoops;
  await assert.rejects(()=>Interpreter.run(program(loop('WHILE',number(0),[])),inaccessible),/unavailable on this backend/);
  assert.deepStrictEqual(inaccessible.effects,[],'missing capability must refuse before takeoff');
  assert.throws(()=>Physical.deriveFacts(program(loop())),/unsupported AST statement kind: while/,'physical preflight must retain its refusal');

  const facts=Contract.collectAst(program(loop()));
  assert(facts.ranges.has('front')); assert(facts.moveDirections.has('forward')); assert(facts.statements.has('while'));
  assert.throws(()=>Interpreter.validateExecutionBudget(program(loop()),10),/exceeds runtime budget before takeoff/);
  assert(Interpreter.validateExecutionBudget(program(loop()),100)>10);
  console.log('PASS conditional loops: student UNTIL, Blockly WHILE/UNTIL, fresh conditions, zero-iteration assignment, source mapping, bounds, empty-loop budget, invalid samples, no false completion and physical refusal');
}
module.exports=prove;
if(require.main===module)prove().catch(e=>{console.error(e);process.exitCode=1;});
