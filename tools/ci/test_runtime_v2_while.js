'use strict';
const assert = require('assert');
const Blockly = require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require('../../plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js');
delete global.Blockly;
const Compiler = require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome');
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
  assert.strictEqual(studentUntil.getStyleName(),'loop_blocks','UNTIL belongs to the existing loop style');
  const expected=loop('UNTIL',{kind:'compare',op:'LT',left:number(1),right:number(2)},[],25);
  assert.deepStrictEqual(Compiler.compileStatement(studentUntil),expected);
  assert(Interpreter.validateExecutionBudget(program(expected),5000)>0);
  const savedStudent=Blockly.serialization.workspaces.save(studentWs);
  const loadedStudent=new Blockly.Workspace();
  Blockly.serialization.workspaces.load(savedStudent,loadedStudent);
  assert.deepStrictEqual(Compiler.compileStatement(loadedStudent.getTopBlocks(true)[0]),expected);
  // A full pupil sequence must map both the new loop condition and its body.
  const takeoff=loadedStudent.newBlock('webeeblocks_v2_takeoff');
  const land=loadedStudent.newBlock('webeeblocks_v2_land');
  const loadedUntil=loadedStudent.getAllBlocks(false).find(b=>b.type==='webeeblocks_v2_until');
  const move=loadedStudent.newBlock('webeeblocks_v2_move');
  for(const [parent,socket,n] of [[takeoff,'HEIGHT',0.5],[move,'DISTANCE',0.1]]){
    const x=loadedStudent.newBlock('math_number');x.setFieldValue(String(n),'NUM');
    parent.getInput(socket).connection.connect(x.outputConnection);
  }
  takeoff.nextConnection.connect(loadedUntil.previousConnection);
  loadedUntil.nextConnection.connect(land.previousConnection);
  loadedUntil.getInput('DO').connection.connect(move.previousConnection);
  const sourceMap=Observer.buildSourceMap(loadedStudent);
  assert.strictEqual(sourceMap['program/1'],loadedUntil.id);
  assert.strictEqual(sourceMap['program/1/condition'],loadedUntil.getInputTargetBlock('BOOL').id);
  assert.strictEqual(sourceMap['program/1/condition/left'],loadedUntil.getInputTargetBlock('BOOL').getInputTargetBlock('A').id);
  assert.strictEqual(sourceMap['program/1/body/0'],move.id);
  const fullAst=Compiler.compileWorkspace(loadedStudent);
  const reopened=new Blockly.Workspace();
  Blockly.serialization.workspaces.load(Blockly.serialization.workspaces.save(loadedStudent),reopened);
  assert.deepStrictEqual(Compiler.compileWorkspace(reopened),fullAst);
  assert.deepStrictEqual(Observer.buildSourceMap(reopened),sourceMap);
  reopened.dispose();loadedStudent.dispose();studentWs.dispose();
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

  // Activity 7 actual Blockly field-bound roundtrip (not a pupil solution).
  // The generic block starts at 100, but A7 must display, save and reopen
  // at most 80 iterations, without accepting a forged out-of-profile .wbb.
  {
    const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities');
    const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
    const ProjectFiles = require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
    const left = Profiles.resolveById(Activities.DOCUMENT, 'progression-mini-grand-prix-v1', Activities.BLOCK_CATALOG);
    const right = JSON.parse(JSON.stringify(left));
    right.runtime.scene = 'mini-grand-prix-r-v1';
    assert(Profiles.validateProfile(right, Activities.BLOCK_CATALOG));
    const pupil = new Blockly.Workspace();
    const takeoff = pupil.newBlock('webeeblocks_v2_takeoff');
    const pupilLoop = pupil.newBlock('controls_whileUntil');
    const land = pupil.newBlock('webeeblocks_v2_land');
    const compare = pupil.newBlock('logic_compare');
    const sensed = pupil.newBlock('webeeblocks_v2_range');
    const threshold = pupil.newBlock('math_number');
    const motion = pupil.newBlock('webeeblocks_v2_move');
    const takeoffHeight = pupil.newBlock('math_number');
    const distance = pupil.newBlock('math_number');
    takeoffHeight.setFieldValue('0.5', 'NUM');
    distance.setFieldValue('0.15', 'NUM');
    threshold.setFieldValue('0.5', 'NUM');
    sensed.setFieldValue('front', 'DIRECTION');
    compare.setFieldValue('LT', 'OP');
    pupilLoop.setFieldValue('UNTIL', 'MODE');
    takeoff.getInput('HEIGHT').connection.connect(takeoffHeight.outputConnection);
    motion.getInput('DISTANCE').connection.connect(distance.outputConnection);
    compare.getInput('A').connection.connect(sensed.outputConnection);
    compare.getInput('B').connection.connect(threshold.outputConnection);
    pupilLoop.getInput('BOOL').connection.connect(compare.outputConnection);
    pupilLoop.getInput('DO').connection.connect(motion.previousConnection);
    takeoff.nextConnection.connect(pupilLoop.previousConnection);
    pupilLoop.nextConnection.connect(land.previousConnection);
    assert.strictEqual(Number(pupilLoop.getFieldValue('MAX_ITERATIONS')), 100,
      'generic Blockly loop default unexpectedly changed');
    Contract.applyFieldBounds(left, pupil);
    assert.strictEqual(Number(pupilLoop.getFieldValue('MAX_ITERATIONS')), 80,
      'A7 must clamp the visible generic default before execution or save');
    pupilLoop.setFieldValue('81', 'MAX_ITERATIONS');
    assert.strictEqual(Number(pupilLoop.getFieldValue('MAX_ITERATIONS')), 80,
      'A7 editable limit accepted an out-of-profile value');
    Contract.preflightWorkspace(left, pupil);
    const initialAst = Compiler.compileWorkspace(pupil);
    assert.strictEqual(initialAst.program[1].max_iterations, 80);
    assert(Contract.preflightAst(left, initialAst));
    const fileOptions = {Blockly, profiles: Profiles, activitiesDocument: Activities.DOCUMENT,
      blockCatalog: Activities.BLOCK_CATALOG, semanticAst: Compiler, activityContract: Contract};
    const pupilWbb = ProjectFiles.encodeProject(left, pupil, fileOptions);
    for (const profile of [left, right]) {
      const decoded = ProjectFiles.validateProjectText(pupilWbb, profile, fileOptions);
      const restored = new Blockly.Workspace();
      Blockly.serialization.workspaces.load(decoded.project.workspace, restored);
      Contract.applyFieldBounds(profile, restored);
      Contract.preflightWorkspace(profile, restored);
      assert.deepStrictEqual(Compiler.compileWorkspace(restored), initialAst,
        'A7 loop semantics changed across Save/Open or L/R scene change');
      const loadedLoop = restored.getAllBlocks(false).find(b => b.type === 'controls_whileUntil');
      assert.strictEqual(Number(loadedLoop.getFieldValue('MAX_ITERATIONS')), 80);
      restored.dispose();
    }
    const forged = JSON.parse(pupilWbb);
    function findLoopNode(value) {
      if (!value || typeof value !== 'object') return null;
      if (value.type === 'controls_whileUntil') return value;
      for (const item of Object.values(value)) {
        const candidate = findLoopNode(item);
        if (candidate) return candidate;
      }
      return null;
    }
    const serializedLoop = findLoopNode(forged.workspace);
    assert(serializedLoop && serializedLoop.fields, 'saved A7 loop missing');
    serializedLoop.fields.MAX_ITERATIONS = 100;
    assert.throws(() => ProjectFiles.validateProjectText(JSON.stringify(forged), left, fileOptions),
      /outside profile bounds|out of bounds|invalid workspace/,
      'opening a forged 100-iteration A7 .wbb must refuse, not silently certify it');
    pupil.dispose();
  }

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
  await assert.rejects(()=>Interpreter.run(program(loop()),unending),error=>
    /iteration limit exceeded/.test(error.message)&&error.code==='LOOP_ITERATION_LIMIT'&&
    Outcome.classify(error).state==='ARRÊTÉ'&&/limite de 3 itérations.*Réinitialisez/.test(Outcome.classify(error).detail)&&
    !Outcome.isRetryable(error)&&Outcome.requiresSafeStop(error));
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
