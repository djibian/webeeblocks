/* Frozen experimental snapshot from draft #46 / #44 semantics. A2 seam proof only. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebeeBlocksExtended = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  const LIMITS={height_m:{min:0.2,max:1.5},distance_m:{min:0.1,max:2.0},vertical_m:{min:0.1,max:0.8},wait_s:{min:0.1,max:5},speed_m_s:{min:0.1,max:0.6},range_m:{min:0.05,max:4},repeat:{min:1,max:20}};
  const SENSOR_DIRECTIONS=['front','back','left','right','up'];
  function finite(v,n){const x=Number(v);if(!Number.isFinite(x))throw new Error(n+' must be finite');return x;}
  function bounded(v,n,l){const x=finite(v,n);if(x<l.min||x>l.max)throw new Error(n+' out of experimental range: '+x);return x;}
  function field(b,n){if(!b||typeof b.getFieldValue!=='function')throw new Error('invalid Blockly block');return b.getFieldValue(n);}
  function valueChild(b,n){const c=b.getInputTargetBlock(n);if(!c)throw new Error('missing value input '+n);return compileExpression(c);}
  function compileExpression(b){switch(b.type){case'webeeblocks_exp_range':{const d=String(field(b,'DIRECTION'));if(SENSOR_DIRECTIONS.indexOf(d)<0)throw new Error('unsupported range direction: '+d);return{kind:'range',direction:d,unit:'m'};}case'math_number':return{kind:'number',value:finite(field(b,'NUM'),'number')};case'logic_compare':{const op=String(field(b,'OP'));return{kind:'compare',op:op,left:valueChild(b,'A'),right:valueChild(b,'B')};}default:throw new Error('unsupported experimental expression block: '+b.type);}}
  function compileSequence(first){const out=[];let b=first,g=0;while(b){if(++g>200)throw new Error('experimental program too large');out.push(compileStatement(b));b=b.getNextBlock?b.getNextBlock():null;}return out;}
  function repeatCount(b){if(b.getInputTargetBlock&&b.getInputTargetBlock('TIMES')){const e=valueChild(b,'TIMES');if(e.kind!=='number'||Math.floor(e.value)!==e.value)throw new Error('repeat count must be an integer literal');return bounded(e.value,'repeat',LIMITS.repeat);}return bounded(field(b,'TIMES'),'repeat',LIMITS.repeat);}
  function compileStatement(b){switch(b.type){case'webeeblocks_exp_takeoff':return{kind:'takeoff',height_m:bounded(field(b,'HEIGHT'),'height_m',LIMITS.height_m)};case'webeeblocks_exp_land':return{kind:'land'};case'webeeblocks_exp_move':{const d=String(field(b,'DIRECTION'));if(['forward','back','left','right'].indexOf(d)<0)throw new Error('unsupported move direction: '+d);return{kind:'move',direction:d,distance_m:bounded(field(b,'DISTANCE'),'distance_m',LIMITS.distance_m)};}case'controls_repeat_ext':return{kind:'repeat',count:repeatCount(b),body:compileSequence(b.getInputTargetBlock('DO'))};case'controls_if':{const r={kind:'if',condition:valueChild(b,'IF0'),then:compileSequence(b.getInputTargetBlock('DO0'))};const e=b.getInputTargetBlock('ELSE');if(e)r.else=compileSequence(e);return r;}default:throw new Error('unsupported experimental statement block: '+b.type);}}
  function compileWorkspace(ws){const tops=ws.getTopBlocks(true);if(tops.length!==1)throw new Error('experimental Crazyflie program must have exactly one top-level sequence');const program=compileSequence(tops[0]);if(program.length<2||program[0].kind!=='takeoff'||program[program.length-1].kind!=='land')throw new Error('experimental program must start with takeoff and end with land');return{version:1,semantics:'webeeblocks-experimental-ast',program:program};}
  return{compileWorkspace:compileWorkspace};
});
