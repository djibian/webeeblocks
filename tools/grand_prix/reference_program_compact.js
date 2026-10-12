/* Compact calibration witness, no seed, geometry or evaluator input.
 * Retains low altitude after an observed open H, raises at a sensed low barrier.
 * Learns commanded side length at the first sensor-recognized corner.
 * Candidate exit policy compares the discovered count; it is not an optimum.
 */
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
const advance=final=>final?[move()]:[iff(and(cmp('GT',v('tour'),0),cmp('GTE',v('avancée'),ar('MINUS',v('longueur apprise'),.25))),[move()],[iff(and(cmp('GT',v('tour'),0),and(cmp('EQ',v('portes'),4),cmp('GT',v('avant'),.65))),[{kind:'move',direction:'forward',distance_m:.4}],[iff(cmp('LT',v('avant'),.35),[move()],[{kind:'move',direction:'forward',distance_m:.2}])])])];
const increment=(name,delta=1)=>set(name,ar('ADD',v(name),delta));
const narrow=cmp('LT',ar('ADD',v('gauche'),v('droite')),.65);
const centered=[iff(cmp('LT',v('gauche'),ar('MINUS',v('droite'),.06)),[move('right')],[iff(cmp('LT',v('droite'),ar('MINUS',v('gauche'),.06)),[move('left')])])];
const reads=[set('avant',range('front')),set('gauche',range('left')),set('droite',range('right'))];
const invalidLow=and(cmp('GT',v('bas'),ar('ADD',v('avant'),.3)),cmp('LT',v('bas'),1.99));
function count(){return iff(cmp('EQ',v('tour'),0),[increment('portes')],[increment('restantes',-1)]);}
function gate(final){return [
  iff(cmp('EQ',v('engagé'),0),[
    ...centered,iff(cmp('EQ',v('bas maintenu'),0),[vertical('down')]),set('bas',range('front')),
    iff(and(cmp('EQ',v('bas maintenu'),1),and(cmp('GT',v('bas'),.35),cmp('LT',v('bas'),1.99))),[set('engagé',1)],[iff(invalidLow,[set('engagé',1)],[iff(and(and(cmp('GT',v('bas'),.09),cmp('LT',v('bas'),1.99)),and(cmp('LT',v('avant'),1.99),and(cmp('GTE',v('bas'),ar('MINUS',v('avant'),.08)),cmp('LTE',v('bas'),ar('ADD',v('avant'),.08))))),final?[set('fin',1)]:[set('fin',1),set('invalide',1)],[set('invalide',1)])])])
  ]),
  iff(and(cmp('EQ',v('engagé'),1),cmp('EQ',v('invalide'),0)),advance(final))
];}
function clearance(final){if(!final)return [count(),set('engagé',0),set('bas maintenu',1)];return [vertical('up'),set('arrière',range('back')),
  iff(and(cmp('GT',v('arrière'),.09),cmp('LT',v('arrière'),.65)),final?[increment('portes finales')]:[count()],[set('invalide',1)]),set('engagé',0)];}
function corridor(final){return [
 iff(and(cmp('EQ',v('bas maintenu'),1),cmp('LT',v('avant'),.4)),[vertical('up'),set('bas maintenu',0)]),
 iff({kind:'logic',op:'OR',left:and(cmp('GTE',ar('ADD',v('gauche'),v('droite')),.72),cmp('LTE',ar('ADD',v('gauche'),v('droite')),.88)),right:{kind:'logic',op:'OR',left:cmp('LT',v('gauche'),.30),right:cmp('LT',v('droite'),.30)}},centered),
 iff(cmp('EQ',v('paroi vue'),0),[move()],advance(final))
];}

const turn=and(cmp('EQ',v('paroi vue'),1),cmp('GT',v('gauche'),.48));
const segment=repeat(10,[iff(and(cmp('EQ',v('virage fait'),0),cmp('EQ',v('invalide'),0)),[
  ...reads,iff(cmp('LT',v('gauche'),.48),[set('paroi vue',1)]),
  iff(narrow,gate(false),[
    iff(cmp('EQ',v('engagé'),1),clearance(false),[
      iff(turn,[iff(cmp('EQ',v('coin'),3),[{kind:'while',mode:'UNTIL',condition:cmp('GTE',v('avancée'),v('longueur apprise')),body:[move(),increment('avancée',.1)],max_iterations:8}],[{kind:'while',mode:'UNTIL',condition:cmp('LTE',v('avant'),.45),body:[move(),set('avant',range('front'))],max_iterations:5}]),iff(and(cmp('EQ',v('tour'),0),cmp('EQ',v('coin'),0)),[set('longueur apprise',v('avancée'))]),iff(and(cmp('EQ',v('tour'),2),cmp('EQ',v('coin'),3)),[],[{kind:'turn',angle_deg:90}]),set('virage fait',1)],corridor(false))
    ])
  ])
])]);
const ast={version:1,semantics:'webeeblocks-ast-v1',program:[
  {kind:'takeoff',height_m:.4},set('bas maintenu',1),set('longueur apprise',0),set('avancée',0),set('portes',0),set('tour',0),set('coin',0),set('engagé',0),set('invalide',0),set('avant',0),set('gauche',0),set('droite',0),set('bas',0),set('arrière',0),set('restantes',0),set('virage fait',0),set('fin',0),set('portes finales',0),set('paroi vue',0),
  repeat(3,[set('coin',0),set('restantes',v('portes')),repeat(4,[iff(cmp('EQ',v('invalide'),0),[set('virage fait',0),set('paroi vue',0),set('avancée',0),{kind:'move',direction:'forward',distance_m:.4},segment,iff(cmp('EQ',v('virage fait'),0),[set('invalide',1)]),increment('coin')])]),iff(and(cmp('GT',v('tour'),0),cmp('NEQ',v('restantes'),0)),[set('invalide',1)]),increment('tour')]),
  iff(and(cmp('EQ',v('bas maintenu'),1),cmp('EQ',v('invalide'),0)),[vertical('up'),set('bas maintenu',0)]),
  repeat(20,[iff(and(cmp('EQ',v('fin'),0),cmp('EQ',v('invalide'),0)),[...reads,iff(narrow,gate(true),[iff(cmp('EQ',v('engagé'),1),clearance(true),corridor(true))])])]),
  {kind:'land'}
]};
function build(conditionalLoops,laps,efficient,memoryChoice){
  const result=JSON.parse(JSON.stringify(ast));
  laps=laps===undefined?3:laps;
  if(!Number.isInteger(laps)||laps<1||laps>7)throw new Error("invalid witness lap strategy");
  const circuit=result.program.find(node=>node.kind==='repeat'&&node.count===3);
  circuit.count=laps;
  function visit(node){
    if(!node||typeof node!=='object')return;
    if(node.kind==='compare'&&node.left&&node.left.kind==='variable_get'&&node.left.variable.name==='tour'&&node.op==='EQ'&&node.right.value===2)node.right.value=laps-1;
    Object.values(node).forEach(child=>Array.isArray(child)?child.forEach(visit):visit(child));
  }
  visit(circuit);
  function odometry(body){for(let i=0;i<body.length;i++){const node=body[i];if(node.kind==='move'&&node.direction==='forward'){body.splice(i+1,0,increment('avancée',node.distance_m));i++;}else{if(node.body)odometry(node.body);if(node.then)odometry(node.then);if(node.else)odometry(node.else);}}}
  // Normalize the learned loop before deriving all odometry from generic moves.
  const learnedLoop=body=>{for(const node of body){if(node.kind==='while'&&node.condition.left&&node.condition.left.kind==='variable_get'&&node.condition.left.variable.name==='avancée')node.body=node.body.slice(0,1);if(node.body)learnedLoop(node.body);if(node.then)learnedLoop(node.then);if(node.else)learnedLoop(node.else);}};
  learnedLoop(circuit.body);odometry(circuit.body);
  if(memoryChoice===true){
    result.program.splice(2,0,set('sortie',0));
    const circuit=result.program.find(n=>n.kind==='repeat');
    function choose(body){for(const node of body){
      const c=node.condition;
      if(node.kind==='if'&&c&&c.kind==='logic'&&c.op==='AND'&&c.left.kind==='compare'&&c.left.left.kind==='variable_get'&&c.left.left.variable.name==='tour'&&c.right.kind==='compare'&&c.right.left.kind==='variable_get'&&c.right.left.variable.name==='coin'){
        node.condition=and(cmp('EQ',v('coin'),3),{kind:'logic',op:'OR',left:cmp('GT',v('tour'),0),right:cmp('LT',v('portes'),4)});node.then=[set('sortie',1)];
      }
      if(node.body)choose(node.body);if(node.then)choose(node.then);if(node.else)choose(node.else);
    }}
    choose(circuit.body);
    result.program[result.program.indexOf(circuit)]={kind:'while',mode:'UNTIL',condition:cmp('EQ',v('sortie'),1),body:circuit.body,max_iterations:2};
  }
  if(conditionalLoops===true){
    const final=result.program[result.program.length-2];
    result.program[result.program.length-2]={kind:'while',mode:'UNTIL',condition:cmp('EQ',v('fin'),1),body:final.body,max_iterations:20};
  }
  return result;
}
return {ast,build};
});
