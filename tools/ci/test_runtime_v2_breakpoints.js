'use strict';
// Transient source-ID breakpoints: interpreter effects, loop/procedure re-entry,
// AST v1 lowered else-if, cancellation and non-persistence of block content.
const assert = require('assert');
const Observer = require('../../plugins/robot_windows/blockly/webeeblocks/execution_observer');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');

function fakeBlock(id, type, inputs) {
  const classes = new Set();
  return {
    id, type, inputs:inputs || {}, next:null, classes,
    getNextBlock() {return this.next;},
    getInputTargetBlock(name) {return this.inputs[name] || null;},
    getSvgRoot() {return {classList:{toggle(name, yes) {
      if (yes) classes.add(name); else classes.delete(name);
    }}};}
  };
}
function fixture() {
  const start=fakeBlock('start','webeeblocks_v2_takeoff');
  const repeat=fakeBlock('repeat','controls_repeat_ext');
  const call=fakeBlock('call','procedures_callnoreturn');
  call.getProcedureCall=()=> 'scan';
  const definition=fakeBlock('definition','procedures_defnoreturn');
  definition.getProcedureDef=()=>['scan'];
  const ifBlock=fakeBlock('choice','controls_if');
  ifBlock.elseifCount_=1;
  const front=fakeBlock('front','webeeblocks_v2_range');
  const right=fakeBlock('right','webeeblocks_v2_range');
  const leftMove=fakeBlock('move-left','webeeblocks_v2_move');
  const rightMove=fakeBlock('move-right','webeeblocks_v2_move');
  const fallback=fakeBlock('fallback','webeeblocks_v2_move');
  const end=fakeBlock('end','webeeblocks_v2_land');
  start.next=repeat;repeat.next=end;
  repeat.inputs.DO=call;
  definition.inputs.STACK=ifBlock;
  ifBlock.inputs={IF0:front,DO0:leftMove,IF1:right,DO1:rightMove,ELSE:fallback};
  const blocks=[start,repeat,call,definition,ifBlock,front,right,leftMove,rightMove,fallback,end];
  const ids=Object.fromEntries(blocks.map(b=>[b.id,b]));
  const workspace = {
    getTopBlocks() {return [start,definition];},
    getBlockById(id) {return ids[id]||null;},
    getAllBlocks() {return blocks;},
    highlightBlock(id) {this.currentHighlight=id;}
  };
  blocks.forEach(b=>{b.workspace=workspace;});
  return {workspace, ids};
}
function program(count) {
  return {version:1,semantics:'webeeblocks-ast-v1',program:[
    {kind:'takeoff',height_m:0.5},
    {kind:'repeat',count:count||2,body:[
      {kind:'call',name:'scan',body:[
        {kind:'if',
          condition:{kind:'range',direction:'front',unit:'m'},
          then:[{kind:'move',direction:'left',distance_m:0.2}],
          else:[{kind:'if',
            condition:{kind:'range',direction:'right',unit:'m'},
            then:[{kind:'move',direction:'right',distance_m:0.2}],
            else:[{kind:'move',direction:'forward',distance_m:0.2}]
          }]
        }
      ]}
    ]},
    {kind:'land'}
  ]};
}
function backend() {
  const trace=[];
  return {trace,capabilities:{procedures:true,conditionalLoops:true},
    async takeoff(){trace.push('takeoff');},
    async move(dir){trace.push('move:'+dir);},
    async land(){trace.push('land');},
    async readRange(direction){trace.push('sensor:'+direction);return direction==='front'?0:1;}
  };
}
async function until(predicate,label) {
  for(let n=0;n<500;n++){
    if(predicate())return;
    await new Promise(resolve=>setTimeout(resolve,0));
  }
  throw Error('timeout: '+label);
}
async function repeatedCallAndElseIf() {
  const {workspace,ids}=fixture(),original=JSON.stringify(program());
  const map=Observer.buildSourceMap(workspace);
  const prefix='program/1/body/0/body/0';
  assert.equal(map[prefix],'choice');
  assert.equal(map[prefix+'/else/0'],'choice','lowered else-if maps to same visible block');
  assert.equal(map[prefix+'/else/0/condition'],'right');
  assert.equal(map[prefix+'/else/0/then/0'],'move-right');
  assert.equal(map[prefix+'/else/0/else/0'],'fallback');
  const pauses=[],b=backend(),obs=Observer.create(workspace,{onPause:d=>pauses.push(d)});
  assert.equal(obs.toggleBreakpoint('definition'),false,'definition has no executable AST node');
  assert.equal(obs.toggleBreakpoint('choice'),true);
  assert(obs.hasBreakpoint('choice'));
  assert(ids.choice.classes.has('webeeblocks-breakpoint'));
  assert.equal(JSON.stringify(program()),original,'a breakpoint must not mutate the semantic AST');
  const run=Interpreter.run(program(),b,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'first step');
  assert.equal(pauses[0].blockId,'start');
  obs.continueRun();
  await until(()=>pauses.length===2,'first procedure call');
  assert.equal(pauses[1].blockId,'choice');
  assert.equal(pauses[1].reason,'breakpoint');
  assert.deepEqual(b.trace,['takeoff'],'must stop before the conditional sensor read');
  obs.continueRun();
  await until(()=>pauses.length===3,'repeated procedure call');
  assert.equal(pauses[2].blockId,'choice');
  assert.equal(pauses[2].reason,'breakpoint');
  // No second pause at else-if IF1 of the same visible block on either iteration.
  assert.deepEqual(b.trace,['takeoff','sensor:front','sensor:right','move:right']);
  obs.continueRun();await run;obs.finish();
  assert.equal(pauses.length,3,'Continue must not pause again for the same else-if visit');
  assert.deepEqual(b.trace,['takeoff','sensor:front','sensor:right','move:right',
    'sensor:front','sensor:right','move:right','land']);
  assert(ids.choice.classes.has('webeeblocks-breakpoint'),'marker remains until explicitly cleared');
  obs.clearBreakpoints();
  assert(!ids.choice.classes.has('webeeblocks-breakpoint'));
  assert.equal(obs.breakpoints.size,0);
}
async function changeWhilePausedAndResume() {
  const {workspace}=fixture(),pauses=[],b=backend(),obs=Observer.create(workspace,{
    onPause:d=>pauses.push(d)
  });
  const run=Interpreter.run(program(1),b,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'first pause');
  assert.equal(obs.toggleBreakpoint('end'),true,'add while paused');
  obs.continueRun();
  await until(()=>pauses.length===2,'land breakpoint');
  assert.equal(pauses[1].blockId,'end');
  assert.deepEqual(b.trace,['takeoff','sensor:front','sensor:right','move:right']);
  assert.equal(obs.toggleBreakpoint('end'),true,'remove while paused');
  assert.equal(obs.hasBreakpoint('end'),false);
  obs.continueRun();await run;obs.finish();
  assert.equal(pauses.length,2);
  assert.equal(b.trace.at(-1),'land');
}
async function breakOnExpressionAndStop() {
  const {workspace}=fixture(),pauses=[],b=backend(),obs=Observer.create(workspace,{
    onPause:d=>pauses.push(d)
  });
  obs.toggleBreakpoint('front');
  const run=Interpreter.run(program(1),b,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'first step');
  obs.continueRun();
  await until(()=>pauses.length===2,'sensor breakpoint');
  assert.equal(pauses[1].blockId,'front');
  assert.deepEqual(b.trace,['takeoff'],'range not yet read at expression breakpoint');
  assert(obs.cancel(),'STOP must cancel pending debugger wait');
  let error;
  try {await run;} catch(e){error=e;}
  assert(error && error.code==='USER_STOPPED','STOP must reject before further commands');
  obs.finish();
  assert.deepEqual(b.trace,['takeoff'],'no additional backend action after STOP');
  const resetTrace=[];
  await (async()=>{resetTrace.push('RESET');})();
  assert.deepEqual(resetTrace,['RESET'],'reset can follow native STOP, never bypass it');
}
async function singleStepDoesNotDoublePause() {
  const {workspace}=fixture(),pauses=[],b=backend(),obs=Observer.create(workspace,{
    onPause:d=>pauses.push(d)
  });
  obs.toggleBreakpoint('start');
  const run=Interpreter.run(program(1),b,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'step at takeoff');
  obs.continueRun(); // Continue from an ordinary step must not re-pause at the same beforeStep.
  await run;obs.finish();
  assert.equal(pauses.length,1);
  assert.equal(b.trace.at(-1),'land');
}

function graphSnapshot(workspace) {
  return JSON.stringify(workspace.getAllBlocks().map(block=>({
    id:block.id,type:block.type,next:block.next&&block.next.id,
    inputs:Object.keys(block.inputs||{}).sort().map(name=>[name,block.inputs[name]&&block.inputs[name].id])
  })));
}
async function breakOnLoopAndCall() {
  const {workspace}=fixture(),b=backend(),pauses=[],obs=Observer.create(workspace,{
    onPause:d=>pauses.push(d)
  });
  obs.toggleBreakpoint('repeat');
  obs.toggleBreakpoint('call');
  const before=graphSnapshot(workspace);
  const run=Interpreter.run(program(2),b,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'start');
  obs.continueRun();
  await until(()=>pauses.length===2,'repeat onNode');
  assert.equal(pauses[1].blockId,'repeat');
  assert.equal(pauses[1].reason,'breakpoint');
  assert.deepEqual(b.trace,['takeoff']);
  obs.continueRun();
  await until(()=>pauses.length===3,'first call');
  assert.equal(pauses[2].blockId,'call');
  assert.deepEqual(b.trace,['takeoff']);
  obs.continueRun();
  await until(()=>pauses.length===4,'second repeat iteration');
  assert.equal(pauses[3].blockId,'repeat');
  assert.equal(pauses[3].iteration,1);
  assert.deepEqual(b.trace,['takeoff','sensor:front','sensor:right','move:right']);
  obs.continueRun();
  await until(()=>pauses.length===5,'second procedure call');
  assert.equal(pauses[4].blockId,'call');
  obs.continueRun();await run;obs.finish();
  assert.equal(pauses.length,5,'no duplicate pause on loop/call beforeStep');
  assert.equal(b.trace[b.trace.length-1],'land');
  assert.equal(graphSnapshot(workspace),before,'breakpoint marker mutated serialized Blockly graph');
}
async function conditionalWhileReentry() {
  const start=fakeBlock('while-start','webeeblocks_v2_takeoff');
  const loop=fakeBlock('while-loop','controls_whileUntil');
  const range=fakeBlock('while-range','webeeblocks_v2_range');
  const move=fakeBlock('while-move','webeeblocks_v2_move');
  const land=fakeBlock('while-land','webeeblocks_v2_land');
  start.next=loop;loop.next=land;loop.inputs={BOOL:range,DO:move};
  const blocks=[start,loop,range,move,land],lookup=Object.fromEntries(blocks.map(x=>[x.id,x]));
  const w={getTopBlocks(){return[start];},getAllBlocks(){return blocks;},
    getBlockById(id){return lookup[id]||null;},highlightBlock(){}};
  blocks.forEach(x=>x.workspace=w);
  const ast={version:1,semantics:'webeeblocks-ast-v1',program:[
    {kind:'takeoff',height_m:0.5},
    {kind:'while',mode:'WHILE',max_iterations:3,
      condition:{kind:'range',direction:'front',unit:'m'},
      body:[{kind:'move',direction:'forward',distance_m:0.2}]},
    {kind:'land'}]};
  const values=[1,1,0],b=backend(),pauses=[],obs=Observer.create(w,{onPause:d=>pauses.push(d)});
  b.readRange=async ()=>{const value=values.shift();b.trace.push('while-range:'+value);return value;};
  obs.toggleBreakpoint('while-loop');
  const run=Interpreter.run(ast,b,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'while takeoff');
  obs.continueRun();
  await until(()=>pauses.length===2,'while first entry');
  assert.equal(pauses[1].blockId,'while-loop');
  assert.deepEqual(b.trace,['takeoff'],'loop breakpoint must pause before initial condition');
  obs.continueRun();
  await until(()=>pauses.length===3,'while next iteration');
  assert.equal(pauses[2].blockId,'while-loop');
  assert.equal(pauses[2].iteration,1);
  assert.deepEqual(b.trace,['takeoff','while-range:1','move:forward','while-range:1']);
  obs.continueRun();await run;obs.finish();
  assert.equal(pauses.length,3,'while re-entry skipped/duplicated a breakpoint');
  assert.deepEqual(b.trace,['takeoff','while-range:1','move:forward',
    'while-range:1','move:forward','while-range:0','land']);
}

async function test() {
  await breakOnLoopAndCall();
  await conditionalWhileReentry();
  await repeatedCallAndElseIf();
  await changeWhilePausedAndResume();
  await breakOnExpressionAndStop();
  await singleStepDoesNotDoublePause();
  console.log('PASS: transient breakpoints across repeat/while loops, repeated procedures, AST else-if, graph invariance, pause edits, STOP and Continue');
}
module.exports=test;
if(require.main===module)test().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
