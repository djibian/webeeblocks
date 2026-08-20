/* Frozen experimental snapshot from draft #45. A2 seam proof only. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebeeBlocksReactiveInterpreter = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  const SENSOR_DIRECTIONS=['front','back','left','right','up'];
  const MOVE_DIRECTIONS=['forward','back','left','right'];
  function fail(m){throw new Error('reactive AST: '+m);}
  function finite(v,n){const x=Number(v);if(!Number.isFinite(x))fail(n+' must be finite');return x;}
  function method(b,n){if(!b||typeof b[n]!=='function')fail('backend is missing '+n+'()');return b[n].bind(b);}
  function evalExpr(e,b,budget,d){if(--budget.remaining<0)fail('execution budget exceeded');switch(e.kind){case'number':return finite(e.value,'number');case'range':{if(SENSOR_DIRECTIONS.indexOf(e.direction)<0||e.unit!=='m')fail('unsupported range expression');return finite(method(b,'readRange')(e.direction),'range');}case'compare':{const l=evalExpr(e.left,b,budget,d+1),r=evalExpr(e.right,b,budget,d+1);if(e.op==='LT')return l<r;if(e.op==='LTE')return l<=r;if(e.op==='GT')return l>r;if(e.op==='GTE')return l>=r;if(e.op==='EQ')return l===r;if(e.op==='NEQ')return l!==r;fail('unsupported comparison '+e.op);}default:fail('unsupported expression kind '+e.kind);}}
  function seq(items,b,budget,d){for(const s of items||[]){if(--budget.remaining<0)fail('execution budget exceeded');switch(s.kind){case'takeoff':method(b,'takeoff')(finite(s.height_m,'height_m'));break;case'land':method(b,'land')();break;case'move':if(MOVE_DIRECTIONS.indexOf(s.direction)<0)fail('unsupported move direction');method(b,'move')(s.direction,finite(s.distance_m,'distance_m'));break;case'if':seq(evalExpr(s.condition,b,budget,d+1)?s.then:(s.else||[]),b,budget,d+1);break;case'repeat':if(!Number.isInteger(s.count)||s.count<1||s.count>20)fail('repeat count out of bounds');for(let i=0;i<s.count;i++)seq(s.body,b,budget,d+1);break;default:fail('unsupported statement kind '+s.kind);}}}
  function run(ast,b){if(!ast||ast.version!==1||ast.semantics!=='webeeblocks-experimental-ast')fail('unsupported AST envelope');const budget={remaining:1000};seq(ast.program,b,budget,0);return{remainingBudget:budget.remaining};}
  function ScriptedBackend(scripts){this.rangeScripts=scripts||{};this.rangeOffsets={};this.trace=[];}
  ScriptedBackend.prototype.readRange=function(d){const a=this.rangeScripts[d],i=this.rangeOffsets[d]||0;if(!a||i>=a.length)fail('no scripted range sample for '+d);const v=finite(a[i],'range');this.rangeOffsets[d]=i+1;this.trace.push({op:'range',direction:d,value_m:v});return v;};
  ScriptedBackend.prototype.takeoff=function(h){this.trace.push({op:'takeoff',height_m:h});};
  ScriptedBackend.prototype.land=function(){this.trace.push({op:'land'});};
  ScriptedBackend.prototype.move=function(d,x){this.trace.push({op:'move',direction:d,distance_m:x});};
  return{run:run,ScriptedBackend:ScriptedBackend};
});
