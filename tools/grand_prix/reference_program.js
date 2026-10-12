/* Machine witness only. Uses the ordinary shared AST, no oracle/config input. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.WebeeBlocksGrandPrixWitness=factory();})(typeof self!=='undefined'?self:this,function(){
'use strict';
const n=value=>({kind:'number',value});
const v=name=>({kind:'variable_get',variable:{id:'gp-'+name,name}});
const set=(name,value)=>({kind:'set_variable',variable:{id:'gp-'+name,name},value:typeof value==='number'?n(value):value});
const ar=(op,left,right)=>({kind:'arithmetic',op,left,right:typeof right==='number'?n(right):right});
const cmp=(op,left,right)=>({kind:'compare',op,left,right:typeof right==='number'?n(right):right});
const and=(left,right)=>({kind:'logic',op:'AND',left,right});
const iff=(condition,then,otherwise=[])=>({kind:'if',condition,then,else:otherwise});
const repeat=(count,body)=>({kind:'repeat',count,body});
const range=direction=>({kind:'range',direction,unit:'m'});
const move=direction=>({kind:'move',direction:direction||'forward',distance_m:.1});
const vertical=direction=>({kind:'vertical',direction,distance_m:.4});
const increment=(name,delta=1)=>set(name,ar('ADD',v(name),delta));
const narrow=cmp('LT',ar('ADD',v('gauche'),v('droite')),.65);
const centered=[iff(cmp('LT',v('gauche'),ar('MINUS',v('droite'),.06)),[move('right')],[iff(cmp('LT',v('droite'),ar('MINUS',v('gauche'),.06)),[move('left')])])];
const reads=[set('avant',range('front')),set('gauche',range('left')),set('droite',range('right'))];
const invalidLow=and(cmp('GT',v('bas'),ar('ADD',v('avant'),.3)),cmp('LT',v('bas'),1.99));
function count(){return iff(cmp('EQ',v('tour'),0),[increment('portes')],[increment('restantes',-1)]);}
function gate(final){return [
  iff(cmp('EQ',v('engagé'),0),[
    ...centered,vertical('down'),set('bas',range('front')),
    iff(invalidLow,[set('engagé',1)],final?[iff(and(and(cmp('GT',v('bas'),.09),cmp('LT',v('bas'),1.99)),and(cmp('LT',v('avant'),1.99),and(cmp('GTE',v('bas'),ar('MINUS',v('avant'),.08)),cmp('LTE',v('bas'),ar('ADD',v('avant'),.08))))),[set('fin',1)],[set('invalide',1)])]:[set('invalide',1)])
  ]),
  iff(and(cmp('EQ',v('engagé'),1),cmp('EQ',v('invalide'),0)),[move()])
];}
function clearance(final){return [vertical('up'),set('arrière',range('back')),
  iff(and(cmp('GT',v('arrière'),.09),cmp('LT',v('arrière'),.65)),final?[increment('portes finales')]:[count()],[set('invalide',1)]),set('engagé',0)];}
const corridor=[iff(and(cmp('GTE',ar('ADD',v('gauche'),v('droite')),.72),cmp('LTE',ar('ADD',v('gauche'),v('droite')),.88)),centered),move()];
const turn=and(cmp('EQ',v('paroi vue'),1),cmp('GT',v('gauche'),.48));
const segment=repeat(20,[iff(and(cmp('EQ',v('virage fait'),0),cmp('EQ',v('invalide'),0)),[
  ...reads,iff(cmp('LT',v('gauche'),.48),[set('paroi vue',1)]),
  iff(narrow,gate(false),[
    iff(cmp('EQ',v('engagé'),1),clearance(false),[
      iff(turn,[{kind:'move',direction:'forward',distance_m:.3},iff(and(cmp('EQ',v('tour'),2),cmp('EQ',v('coin'),3)),[],[{kind:'turn',angle_deg:90}]),set('virage fait',1)],corridor)
    ])
  ])
])]);
const ast={version:1,semantics:'webeeblocks-ast-v1',program:[
  {kind:'takeoff',height_m:.5},{kind:'vertical',direction:'up',distance_m:.3},set('portes',0),set('tour',0),set('coin',0),set('engagé',0),set('invalide',0),set('avant',0),set('gauche',0),set('droite',0),set('bas',0),set('arrière',0),set('restantes',0),set('virage fait',0),set('fin',0),set('portes finales',0),set('paroi vue',0),
  repeat(3,[set('coin',0),set('restantes',v('portes')),repeat(4,[set('virage fait',0),set('paroi vue',0),{kind:'move',direction:'forward',distance_m:.4},segment,iff(cmp('EQ',v('virage fait'),0),[set('invalide',1)]),increment('coin')]),iff(and(cmp('GT',v('tour'),0),cmp('NEQ',v('restantes'),0)),[set('invalide',1)]),increment('tour')]),
  repeat(20,[iff(and(cmp('EQ',v('fin'),0),cmp('EQ',v('invalide'),0)),[...reads,iff(narrow,gate(true),[iff(cmp('EQ',v('engagé'),1),clearance(true),corridor)])])]),
  {kind:'land'}
]};
function build(conditionalLoops){
  const result=JSON.parse(JSON.stringify(ast));
  if(conditionalLoops===true){
    const final=result.program[result.program.length-2];
    result.program[result.program.length-2]={kind:'while',mode:'UNTIL',condition:cmp('EQ',v('fin'),1),body:final.body,max_iterations:20};
  }
  return result;
}
return {ast,build};
});
