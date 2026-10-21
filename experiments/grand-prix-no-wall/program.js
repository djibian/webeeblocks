/* Experimental ordinary Blockly witness for the public 2 m U; no world input. */
'use strict';
const n=value=>({kind:'number',value});
const v=name=>({kind:'variable_get',variable:{id:'gpu-'+name,name}});
const set=(name,value)=>({kind:'set_variable',variable:{id:'gpu-'+name,name},value:typeof value==='number'?n(value):value});
const ar=(op,left,right)=>({kind:'arithmetic',op,left,right:typeof right==='number'?n(right):right});
const cmp=(op,left,right)=>({kind:'compare',op,left,right:typeof right==='number'?n(right):right});
const and=(left,right)=>({kind:'logic',op:'AND',left,right});
const iff=(condition,then,otherwise=[])=>otherwise.length?({kind:'if',condition,then,else:otherwise}):({kind:'if',condition,then});
const range=direction=>({kind:'range',direction,unit:'m'});
const move=(distance,direction='forward')=>({kind:'move',direction,distance_m:distance});
const vertical=direction=>({kind:'vertical',direction,distance_m:.4});
const add=(name,value)=>set(name,ar('ADD',v(name),value));
const advance=distance=>[move(distance),add('avancement',Math.round(distance*10))];
const between=(name,lo,hi)=>and(cmp('GTE',v(name),lo),cmp('LTE',v(name),hi));
const center=[iff(cmp('LT',v('gauche'),ar('MINUS',v('droite'),.06)),[move(.1,'right')],[iff(cmp('LT',v('droite'),ar('MINUS',v('gauche'),.06)),[move(.1,'left')])])];
function build(){
 const refuse=[set('invalide',1),set('terminé',1)];
 const final=[set('avant',range('front')),{kind:'while',mode:'UNTIL',max_iterations:6,
  condition:between('avant',.63,.73),body:[iff(cmp('GT',v('avant'),.73),[move(.1)],[move(.1,'back')]),set('avant',range('front'))]},
  iff(cmp('EQ',v('portes'),2),[move(.4,'left'),move(.1,'left')]),
  iff(cmp('EQ',v('portes'),3),[move(.4,'right'),move(.1,'right')]),set('terminé',1)];
 const passage=[...advance(.2),set('gauche',range('left')),set('droite',range('right')),set('bas',range('front')),
  iff(and(and(cmp('GT',ar('ADD',v('gauche'),v('droite')),.45),cmp('LT',ar('ADD',v('gauche'),v('droite')),.75)),cmp('GT',v('bas'),.6)),
   [...center,...advance(.4),...advance(.2),vertical('up'),set('arrière',range('back')),
    iff(between('arrière',.30,.65),[add('portes',1),set('H passé',1)],refuse)],refuse)];
 const observe=[vertical('down'),set('bas',range('front')),
  iff(cmp('GT',v('bas'),ar('ADD',v('avant'),.3)),passage,
   [iff(and(cmp('EQ',v('côté'),2),and(cmp('GTE',v('bas'),ar('MINUS',v('avant'),.08)),cmp('LTE',v('bas'),ar('ADD',v('avant'),.08)))),final,refuse)])];
 const stride=[iff(cmp('GT',v('avant'),.75),advance(.4),advance(.1))];
 const body=[iff(and(cmp('LT',v('côté'),2),cmp('GTE',v('avancement'),21)),[set('terminé',1)],
  [set('avant',range('front')),
   iff(and(cmp('LTE',v('avant'),.4),and(cmp('GTE',v('avant'),.30),cmp('EQ',v('H passé'),0))),observe,
    [iff(and(cmp('EQ',v('côté'),2),cmp('LTE',v('avant'),.4)),observe,
     [iff(and(cmp('LT',v('côté'),2),cmp('GTE',v('avancement'),17)),advance(.1),stride)])])])];
 return {version:1,semantics:'webeeblocks-ast-v1',program:[
  {kind:'takeoff',height_m:.4},vertical('up'),...['côté','portes','avancement','H passé','terminé','invalide','avant','bas','gauche','droite','arrière'].map(name=>set(name,0)),
  {kind:'repeat',count:3,body:[set('avancement',0),set('H passé',0),set('terminé',0),
   {kind:'while',mode:'UNTIL',condition:cmp('EQ',v('terminé'),1),max_iterations:25,body:[iff(cmp('EQ',v('invalide'),0),body,[set('terminé',1)])]},
   iff(and(cmp('LT',v('côté'),2),cmp('EQ',v('invalide'),0)),[{kind:'turn',angle_deg:90}]),add('côté',1)]},
  {kind:'land'}]};
}
module.exports={build};
