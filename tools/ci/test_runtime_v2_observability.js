'use strict';
const assert = require('assert');
const Interpreter = require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const Observer = require('../../plugins/robot_windows/blockly/webeeblocks/execution_observer.js');
const Outcome = require('../../plugins/robot_windows/blockly/webeeblocks/runtime_outcome.js');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
function block(id,type,inputs){return{id,type,_next:null,_inputs:inputs||{},getNextBlock(){return this._next;},getInputTargetBlock(name){return this._inputs[name]||null;}};}
function link(){var blocks=Array.from(arguments);for(var i=0;i<blocks.length-1;i++)blocks[i]._next=blocks[i+1];return blocks[0];}
function ast(){return{version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:1},{kind:'repeat',count:3,body:[{kind:'if',condition:{kind:'compare',op:'LT',left:{kind:'range',direction:'front',unit:'m'},right:{kind:'number',value:.5}},then:[{kind:'move',direction:'left',distance_m:.3}],else:[{kind:'move',direction:'forward',distance_m:.3}]}]},{kind:'land'}]};}
function backend(values){var r=values.slice(),trace=[];return{trace,async takeoff(h){trace.push(['takeoff',h]);},async land(){trace.push(['land']);},async move(d,x){trace.push(['move',d,x]);},async vertical(){throw Error('unused');},async turn(){throw Error('unused');},async wait(){throw Error('unused');},async setSpeed(){throw Error('unused');},async readRange(d){var v=r.shift();trace.push(['range',d,v]);return v;}};}
function workspace(){var range=block('range-front','webeeblocks_v2_range'),num=block('threshold','math_number'),cmp=block('compare','logic_compare',{A:range,B:num}),left=block('left-action','webeeblocks_v2_move'),forward=block('forward-action','webeeblocks_v2_move'),iff=block('if','controls_if',{IF0:cmp,DO0:left,ELSE:forward}),repeat=block('repeat','controls_repeat_ext',{DO:iff}),takeoff=block('takeoff','webeeblocks_v2_takeoff'),land=block('land','webeeblocks_v2_land');link(takeoff,repeat,land);var all={takeoff,repeat,if:iff,compare:cmp,'range-front':range,threshold:num,'left-action':left,'forward-action':forward,land};return{getTopBlocks(){return[takeoff];},getBlockById(id){return all[id]||null;},highlightBlock(){}};}
async function until(p,label){var start=Date.now();while(Date.now()-start<1000){if(p())return;await new Promise(r=>setTimeout(r,0));}throw Error('timeout '+label);}
(async()=>{
  var a=backend([.4,.8,.3]),b=backend([.4,.8,.3]),program=ast();
  await Interpreter.run(program,a,{maxSteps:1000});
  await Interpreter.run(program,b,{maxSteps:1000,hooks:{onNode(){},beforeStep(){},onSensor(){}}});
  assert.deepStrictEqual(a.trace,b.trace);assert.deepStrictEqual(program,ast());
  var c=backend([.4,.8,.3]),pauses=[],sensors=[],obs=Observer.create(workspace(),{onPause:d=>pauses.push([d.blockId,d.node.kind,d.iteration,d.decision]),onSensor:d=>sensors.push([d.blockId,d.direction,d.value])});
  var run=Interpreter.run(ast(),c,{maxSteps:1000,hooks:obs.begin(true)});
  await until(()=>pauses.length===1,'takeoff');assert.deepStrictEqual(c.trace,[]);assert.deepStrictEqual(pauses[0].slice(0,2),['takeoff','takeoff']);obs.next();
  await until(()=>pauses.length===2,'repeat iteration');assert.deepStrictEqual(c.trace,[['takeoff',1]]);assert.deepStrictEqual(pauses[1].slice(0,3),['repeat','repeat',0]);obs.next();
  await until(()=>pauses.length===3,'range');assert.deepStrictEqual(c.trace,[['takeoff',1]]);assert.deepStrictEqual(pauses[2].slice(0,2),['range-front','range']);obs.next();
  await until(()=>sensors.length===1,'sensor');await until(()=>pauses.length===4,'number');assert.deepStrictEqual(sensors[0],['range-front','front',.4]);assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[3].slice(0,2),['threshold','number']);obs.next();
  await until(()=>pauses.length===5,'compare decision');assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[4].slice(0,2),['compare','compare']);obs.next();
  await until(()=>pauses.length===6,'if branch decision');assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[5].slice(0,2),['if','if']);assert.strictEqual(pauses[5][3],true);obs.next();
  await until(()=>pauses.length===7,'chosen move');assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4]]);assert.deepStrictEqual(pauses[6].slice(0,2),['left-action','move']);obs.continueRun();await run;obs.finish();
  assert.deepStrictEqual(c.trace,[['takeoff',1],['range','front',.4],['move','left',.3],['range','front',.8],['move','forward',.3],['range','front',.3],['move','left',.3],['land']]);
  var sent=[],wwi=new WwiBackend({send:m=>sent.push(m)},{timeoutMs:500,simulationDebug:true});var req=wwi.move('forward',2);wwi.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 ERR UNSAFE_OR_TIMEOUT');var error;try{await req;}catch(e){error=e;}assert.strictEqual(error.code,'UNSAFE_OR_TIMEOUT');assert.strictEqual(error.message,'Runtime v2 backend error: UNSAFE_OR_TIMEOUT');assert.deepStrictEqual(Outcome.classify(error),{state:'ARRÊTÉ',detail:'L’action n’a pas pu être terminée',machineCode:'UNSAFE_OR_TIMEOUT'});assert.strictEqual(Outcome.classify(Error('technical')).state,'ERREUR');assert.strictEqual(wwi.capabilities.simulationDebug,true);
  var physical=new WwiBackend({send:m=>sent.push(m)},{timeoutMs:500,simulationDebug:false});assert.notStrictEqual(physical.capabilities.simulationDebug,true);
  console.log('PASS: observability is optional, semantic stepping pauses through decisions, raw sensor is fresh, and machine codes remain testable.');
})().catch(e=>{console.error(e.stack||e);process.exit(1);});
