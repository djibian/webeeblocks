/* Sensor/variable AST. No seed, position or oracle input. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.WebeeBlocksGrandPrixUWitness=factory();})(typeof self!=='undefined'?self:this,function(){
'use strict';
const n=value=>({kind:'number',value});
const v=name=>({kind:'variable_get',variable:{id:'gpu-'+name,name}});
const set=(name,value)=>({kind:'set_variable',variable:{id:'gpu-'+name,name},value:typeof value==='number'?n(value):value});
const ar=(op,left,right)=>({kind:'arithmetic',op,left,right:typeof right==='number'?n(right):right});
const cmp=(op,left,right)=>({kind:'compare',op,left,right:typeof right==='number'?n(right):right});
const and=(left,right)=>({kind:'logic',op:'AND',left,right});
const iff=(condition,then,otherwise=[])=>({kind:'if',condition,then,else:otherwise});
const range=direction=>({kind:'range',direction,unit:'m'});
const move=(distance,direction='forward')=>({kind:'move',direction,distance_m:distance});
const vertical=direction=>({kind:'vertical',direction,distance_m:.4});
const inc=name=>set(name,ar('ADD',v(name),1));
const reads=[set('avant',range('front')),set('gauche',range('left')),set('droite',range('right'))];
const sum=()=>ar('ADD',v('gauche'),v('droite'));
const center=[iff(cmp('LT',v('gauche'),ar('MINUS',v('droite'),.06)),[move(.1,'right')],[iff(cmp('LT',v('droite'),ar('MINUS',v('gauche'),.06)),[move(.1,'left')])])];
const stride=[iff(cmp('GT',v('avant'),.75),[move(.4)],[iff(cmp('GT',v('avant'),.35),[move(.2)],[move(.1)])])];
function build(){
 const gate=[set('paroi vue',1),...center,vertical('down'),set('bas',range('front')),
  iff(cmp('GTE',v('bas'),1.99),[{kind:'turn',angle_deg:-20},set('bas',range('front')),{kind:'turn',angle_deg:20}]),
  iff(and(cmp('LT',v('bas'),1.99),cmp('GT',v('bas'),ar('ADD',v('avant'),.3))),
    [move(.4),vertical('up'),move(.3),set('arrière',range('back')),
     iff(and(cmp('GT',v('arrière'),.30),cmp('LT',v('arrière'),.85)),[inc('portes')],[set('invalide',1),set('côté terminé',1)])],
    [set('invalide',1),set('côté terminé',1)])];
 const final=[vertical('down'),set('bas',range('front')),
  iff(and(cmp('LT',v('avant'),1.99),and(cmp('GTE',v('bas'),ar('MINUS',v('avant'),.08)),cmp('LTE',v('bas'),ar('ADD',v('avant'),.08)))),
   [move(.1),iff(cmp('EQ',v('portes'),2),[move(.4,'left'),move(.1,'left')]),iff(cmp('EQ',v('portes'),3),[move(.4,'right'),move(.1,'right')])],
   [set('invalide',1)]),set('côté terminé',1)];
 const turnCorner=[{kind:'turn',angle_deg:90},set('droite',range('right')),
  {kind:'while',mode:'UNTIL',condition:cmp('GTE',v('droite'),.44),max_iterations:5,
   body:[move(.1,'left'),set('droite',range('right'))]},set('côté terminé',1)];
 const body=[...reads,
  iff(cmp('LT',sum(),.65),gate,[
   iff(and(cmp('EQ',v('côté'),2),and(cmp('GT',sum(),1.65),cmp('LT',v('avant'),.85))),final,[
    iff(cmp('LT',v('gauche'),.75),[set('paroi vue',1)]),
    iff(and(cmp('LT',v('côté'),2),cmp('LTE',v('avant'),.20)),turnCorner,
      [iff(and(cmp('EQ',v('côté'),2),cmp('GT',sum(),1.65)),[move(.1)],
        [iff(and(cmp('GT',sum(),.9),cmp('LT',sum(),1.1)),center),...stride])])
   ])
  ])];
 return {version:1,semantics:'webeeblocks-ast-v1',program:[
  {kind:'takeoff',height_m:.4},vertical('up'),...['avant','gauche','droite','bas','arrière','côté','portes','paroi vue','côté terminé','invalide'].map(name=>set(name,0)),
  {kind:'repeat',count:3,body:[set('paroi vue',0),set('côté terminé',0),
   {kind:'while',mode:'UNTIL',condition:cmp('EQ',v('côté terminé'),1),max_iterations:60,body:[iff(cmp('EQ',v('invalide'),0),body,[set('côté terminé',1)])]},inc('côté')]},
  {kind:'land'}]};
}
return {build};
});
