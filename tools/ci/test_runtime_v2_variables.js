'use strict';
const assert = require('assert');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Blockly = require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const SemanticAst = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));
const Interpreter = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/interpreter.js'));
const ActivityContract = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const ExecutionObserver = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/execution_observer.js'));
const ProjectFiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/project_files.js'));

Blockly.defineBlocksWithJsonArray([
  {type:'webeeblocks_v2_takeoff', message0:'takeoff %1', args0:[{type:'field_number',name:'HEIGHT',value:0.8}], previousStatement:null,nextStatement:null},
  {type:'webeeblocks_v2_move', message0:'move %1 %2', args0:[{type:'field_dropdown',name:'DIRECTION',options:[['forward','forward'],['left','left']]},{type:'field_number',name:'DISTANCE',value:0.3}], previousStatement:null,nextStatement:null},
  {type:'webeeblocks_v2_range', message0:'range %1', args0:[{type:'field_dropdown',name:'DIRECTION',options:[['front','front'],['left','left'],['right','right']]}], output:'Number'},
  {type:'webeeblocks_v2_land', message0:'land', previousStatement:null}
]);

function connectStatement(a,b){a.nextConnection.connect(b.previousConnection);}
function buildWorkspace(){
  const workspace=new Blockly.Workspace();
  const variable=workspace.createVariable('distance mémorisée','', 'memo-distance');
  const takeoff=workspace.newBlock('webeeblocks_v2_takeoff');
  const set=workspace.newBlock('variables_set');
  const range=workspace.newBlock('webeeblocks_v2_range');
  const decision=workspace.newBlock('controls_if');
  const compare=workspace.newBlock('logic_compare');
  const get=workspace.newBlock('variables_get');
  const threshold=workspace.newBlock('math_number');
  const move=workspace.newBlock('webeeblocks_v2_move');
  const land=workspace.newBlock('webeeblocks_v2_land');
  takeoff.setFieldValue('0.8','HEIGHT');
  set.getField('VAR').setValue(variable.getId());
  range.setFieldValue('front','DIRECTION');
  set.getInput('VALUE').connection.connect(range.outputConnection);
  compare.setFieldValue('LT','OP');
  get.getField('VAR').setValue(variable.getId());
  threshold.setFieldValue('0.5','NUM');
  compare.getInput('A').connection.connect(get.outputConnection);
  compare.getInput('B').connection.connect(threshold.outputConnection);
  decision.getInput('IF0').connection.connect(compare.outputConnection);
  move.setFieldValue('left','DIRECTION');move.setFieldValue('0.3','DISTANCE');
  decision.getInput('DO0').connection.connect(move.previousConnection);
  connectStatement(takeoff,set);connectStatement(set,decision);connectStatement(decision,land);
  return workspace;
}
function profile(){return Profiles.resolveById(Activities.DOCUMENT,'progression-memory-v1',Activities.BLOCK_CATALOG);}
function compile(workspace){const p=profile();ActivityContract.preflightWorkspace(p,workspace);const ast=SemanticAst.compileWorkspace(workspace);ActivityContract.preflightAst(p,ast);return ast;}
function backend(log){return{capabilities:{actions:['takeoff','move','land'],rangeDirections:['front','left','right'],moveDirections:['forward','left'],verticalDirections:[]},async takeoff(v){log.push(['takeoff',v]);},async land(){log.push(['land']);},async move(d,v){log.push(['move',d,v]);},async readRange(d){log.push(['range',d]);return 0.4;}};}
async function execute(ast,hooks){const log=[];const result=await Interpreter.run(ast,backend(log),{hooks:hooks||{}});return{log,result};}
function memoryTransport(){const state={text:null,writes:0};const handle={name:'memoire.wbb'};return{state,nativeFileSystemAccess:true,async open(){return{handle,name:handle.name,text:state.text,mode:'test'};},async saveAs(name,text){state.text=text;state.writes++;return{handle,name,mode:'test'};},async save(target,name,text){assert.strictEqual(target,handle);state.text=text;state.writes++;return{handle,name,mode:'test'};}};}
async function roundTrip(workspace, expectedAst){const p={value:profile()},transport=memoryTransport();const manager=ProjectFiles.createManager({Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,blockCatalog:Activities.BLOCK_CATALOG,semanticAst:SemanticAst,activityContract:ActivityContract,workspace,getProfile:()=>p.value,setProfile:value=>{p.value=value;},transport});await manager.saveAs('memoire');const bytes=transport.state.text;assert(bytes.includes('distance mémorisée'),'serialized project lost variable name');workspace.clear();transport.state.text=bytes;await manager.open();assert.deepStrictEqual(compile(workspace),expectedAst,'project Save/Open changed variable AST identity or semantics');}

(async function(){
  const p4=Profiles.resolveById(Activities.DOCUMENT,'progression-combined-decisions-v1',Activities.BLOCK_CATALOG),p5=profile();
  assert.strictEqual(p4.world,p5.world);assert(p4.toolbox.every(type=>p5.toolbox.includes(type)),'memory profile must be cumulative');assert(p5.toolbox.includes('variables_set'));assert(p5.toolbox.includes('variables_get'));assert(p5.runtime.allowedStatementKinds.includes('set_variable'));
  const workspace=buildWorkspace(),ast=compile(workspace);
  const set=ast.program.find(node=>node.kind==='set_variable');assert(set);assert.deepStrictEqual(set.variable,{id:'memo-distance',name:'distance mémorisée'});assert.strictEqual(set.value.kind,'range');
  const normal=await execute(ast,{}),variableEvents=[];
  const observed=await execute(ast,{onNode:async()=>{},beforeStep:async()=>{},onSensor:async()=>{},onVariables:async detail=>{variableEvents.push(detail.values);}});
  assert.deepStrictEqual(observed.log,normal.log,'debug hooks changed normal execution semantics');assert.deepStrictEqual(normal.result.variables,{'distance mémorisée':0.4});assert.deepStrictEqual(variableEvents.at(-1),{'distance mémorisée':0.4});assert(normal.log.some(item=>item[0]==='move'&&item[1]==='left'),'stored value was not reused in decision');

  const observerVariableEvents=[],activeEvents=[];
  const observer=ExecutionObserver.create(workspace,{
    onActive:detail=>{activeEvents.push({blockId:detail.blockId,kind:detail.node&&detail.node.kind});},
    onVariables:detail=>{observerVariableEvents.push(detail.values);}
  });
  const observerHooks=observer.begin(true);
  observer.continueRun();
  const throughObserver=await execute(ast,observerHooks);
  observer.finish();
  const setBlock=workspace.getAllBlocks(false).find(block=>block.type==='variables_set');
  assert.deepStrictEqual(throughObserver.log,normal.log,'execution observer changed variable-program semantics');
  assert.deepStrictEqual(observerVariableEvents.at(-1),{'distance mémorisée':0.4},'execution observer did not surface current variable values');
  assert(activeEvents.some(detail=>detail.kind==='set_variable'&&detail.blockId===setBlock.id),'set-variable interpreter event did not map back to its real Blockly block');

  let backendActions=0;await assert.rejects(Interpreter.run({version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:0.8},{kind:'if',condition:{kind:'variable_get',variable:{id:'x',name:'x'}},then:[],else:[]},{kind:'land'}]},{async takeoff(){backendActions++;},async land(){backendActions++;}}),/read before assignment/);assert.strictEqual(backendActions,0,'uninitialized variable was not rejected before backend action');
  await assert.rejects(Interpreter.run(ast,backend([]),{maxSteps:1}),/execution budget exceeded/);
  await roundTrip(workspace,ast);
  console.log('PASS variables-memory: Blockly model -> stable AST -> fail-closed interpreter -> execution observer -> project round-trip');
})().catch(error=>{console.error(error);process.exit(1);});
