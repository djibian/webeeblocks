'use strict';
const Reference=require('./program');
const move=(distance,direction='forward')=>({kind:'move',direction,distance_m:distance});
const vertical=direction=>({kind:'vertical',direction,distance_m:.4});
function build(){
 const mode=process.argv[3];let ast=Reference.build();
 if(mode==='wrong-landing'){
  const alter=o=>{if(Array.isArray(o))o.forEach(alter);else if(o&&typeof o==='object'){
   if(o.kind==='compare'&&o.op==='EQ'&&o.left.kind==='variable_get'&&o.left.variable.name==='portes'&&o.right.kind==='number')o.right.value=999;
   Object.values(o).forEach(alter);
  }};alter(ast);return ast;
 }
 const prefix=[{kind:'takeoff',height_m:.4},vertical('up')];let body;
 if(mode==='deadline')body=[{kind:'repeat',count:20,body:[{kind:'repeat',count:2,body:[move(.4),move(.4,'back')]}]}];
 if(mode==='low-outside')body=[move(.3),vertical('down')];
 if(mode==='collision')body=[move(.4),move(.4)];
 if(mode==='reverse')body=[move(.4),move(.2),vertical('down'),move(.4),move(.3),move(.4,'back'),move(.3,'back')];
 if(!body)throw Error('unknown bounded negative mode');
 return {version:1,semantics:'webeeblocks-ast-v1',program:[...prefix,...body,{kind:'land'}]};
}
module.exports={build};
