'use strict';
const assert=require('assert'),vm=require('vm'),fs=require('fs');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;require('../../plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js');delete global.Blockly;
const C=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const I=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const A=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const Obs=require('../../plugins/robot_windows/blockly/webeeblocks/execution_observer');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
function num(ws,v){let b=ws.newBlock('math_number');b.setFieldValue(String(v),'NUM');return b;}
function connect(b,name,v){b.getInput(name).connection.connect(v.outputConnection);return b;}
function readVar(ws,v){let b=ws.newBlock('variables_get');b.getField('VAR').setValue(v.getId());return b;}
function setVar(ws,v,x){let b=ws.newBlock('variables_set');b.getField('VAR').setValue(v.getId());return connect(b,'VALUE',x);}
function diff(ws,a,b){let x=ws.newBlock('math_arithmetic');x.setFieldValue('MINUS','OP');connect(x,'A',a);connect(x,'B',b);return x;}
function link(...bs){for(let i=1;i<bs.length;i++)bs[i-1].nextConnection.connect(bs[i].previousConnection);}
function profile(){
 let context={WebeeBlocksActivities:{BLOCK_CATALOG:Object.assign({},Activities.BLOCK_CATALOG),DOCUMENT:Activities.DOCUMENT},
 WebeeBlocksRuntimeOutcome:{classify:()=>({})},Blockly:{inject(){}},WebeeBlocksWwiBackend:function(){}};
 context.window=context;
 vm.runInNewContext(fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js','utf8'),context);
 return JSON.parse(JSON.stringify(context.WebeeBlocksActivities.getProfile('progression-grand-prix-u-v1')));
}
module.exports=async function(){
 const p=profile();
 assert.strictEqual(p.runtime.motionExpressions,true);
 assert.deepStrictEqual(p.runtime.astBounds['move.lateral.distance_m'],{min:.01,max:.6});
 assert.strictEqual(p.parameterBounds.math_number.NUM.step,.01);
 assert.strictEqual(p.toolbox.includes('webeeblocks_v2_move'),false);
 assert.strictEqual(p.toolbox.includes('webeeblocks_v2_move_expr'),true);
 const ws=new Blockly.Workspace(),alt=ws.getVariableMap().createVariable('altitude','','altitude'),margin=ws.getVariableMap().createVariable('marge','','marge');
 const setAlt=setVar(ws,alt,num(ws,.8)),setMargin=setVar(ws,margin,num(ws,.15));
 const takeoff=connect(ws.newBlock('webeeblocks_v2_takeoff_expr'),'HEIGHT',readVar(ws,alt));
 const move=ws.newBlock('webeeblocks_v2_move_expr'),sensor=ws.newBlock('webeeblocks_v2_range');
 sensor.setFieldValue('front','DIRECTION');connect(move,'DISTANCE',diff(ws,sensor,readVar(ws,margin)));
 const lateral=ws.newBlock('webeeblocks_v2_move_expr');lateral.setFieldValue('left','DIRECTION');connect(lateral,'DISTANCE',num(ws,.5));
 const vertical=ws.newBlock('webeeblocks_v2_vertical_expr');vertical.setFieldValue('down','DIRECTION');
 connect(vertical,'DISTANCE',diff(ws,readVar(ws,alt),num(ws,.4)));
 const land=ws.newBlock('webeeblocks_v2_land');link(setAlt,setMargin,takeoff,move,lateral,vertical,land);
 const ast=C.compileWorkspace(ws);I.validateProgram(ast);I.validateExecutionBudget(ast,20000);
 assert.strictEqual(ast.program[2].height_m.kind,'variable_get');
 assert.strictEqual(ast.program[3].distance_m.kind,'arithmetic');
 let copy=new Blockly.Workspace();Blockly.serialization.workspaces.load(Blockly.serialization.workspaces.save(ws),copy);
 assert.deepStrictEqual(C.compileWorkspace(copy),ast);
 const map=Obs.buildSourceMap(copy);assert(map['program/3/distance_m/left']);
 const facts=A.preflightAst(p,ast);assert(facts.ranges.has('front'));
 const effects=[],backend={capabilities:{actions:['takeoff','move','vertical','land'],rangeDirections:['front'],moveDirections:['forward','left'],verticalDirections:['down']},
 takeoff:async x=>effects.push(['takeoff',x]),move:async(d,x)=>effects.push(['move',d,x]),vertical:async(d,x)=>effects.push(['vertical',d,x]),
 land:async()=>effects.push(['land']),readRange:async()=>2};
 A.preflightBackend(p,facts,backend);
 await I.run(ast,backend,{motionBounds:p.runtime.astBounds,maxSteps:20000});
 assert.deepStrictEqual(effects,[['takeoff',.8],['move','forward',1.85],['move','left',.5],['vertical','down',.4],['land']]);
 const uniqueMove=ws.newBlock('webeeblocks_v2_move_expr');
 assert(uniqueMove.getInput('DISTANCE')&&!uniqueMove.getField('DISTANCE'),
   'Grand Prix movement must offer exactly one expression socket');uniqueMove.dispose();
 const bad=JSON.parse(JSON.stringify(ast));bad.program[4].distance_m={kind:'number',value:.61};
 const observed=[],guarded=Object.assign({},backend,{takeoff:async x=>observed.push('takeoff'),move:async(d,x)=>observed.push(d)});
 await assert.rejects(()=>I.run(bad,guarded,{motionBounds:p.runtime.astBounds}),/out-of-bounds/);
 assert.deepStrictEqual(observed,['takeoff','forward'],'out-of-range move reached backend');
 const unavailable=JSON.parse(JSON.stringify(p));unavailable.runtime.motionExpressions=false;
 assert.throws(()=>A.preflightAst(unavailable,ast),/motion expression unavailable/);
 const forbidden=JSON.parse(JSON.stringify(p));forbidden.runtime.rangeDirections=[];
 assert.throws(()=>A.preflightAst(forbidden,ast),/range capability unavailable/);
 // A centimetre is an admissible command length, not a 1 cm control accuracy guarantee.
 async function trial(kind,value,direction){
   const statement=kind==='takeoff'?{kind,height_m:{kind:'number',value}}:
     {kind,direction,distance_m:{kind:'number',value}};
   const body=kind==='takeoff'?[statement,{kind:'land'}]:
     [{kind:'takeoff',height_m:0.8},statement,{kind:'land'}];
   const candidate={version:1,semantics:'webeeblocks-ast-v1',program:body};
   const calls=[],b={takeoff:async h=>calls.push(['takeoff',h]),move:async(d,n)=>calls.push(['move',d,n]),
     vertical:async(d,n)=>calls.push(['vertical',d,n]),land:async()=>calls.push(['land'])};
   return {candidate,calls,backend:b};
 }
 for(const [kind,direction,good,bad] of [
   ['takeoff',null,[.3,1],[.29,1.01]],
   ['move','forward',[.01,1.9],[0,1.91]],
   ['move','back',[.01,1.9],[-.01,1.91]],
   ['move','left',[.01,.6],[0,.61]],
   ['move','right',[.01,.6],[0,.61]],
   ['vertical','up',[.1,.5],[.09,.51]],
   ['vertical','down',[.1,.5],[.09,.51]]
 ]){
   for(const value of good){
     const t=await trial(kind,value,direction);
     await I.run(t.candidate,t.backend,{motionBounds:p.runtime.astBounds});
     assert.strictEqual(t.calls.length,kind==='takeoff'?2:3,'valid boundary not dispatched');
   }
   for(const value of bad){
     const t=await trial(kind,value,direction);
     await assert.rejects(()=>I.run(t.candidate,t.backend,{motionBounds:p.runtime.astBounds}),/out-of-bounds/);
     assert.deepStrictEqual(t.calls,kind==='takeoff'?[]:[['takeoff',.8]],'invalid movement crossed the backend boundary');
   }
 }
 const old={version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.8},{kind:'move',direction:'forward',distance_m:.3},{kind:'land'}]};
 I.validateProgram(old);A.preflightAst(p,old);
 copy.dispose();ws.dispose();
 console.log('PASS Grand Prix single-expression movement toolbox, preflight, bounds, source-map and Blockly Save/Open');
};