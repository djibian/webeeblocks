(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.WebeeBlocksDynamicBackend=factory();})(typeof self!=='undefined'?self:this,function(){
'use strict';
function fail(m){throw new Error('dynamic backend: '+m);}
function finite(v,n){var x=Number(v);if(!Number.isFinite(x))fail(n+' must be finite');return x;}
function Backend(endpoint){this.endpoint=endpoint||'http://127.0.0.1:8766';this.trace=[];}
Backend.prototype.assertCapabilities=function(ast){
  function expr(e){if(!e||typeof e.kind!=='string')fail('invalid AST expression');if(e.kind==='number')return;if(e.kind==='range'){if(e.direction!=='front')fail('capability unavailable: range('+e.direction+')');return;}if(e.kind==='compare'||e.kind==='logic'){expr(e.left);expr(e.right);return;}fail('capability unavailable: expression '+e.kind);}
  function seq(xs){if(!Array.isArray(xs))fail('invalid AST sequence');xs.forEach(function(s){if(!s||typeof s.kind!=='string')fail('invalid AST statement');if(s.kind==='takeoff'||s.kind==='land')return;if(s.kind==='move'){if(s.direction!=='forward'&&s.direction!=='left')fail('capability unavailable: move('+s.direction+')');return;}if(s.kind==='if'){expr(s.condition);seq(s.then||[]);seq(s.else||[]);return;}if(s.kind==='repeat'){seq(s.body||[]);return;}fail('capability unavailable: '+s.kind);});}
  if(!ast||ast.version!==1||ast.semantics!=='webeeblocks-experimental-ast')fail('unsupported AST envelope');seq(ast.program);return true;
};
Backend.prototype.rpc=function(payload){var x=new XMLHttpRequest();x.open('POST',this.endpoint+'/rpc',false);x.setRequestHeader('Content-Type','text/plain;charset=UTF-8');x.send(JSON.stringify(payload));var r;try{r=JSON.parse(x.responseText);}catch(e){fail('invalid RPC JSON');}if(x.status!==200||!r||r.ok!==true)fail((r&&r.error)||('RPC HTTP '+x.status));return r;};
Backend.prototype.readRange=function(direction){if(direction!=='front')fail('capability unavailable: range('+direction+')');var r=this.rpc({op:'range',direction:direction});var v=finite(r.value_m,'range(front)');this.trace.push({op:'range',direction:'front',value_m:v,source:r.source});return v;};
Backend.prototype.takeoff=function(h){h=finite(h,'height_m');var r=this.rpc({op:'takeoff',height_m:h});this.trace.push({op:'takeoff',height_m:h,before:r.before,after:r.after,stop:r.stop});};
Backend.prototype.land=function(){var r=this.rpc({op:'land'});this.trace.push({op:'land',before:r.before,after:r.after,stop:r.stop});};
Backend.prototype.move=function(direction,d){if(direction!=='forward'&&direction!=='left')fail('capability unavailable: move('+direction+')');d=finite(d,'distance_m');var r=this.rpc({op:'move',direction:direction,distance_m:d});this.trace.push({op:'move',direction:direction,distance_m:d,before:r.before,after:r.after,stop:r.stop});};
Backend.prototype.vertical=function(){fail('capability unavailable: vertical');};Backend.prototype.turn=function(){fail('capability unavailable: turn');};Backend.prototype.wait=function(){fail('capability unavailable: wait');};Backend.prototype.setSpeed=function(){fail('capability unavailable: setSpeed');};
Backend.prototype.getControllerTrace=function(){var x=new XMLHttpRequest();x.open('GET',this.endpoint+'/trace',false);x.send(null);if(x.status!==200)fail('trace HTTP '+x.status);return JSON.parse(x.responseText);};
return {DynamicBackend:Backend};
});
