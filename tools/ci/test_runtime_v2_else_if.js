'use strict';
// Real Blockly 13.2.1 mutator, AST v1 lowering, interpreter, source mapping and WBB.
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.resolve(__dirname,'../..');
const Blockly=require(root+'/plugins/robot_windows/blockly_v2/node_modules/blockly');
require(root+'/plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require(root+'/plugins/robot_windows/blockly/webeeblocks/crazyflie_v2');
delete global.Blockly;
const base=root+'/plugins/robot_windows/blockly/webeeblocks/';
const Compiler=require(base+'semantic_ast'),Interpreter=require(base+'interpreter');
const Observer=require(base+'execution_observer'),Contract=require(base+'activity_contract');
const Profiles=require(base+'activity_profiles'),Activities=require(base+'activities');
const Files=require(base+'project_files'),Wwi=require(base+'wwi_backend');
const setup={WebeeBlocksActivities:Activities,Blockly:{inject(){}},
  WebeeBlocksWwiBackend:Wwi,WebeeBlocksRuntimeOutcome:{classify(){return {};}}};
setup.window=setup;
vm.runInNewContext(fs.readFileSync(root+'/plugins/robot_windows/grand_prix_u/setup.js','utf8'),setup);
const document=JSON.parse(JSON.stringify(setup.WebeeBlocksActivities.DOCUMENT));
const profile=Profiles.resolveById(document,'progression-grand-prix-u-v1',Activities.BLOCK_CATALOG);
const options={Blockly,profiles:Profiles,activitiesDocument:document,blockCatalog:Activities.BLOCK_CATALOG,
  semanticAst:Compiler,activityContract:Contract};
function num(w,value){const b=w.newBlock('math_number');b.setFieldValue(String(value),'NUM');return b;}
function put(parent,socket,child){parent.getInput(socket).connection.connect(child.outputConnection);return parent;}
function link(...blocks){for(let i=1;i<blocks.length;i++)blocks[i-1].nextConnection.connect(blocks[i].previousConnection);}
function read(w,variable){const b=w.newBlock('variables_get');b.getField('VAR').setValue(variable.getId());return b;}
function assign(w,variable,value){
  const b=w.newBlock('variables_set');b.getField('VAR').setValue(variable.getId());
  put(b,'VALUE',num(w,value));return b;
}
function compare(w,left,right){
  const b=w.newBlock('logic_compare');b.setFieldValue('LT','OP');
  put(b,'A',left);put(b,'B',right);return b;
}
function sensor(w,direction){
  const b=w.newBlock('webeeblocks_v2_range');b.setFieldValue(direction,'DIRECTION');return b;
}
function fixture(elseifs,hasElse,initial,procedure){
  const w=new Blockly.Workspace(),variable=w.getVariableMap().createVariable('mesure'),
    choice=w.getVariableMap().createVariable('choix');
  const init=assign(w,variable,initial),takeoff=w.newBlock('webeeblocks_v2_takeoff'),
    decision=w.newBlock('controls_if'),land=w.newBlock('webeeblocks_v2_land');
  put(takeoff,'HEIGHT',num(w,0.5));
  // Headless Blockly uses the same mutator extraState as serialized .wbb.
  decision.loadExtraState({elseIfCount:elseifs,hasElse});
  assert.strictEqual(decision.elseifCount_,elseifs);
  assert(decision.getInput('IF'+elseifs)&&decision.getInput('DO'+elseifs));
  assert.strictEqual(!!decision.getInput('ELSE'),hasElse);
  const arithmetic=w.newBlock('math_arithmetic');arithmetic.setFieldValue('ADD','OP');
  put(arithmetic,'A',read(w,variable));put(arithmetic,'B',num(w,0.2));
  const conditions=[
    compare(w,sensor(w,'front'),num(w,0.2)),
    compare(w,arithmetic,num(w,0.5)),
    compare(w,sensor(w,'left'),num(w,0.8))
  ];
  const actions=[];
  for(let i=0;i<=elseifs;i++){
    put(decision,'IF'+i,conditions[i]);
    const action=assign(w,choice,i+1);actions.push(action);
    decision.getInput('DO'+i).connection.connect(action.previousConnection);
  }
  // Unused candidate conditions must not become detached top-level blocks.
  for(let i=elseifs+1;i<conditions.length;i++)conditions[i].dispose(true);
  const fallback=hasElse?assign(w,choice,4):null;
  if(fallback)decision.getInput('ELSE').connection.connect(fallback.previousConnection);
  let call=null,definition=null;
  if(procedure){
    definition=w.newBlock('procedures_defnoreturn');
    definition.setFieldValue('choisir','NAME');
    definition.getInput('STACK').connection.connect(decision.previousConnection);
    call=w.newBlock('procedures_callnoreturn');call.loadExtraState({name:'choisir'});
    link(init,takeoff,call,land);
  }else link(init,takeoff,decision,land);
  return {w,variable,choice,init,takeoff,decision,land,actions,fallback,call,definition};
}
function backend(front,left){
  const effects=[],reads=[];
  return {effects,reads,
    capabilities:{procedures:true,conditionalLoops:true,actions:['takeoff','land'],
      rangeDirections:['front','left'],moveDirections:[],verticalDirections:[]},
    async takeoff(){effects.push('takeoff');},
    async land(){effects.push('land');},
    async readRange(direction){reads.push(direction);return direction==='front'?front:left;}};
}
async function check(elseifs,hasElse,initial,procedure,front,left,expected,expectedReads){
  const f=fixture(elseifs,hasElse,initial,procedure);
  try{
    Contract.preflightWorkspace(profile,f.w);
    const ast=Compiler.compileWorkspace(f.w);
    assert.strictEqual(ast.version,1);assert.strictEqual(ast.semantics,'webeeblocks-ast-v1');
    Contract.preflightAst(profile,ast);
    const conditional=procedure?ast.program[2].body[0]:ast.program[2];
    assert.strictEqual(conditional.kind,'if');
    let tail=conditional;
    for(let i=0;i<elseifs;i++){
      assert.strictEqual(tail.else.length,1);
      tail=tail.else[0];assert.strictEqual(tail.kind,'if');
    }
    assert.strictEqual(!!tail.else,hasElse);
    const prefix=procedure?'program/2/body/0':'program/2';
    const mapping=Observer.buildSourceMap(f.w);
    let branchPath=prefix;
    for(let i=0;i<=elseifs;i++){
      assert.strictEqual(mapping[branchPath],f.decision.id);
      assert.strictEqual(mapping[branchPath+'/then/0'],f.actions[i].id);
      assert.strictEqual(mapping[branchPath+'/condition'],
        f.decision.getInputTargetBlock('IF'+i).id);
      branchPath+='/else/0';
    }
    if(hasElse)assert.strictEqual(mapping[branchPath.slice(0,-2)+'/0'],undefined); // no phantom synthetic if
    const encoded=Files.encodeProject(profile,f.w,options);
    const loaded=Files.validateProjectText(encoded,profile,options);
    assert.deepStrictEqual(loaded.ast,ast);
    const copy=new Blockly.Workspace();
    try{
      Blockly.serialization.workspaces.load(loaded.project.workspace,copy);
      assert.deepStrictEqual(Compiler.compileWorkspace(copy),ast);
      assert.deepStrictEqual(Observer.buildSourceMap(copy),mapping);
    }finally{copy.dispose();}
    const values=[],highlights=[],paused=[];
    let observer;
    observer=Observer.create(f.w,{
      onActive:ctx=>{highlights.push(ctx);assert(ctx.blockId,'unmapped AST path '+ctx.path.join('/'));},
      onVariables:ctx=>{if(ctx.variable.name==='choix')values.push(ctx.values.choix);},
      onPause:ctx=>{paused.push(ctx);queueMicrotask(()=>observer.next());}
    });
    const hooks=observer.begin(true),b=backend(front,left);
    const result=await Interpreter.run(ast,b,{maxSteps:1000,hooks});
    observer.finish();
    assert.deepStrictEqual(b.effects,['takeoff','land']);
    assert.deepStrictEqual(b.reads,expectedReads);
    assert.deepStrictEqual(values,expected===undefined?[]:[expected],'exactly one arm must run');
    assert.strictEqual(result.variables.choix,expected);
    assert(highlights.length>0&&paused.length>0,'step-by-step observer must advance');
    assert(paused.every(c=>c.blockId),'pause must identify real Blockly block');
    assert(Interpreter.validateExecutionBudget(ast,1000)>0);
    // Existing profile restrictions and flight boundaries remain active.
    const old=Profiles.resolveById(Activities.DOCUMENT,'progression-sequence-v1',Activities.BLOCK_CATALOG);
    assert.throws(()=>Contract.preflightWorkspace(old,f.w),/forbidden by profile/);
    return {ast,mapping};
  }finally{f.w.dispose();}
}
async function prove(){
  await check(0,false,0,false,0.1,0.1,1,['front']);
  await check(0,true,0,false,0.3,0.1,4,['front']);
  await check(1,false,0,false,0.3,0.1,2,['front']);
  await check(2,true,0,true,0.1,0.1,1,['front']);
  await check(2,true,0,true,0.3,0.1,2,['front']);
  await check(2,true,1,true,0.3,0.2,3,['front','left']);
  await check(2,true,1,true,0.3,0.9,4,['front','left']);
  await check(2,false,1,true,0.3,0.9,undefined,['front','left']);
  // Missing IF1 must not silently become false; no synthetically missing arm.
  const missing=fixture(2,false,0,false);
  missing.decision.getInputTargetBlock('IF1').unplug(true);
  assert.throws(()=>Compiler.compileWorkspace(missing.w),/missing value input IF1/);
  missing.w.dispose();
  // Lowered else-if arms are nested AST: forbidden takeoff/LAND still fail closed.
  const invalid=fixture(2,true,0,true);
  const bad=invalid.w.newBlock('webeeblocks_v2_land');
  invalid.actions[1].nextConnection.connect(bad.previousConnection);
  assert.throws(()=>Compiler.compileWorkspace(invalid.w),/top-level boundaries/);
  invalid.w.dispose();
  // Existing AST v1 variable definite-assignment analysis must inspect every arm.
  const unassigned=fixture(2,false,0,false);
  const missingVariable=unassigned.w.getVariableMap().createVariable('inconnue');
  const readMissing=read(unassigned.w,missingVariable);
  unassigned.actions[1].getInput('VALUE').connection.disconnect();
  unassigned.actions[1].getInput('VALUE').connection.connect(readMissing.outputConnection);
  assert.throws(()=>Interpreter.validateProgram(Compiler.compileWorkspace(unassigned.w)),/read before assignment/);
  unassigned.w.dispose();
  console.log('PASS Blockly else-if: mutator 0/1/2, ordered exclusive AST v1, variables/sensors/arithmetic, nested procedures, steps, WBB, limits and legacy if');
}
module.exports=prove;
if(require.main===module)prove().catch(e=>{console.error(e);process.exitCode=1;});
