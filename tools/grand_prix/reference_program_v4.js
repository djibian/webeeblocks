/* Sensor-only gp-v4 witness. Public score threshold is policy, not world data. */
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
const move=(distance=.1,direction='forward')=>({kind:'move',direction,distance_m:distance});
const vertical=direction=>({kind:'vertical',direction,distance_m:.4});
const inc=(name,delta=1)=>set(name,ar('ADD',v(name),delta));
const reads=[set('avant',range('front')),set('gauche',range('left')),set('droite',range('right'))];
const narrow=cmp('LT',ar('ADD',v('gauche'),v('droite')),.65);
const center=[iff(cmp('LT',v('gauche'),ar('MINUS',v('droite'),.06)),[move(.1,'right')],[iff(cmp('LT',v('droite'),ar('MINUS',v('gauche'),.06)),[move(.1,'left')])])];
function forward(d,odometry){return [move(d),...(odometry?[inc('avancée',d)]:[])];}
function stride(odometry){return [iff(cmp('GT',v('avant'),.65),forward(.4,odometry),[iff(cmp('GT',v('avant'),.35),forward(.2,odometry),forward(.1,odometry))])];}
function recognition(final){return [
 ...center,vertical('down'),set('bas',range('front')),
 // A central saturation is never an opening certificate. Observe an oblique
 // finite return beyond the opening, directed toward the continuous outer wall.
 iff(cmp('GTE',v('bas'),1.99),[{kind:'turn',angle_deg:-20},set('bas',range('front')),{kind:'turn',angle_deg:20}]),
 iff(and(cmp('LT',v('bas'),1.99),cmp('GT',v('bas'),ar('ADD',v('avant'),.3))),[set('engagé',1)],[
  iff(and(cmp('GT',v('bas'),.09),and(cmp('LT',v('avant'),1.99),and(cmp('GTE',v('bas'),ar('MINUS',v('avant'),.08)),cmp('LTE',v('bas'),ar('ADD',v('avant'),.08))))),
   final?[move(.4,'back'),move(.1,'back'),set('fin',1)]:[set('invalide',1),set('fermé boucle',1)],
   [set('invalide',1)])
 ])
];}
function gate(final){return [iff(cmp('EQ',v('engagé'),0),recognition(final)),iff(and(cmp('EQ',v('engagé'),1),cmp('EQ',v('invalide'),0)),forward(.1,!final))];}
function clear(final){return [vertical('up'),set('arrière',range('back')),iff(and(cmp('GT',v('arrière'),.09),cmp('LT',v('arrière'),.65)),
 final?[inc('portes finales')]:[iff(cmp('EQ',v('tour'),0),[inc('portes')])],[set('invalide',1)]),set('engagé',0)];}
function corridor(final){return [iff({kind:'logic',op:'OR',left:cmp('LT',v('gauche'),.3),right:cmp('LT',v('droite'),.3)},center),...stride(!final)];}
function build(conditionalLoops,laps=1,efficient=true,memoryChoice=false){
 if(!conditionalLoops)throw new Error('gp-v4 requires bounded conditional loops');
 if(!Number.isInteger(laps)||laps<1||laps>2)throw new Error('bounded gp-v4 lap policy');
 const finishCorner=[iff(and(cmp('EQ',v('tour'),0),cmp('EQ',v('coin'),0)),[set('longueur apprise',v('avancée'))]),
  iff(and(cmp('EQ',v('tour'),laps-1),cmp('EQ',v('coin'),3)),[],[{kind:'turn',angle_deg:90}]),set('virage fait',1)];
 const corner=[iff(cmp('EQ',v('coin'),3),[iff(cmp('GTE',v('avancée'),v('longueur apprise')),finishCorner,forward(.1,true))],[iff(cmp('LTE',v('avant'),.50),finishCorner,forward(.1,true))])];
 const segment=repeat(16,[iff(and(cmp('EQ',v('virage fait'),0),cmp('EQ',v('invalide'),0)),[...reads,
  iff(cmp('LT',v('gauche'),.75),[set('paroi vue',1)]),
  iff(narrow,gate(false),[iff(cmp('EQ',v('engagé'),1),clear(false),[
   iff(and(cmp('EQ',v('paroi vue'),1),cmp('GT',v('gauche'),.75)),corner,corridor(false))])])
 ])]);
 const circuit=repeat(laps,[set('coin',0),repeat(4,[iff(cmp('EQ',v('invalide'),0),[set('virage fait',0),set('paroi vue',0),set('avancée',0),...forward(.4,true),segment,iff(cmp('EQ',v('virage fait'),0),[set('invalide',1)]),inc('coin')])]),inc('tour')]);
 const final={kind:'while',mode:'UNTIL',condition:cmp('EQ',v('fin'),1),max_iterations:45,body:[iff(cmp('EQ',v('invalide'),0),[...reads,iff(narrow,gate(true),[iff(cmp('EQ',v('engagé'),1),clear(true),corridor(true))])])]};
 const program=[{kind:'takeoff',height_m:.4},vertical('up'),...['avant','gauche','droite','bas','arrière','portes','portes finales','tour','coin','engagé','fin','invalide','fermé boucle','virage fait','paroi vue','avancée','longueur apprise'].map(name=>set(name,0)),circuit,final,{kind:'land'}];
 return {version:1,semantics:'webeeblocks-ast-v1',program};
}
return {build};
});
