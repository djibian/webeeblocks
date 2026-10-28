'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.resolve(__dirname,'../..');
const Blockly=require(root+'/plugins/robot_windows/blockly_v2/node_modules/blockly');
require(root+'/plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require(root+'/plugins/robot_windows/blockly/webeeblocks/crazyflie_v2');
delete global.Blockly;
const base=root+'/plugins/robot_windows/blockly/webeeblocks/';
const Compiler=require(base+'semantic_ast'),Interpreter=require(base+'interpreter');
const Contract=require(base+'activity_contract'),Observer=require(base+'execution_observer');
const Activities=require(base+'activities'),Profiles=require(base+'activity_profiles');
const Files=require(base+'project_files'),Physical=require(base+'physical_capability_contract');
const Wwi=require(base+'wwi_backend');
const setup={WebeeBlocksActivities:Activities,Blockly:{inject(){}},WebeeBlocksWwiBackend:Wwi,WebeeBlocksRuntimeOutcome:{classify(){return {};}}};setup.window=setup;
vm.runInNewContext(fs.readFileSync(root+'/plugins/robot_windows/grand_prix_u/setup.js','utf8'),setup);
const document=JSON.parse(JSON.stringify(setup.WebeeBlocksActivities.DOCUMENT));
const profile=Profiles.resolveById(document,'progression-grand-prix-u-v1',Activities.BLOCK_CATALOG);
const fileOptions={Blockly,profiles:Profiles,activitiesDocument:document,blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Compiler,activityContract:Contract};
function connect(...blocks){for(let i=1;i<blocks.length;i++)blocks[i-1].nextConnection.connect(blocks[i].previousConnection);}
function call(w,name){const b=w.newBlock('procedures_callnoreturn');b.loadExtraState({name});return b;}
function definition(w,name){const b=w.newBlock('procedures_defnoreturn');b.setFieldValue(name,'NAME');return b;}
function number(w,value){const b=w.newBlock('math_number');b.setFieldValue(String(value),'NUM');return b;}
function fixture(){
 const w=new Blockly.Workspace(),variable=w.getVariableMap().createVariable('pas');
 const t=w.newBlock('webeeblocks_v2_takeoff'),init=w.newBlock('variables_set');
 t.setFieldValue('0.8','HEIGHT');init.setFieldValue(variable.getId(),'VAR');
 init.getInput('VALUE').connection.connect(number(w,0).outputConnection);
 const repeat=w.newBlock('controls_repeat_ext');repeat.getInput('TIMES').connection.connect(number(w,3).outputConnection);
 const d=definition(w,'avancer_un_pas'),c=call(w,'avancer_un_pas'),l=w.newBlock('webeeblocks_v2_land');
 repeat.getInput('DO').connection.connect(c.previousConnection);connect(t,init,repeat,l);
 const move=w.newBlock('webeeblocks_v2_move');move.setFieldValue('0.1','DISTANCE');
 const change=w.newBlock('math_change');change.setFieldValue(variable.getId(),'VAR');change.getInput('DELTA').connection.connect(number(w,1).outputConnection);
 d.getInput('STACK').connection.connect(move.previousConnection);connect(move,change);
 t.moveBy(20,40);d.moveBy(520,40);
 return {w,d,c,t,init,repeat,l,move,change,variable};
}
function backend(ranges=[.3]){
 const trace=[];return {trace,capabilities:{procedures:true,conditionalLoops:true,actions:['takeoff','move','land'],rangeDirections:['front'],moveDirections:['forward'],verticalDirections:[]},
 async takeoff(){trace.push('takeoff');},async move(){trace.push('move');},async land(){trace.push('land');},async readRange(){trace.push('range');return ranges.shift();}};
}
function program(body){return {version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.8},...body,{kind:'land'}]};}
function astCall(body){return {kind:'call',name:'observer',body};}
async function prove(){
 const f=fixture(),ast=Compiler.compileWorkspace(f.w);
 assert.strictEqual(ast.program[2].body[0].kind,'call');
 assert.strictEqual(ast.program[2].body[0].body[0].kind,'move');
 assert.strictEqual(f.w.getAllBlocks(false).length,11);
 const containers=new Set(['controls_repeat_ext','controls_whileUntil','webeeblocks_v2_until','controls_if','procedures_defnoreturn']);
 const depths=f.w.getAllBlocks(false).map(block=>{let depth=0;for(let parent=block.getSurroundParent();parent;parent=parent.getSurroundParent())if(containers.has(parent.type))depth++;return depth;});
 assert.strictEqual(Math.max(...depths),1,'measured Blockly statement nesting');
 assert.strictEqual(f.t.getDescendants(false).length,7,'measured main-program block count');
 assert.deepStrictEqual(f.d.getProcedureDef(),['avancer_un_pas',[],false]);
 Contract.preflightWorkspace(profile,f.w);Contract.preflightAst(profile,ast);
 const b=backend(),seen=[],changes=[];
 const mapping=Observer.buildSourceMap(f.w);
 const result=await Interpreter.run(ast,b,{maxSteps:200,hooks:{onNode:async ctx=>{seen.push(mapping[ctx.path.join('/')]);},onVariables:async ctx=>changes.push(ctx.values.pas)}});
 assert.deepStrictEqual(b.trace,['takeoff','move','move','move','land']);assert.deepStrictEqual(result.variables,{pas:3});
 assert.deepStrictEqual(changes,[0,1,2,3]);assert(seen.every(Boolean),'every executed node must map to a real Blockly block');
 assert.strictEqual(seen.filter(id=>id===f.c.id).length,3);assert.strictEqual(seen.filter(id=>id===f.move.id).length,3);
 assert.strictEqual(mapping['program/2/body/0/body/1/value/right'],f.change.getInputTargetBlock('DELTA').id);
 const cost=Interpreter.validateExecutionBudget(ast,200);
 assert.strictEqual(200-result.remainingBudget,cost,'static call budget must account for each expanded execution');
 const tooSmall=backend();await assert.rejects(()=>Interpreter.run(ast,tooSmall,{maxSteps:cost-1}),/before takeoff/);assert.deepStrictEqual(tooSmall.trace,[]);
 const noCapability=backend();delete noCapability.capabilities.procedures;
 await assert.rejects(()=>Interpreter.run(ast,noCapability),/procedures unavailable/);assert.deepStrictEqual(noCapability.trace,[]);
 assert.throws(()=>Contract.preflightBackend(profile,Contract.collectAst(ast),noCapability),/procedures unavailable/);
 assert.throws(()=>Physical.deriveFacts(ast),/unsupported AST statement kind: call/);
 assert.strictEqual(new Wwi({send(){}}).capabilities.procedures,true);
 const old=Profiles.resolveById(Activities.DOCUMENT,'progression-sequence-v1',Activities.BLOCK_CATALOG);
 assert.throws(()=>Contract.preflightWorkspace(old,f.w),/forbidden by profile/);
 assert.throws(()=>Contract.preflightAst(old,ast),/forbidden by profile/);
 // Ordinary portable .wbb, retained definition/call IDs and AST after validation.
 const text=Files.encodeProject(profile,f.w,fileOptions),loaded=Files.validateProjectText(text,profile,fileOptions);
 assert.deepStrictEqual(loaded.ast,ast);
 const reopened=new Blockly.Workspace();Blockly.serialization.workspaces.load(loaded.project.workspace,reopened);
 assert.deepStrictEqual(Compiler.compileWorkspace(reopened),ast);assert.deepStrictEqual(Observer.buildSourceMap(reopened),mapping);reopened.dispose();
 // Composition with #657: a pupil UNTIL can invoke the same procedure.
 const composition=fixture(),until=composition.w.newBlock('webeeblocks_v2_until');
 composition.c.previousConnection.disconnect();
 composition.repeat.getInput('DO').connection.connect(until.previousConnection);
 until.getInput('DO').connection.connect(composition.c.previousConnection);
 const condition=composition.w.newBlock('logic_compare'),read=composition.w.newBlock('variables_get');
 read.setFieldValue(composition.variable.getId(),'VAR');condition.setFieldValue('GTE','OP');
 condition.getInput('A').connection.connect(read.outputConnection);condition.getInput('B').connection.connect(number(composition.w,3).outputConnection);
 until.getInput('BOOL').connection.connect(condition.outputConnection);
 const composedAst=Compiler.compileWorkspace(composition.w),composedBackend=backend();
 assert.deepStrictEqual((await Interpreter.run(composedAst,composedBackend,{maxSteps:20000})).variables,{pas:3});
 assert.strictEqual(Observer.buildSourceMap(composition.w)['program/2/body/0/body/0/body/0'],composition.move.id);
 composition.w.dispose();
 const nested=fixture(),outer=definition(nested.w,'externe');
 outer.getInput('STACK').connection.connect(call(nested.w,'avancer_un_pas').previousConnection);
 nested.c.loadExtraState({name:'externe'});
 const nestedAst=Compiler.compileWorkspace(nested.w);
 assert.deepStrictEqual((await Interpreter.run(nestedAst,backend())).variables,{pas:3});
 assert.strictEqual(Observer.buildSourceMap(nested.w)['program/2/body/0/body/0/body/0'],nested.move.id);nested.w.dispose();
 // Rename uses Blockly's supported synchronization, not a second name registry.
 Blockly.Events.disable();
 try{f.d.setFieldValue('autre_nom','NAME');}finally{Blockly.Events.enable();}
 assert.strictEqual(f.c.getProcedureCall(),'autre_nom');assert.strictEqual(Compiler.compileWorkspace(f.w).program[2].body[0].name,'autre_nom');
 // Nonexistent calls, direct/indirect/unreachable cycles, signatures, flight edges.
 const missing=fixture();missing.c.loadExtraState({name:'absente'});assert.throws(()=>Compiler.compileWorkspace(missing.w),/undefined procedure/);missing.w.dispose();
 const direct=fixture(),self=call(direct.w,'avancer_un_pas');connect(direct.change,self);assert.throws(()=>Compiler.compileWorkspace(direct.w),/recursive procedure cycle/);direct.w.dispose();
 const indirect=fixture(),other=definition(indirect.w,'autre');other.getInput('STACK').connection.connect(call(indirect.w,'avancer_un_pas').previousConnection);connect(indirect.change,call(indirect.w,'autre'));assert.throws(()=>Compiler.compileWorkspace(indirect.w),/recursive procedure cycle/);indirect.w.dispose();
 const unused=fixture(),u=definition(unused.w,'inutile');u.getInput('STACK').connection.connect(call(unused.w,'inutile').previousConnection);assert.throws(()=>Compiler.compileWorkspace(unused.w),/recursive procedure cycle/);unused.w.dispose();
 const duplicate=fixture(),dup=definition(duplicate.w,'different');dup.getProcedureDef=()=>['AVANCER_UN_PAS',[],false];assert.throws(()=>Compiler.compileWorkspace(duplicate.w),/duplicate procedure/);duplicate.w.dispose();
 const params=fixture();params.d.loadExtraState({params:[{name:'x'}]});assert.throws(()=>Compiler.compileWorkspace(params.w),/parameters unsupported/);params.w.dispose();
 for(const type of ['webeeblocks_v2_takeoff','webeeblocks_v2_land']){
  const bad=fixture();connect(bad.change,bad.w.newBlock(type));assert.throws(()=>Compiler.compileWorkspace(bad.w),/top-level boundaries/);bad.w.dispose();
 }
 const incomplete=fixture();incomplete.l.dispose();assert.throws(()=>Compiler.compileWorkspace(incomplete.w),/end with land/);incomplete.w.dispose();
 const dangling=fixture();dangling.w.newBlock('webeeblocks_v2_move');assert.throws(()=>Compiler.compileWorkspace(dangling.w),/exactly one top-level/);dangling.w.dispose();
 const unassigned=fixture();unassigned.init.dispose(true);assert.throws(()=>Interpreter.validateProgram(Compiler.compileWorkspace(unassigned.w)),/before assignment/);unassigned.w.dispose();
 // Static and runtime restrictions descend into the expanded body.
 const sensed=program([astCall([{kind:'set_variable',variable:{id:'r',name:'mesure'},value:{kind:'range',direction:'front',unit:'m'}}])]);
 assert(Contract.collectAst(sensed).ranges.has('front'));
 const restricted=JSON.parse(JSON.stringify(profile));restricted.runtime.rangeDirections=[];
 assert.throws(()=>Contract.preflightAst(restricted,sensed),/range capability unavailable/);
 const over=program([astCall([{kind:'move',direction:'forward',distance_m:.5}])]);assert.throws(()=>Contract.preflightAst(profile,over),/outside profile bounds/);
 const invalid=backend([NaN]);await assert.rejects(()=>Interpreter.run(sensed,invalid),/must be finite/);assert.deepStrictEqual(invalid.trace,['takeoff','range']);
 const interrupted=backend();await assert.rejects(()=>Interpreter.run(ast,interrupted,{hooks:{beforeStep:async c=>{if(c.node.kind==='move')throw Object.assign(new Error('interrupted'),{code:'USER_STOPPED'});}}}),/interrupted/);assert.deepStrictEqual(interrupted.trace,['takeoff']);
 const infinite=program([astCall([{kind:'while',mode:'WHILE',condition:{kind:'number',value:1},body:[],max_iterations:2}])]);
 const guarded=backend();await assert.rejects(()=>Interpreter.run(infinite,guarded),/iteration limit exceeded/);assert.deepStrictEqual(guarded.trace,['takeoff']);
 const withoutLoop=backend();delete withoutLoop.capabilities.conditionalLoops;await assert.rejects(()=>Interpreter.run(infinite,withoutLoop),/conditional loops unavailable/);assert.deepStrictEqual(withoutLoop.trace,[]);
 const time=program([astCall([{kind:'set_variable',variable:{id:'t',name:'temps'},value:{kind:'elapsed_time',unit:'s'}}])]);
 assert(Contract.collectAst(time).elapsedTime);const unavailableTime=backend();await assert.rejects(()=>Interpreter.run(time,unavailableTime),/elapsed simulation time unavailable/);assert.deepStrictEqual(unavailableTime.trace,[]);
 const astNestedLand=program([astCall([{kind:'land'}])]);assert.throws(()=>Interpreter.validateProgram(astNestedLand),/top-level boundaries/);
 assert.throws(()=>Interpreter.validateProgram(program([{kind:'call',name:'x'}])),/sequence must be an array/);
 // Expanded DAG must stop before exponential resource consumption.
 const huge=fixture();
 for(let i=0;i<13;i++){
  const d=definition(huge.w,'p'+i);
  if(i===12)d.getInput('STACK').connection.connect(huge.w.newBlock('webeeblocks_v2_move').previousConnection);
  else{const a=call(huge.w,'p'+(i+1)),b=call(huge.w,'p'+(i+1));d.getInput('STACK').connection.connect(a.previousConnection);connect(a,b);}
 }
 assert.throws(()=>Compiler.compileWorkspace(huge.w),/procedure expansion too large/);huge.w.dispose();
 // Durable fixture generated from real blocks; no hand-authored AST masquerade.
 if(process.argv.includes('--write-fixture')){
  const demo=fixture();const target=root+'/tools/blockly/procedure_steps_demo.wbb';fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,Files.encodeProject(profile,demo.w,fileOptions));demo.w.dispose();
 }
 const demoPath=root+'/tools/blockly/procedure_steps_demo.wbb';
 if(fs.existsSync(demoPath)){
  const retained=Files.validateProjectText(fs.readFileSync(demoPath,'utf8'),profile,fileOptions);
  assert.deepStrictEqual((await Interpreter.run(retained.ast,backend())).variables,{pas:3});
 }
 f.w.dispose();
 console.log('PASS procedures: real Blockly definitions/calls, exact budget, rename, cycles/signatures, .wbb round-trip, source maps, nested restrictions, invalid sensor, interruption and physical refusal; demo 11 blocks');
}
module.exports=prove;
if(require.main===module)prove().catch(e=>{console.error(e);process.exitCode=1;});
