/* Developer-authored gp-v4 strategy D; ordinary AST, never an oracle API. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.WebeeBlocksGrandPrixTimePolicy=factory();})(typeof self!=='undefined'?self:this,function(){
'use strict';
const n=value=>({kind:'number',value});
const v=name=>({kind:'variable_get',variable:{id:'gp-'+name,name}});
const set=(name,value)=>({kind:'set_variable',variable:{id:'gp-'+name,name},value:typeof value==='number'?n(value):value});
const ar=(op,left,right)=>({kind:'arithmetic',op,left,right:typeof right==='number'?n(right):right});
const cmp=(op,left,right)=>({kind:'compare',op,left,right:typeof right==='number'?n(right):right});
const and=(left,right)=>({kind:'logic',op:'AND',left,right});
const iff=(condition,then,otherwise=[])=>({kind:'if',condition,then,else:otherwise});
function build(navigation,threshold,reserve=150){
 if(!navigation||typeof navigation.build!=='function')throw new Error('navigation witness required');
 if(!Number.isInteger(threshold)||threshold<1||threshold>600||!Number.isFinite(reserve)||reserve<0||reserve>600)throw new Error('invalid public timing policy');
 const ast=JSON.parse(JSON.stringify(navigation.build(true,2,true,false)));
 const circuit=ast.program.find(node=>node.kind==='repeat'&&node.count===2);
 if(!circuit)throw new Error('bounded two-lap navigation required');
 const decision=[
  set('temps observé',{kind:'elapsed_time',unit:'s'}),
  set('retard sortie',ar('MINUS',ar('ADD',v('temps observé'),reserve),threshold)),
  iff(cmp('LT',v('retard sortie'),0),[set('retard sortie',0)]),
  set('retard poursuite',ar('MINUS',ar('ADD',ar('MULTIPLY',v('temps observé'),2),reserve),threshold)),
  iff(cmp('LT',v('retard poursuite'),0),[set('retard poursuite',0)]),
  iff(cmp('GTE',ar('MINUS',v('retard poursuite'),v('retard sortie')),ar('MULTIPLY',v('portes'),5)),[set('sortie',1)])
 ];
 let replaced=0;
 function body(items){for(let i=0;i<items.length;i++){
  const node=items[i],c=node.condition;
  if(node.kind==='if'&&c&&c.kind==='logic'&&c.op==='AND'&&c.left.kind==='compare'&&c.left.op==='EQ'&&c.left.left.kind==='variable_get'&&c.left.left.variable.name==='tour'&&c.left.right.value===1&&c.right.kind==='compare'&&c.right.left.kind==='variable_get'&&c.right.left.variable.name==='coin'&&c.right.right.value===3){
   items.splice(i,0,iff(and(cmp('EQ',v('tour'),0),cmp('EQ',v('coin'),3)),JSON.parse(JSON.stringify(decision))));i++;
   node.condition=and({kind:'logic',op:'OR',left:cmp('GTE',v('tour'),1),right:cmp('EQ',v('sortie'),1)},cmp('EQ',v('coin'),3));
   replaced++;
  }
  for(const key of ['body','then','else'])if(Array.isArray(node[key]))body(node[key]);
 }}
 body(circuit.body);
 if(replaced!==2)throw new Error('navigation corner contract changed');
 const index=ast.program.indexOf(circuit);
 ast.program.splice(index,0,...['temps observé','retard sortie','retard poursuite'].map(name=>set(name,0)));
 ast.program[ast.program.indexOf(circuit)]={kind:'while',mode:'UNTIL',condition:cmp('EQ',v('sortie'),1),body:circuit.body,max_iterations:2};
 return ast;
}
return {build};
});
