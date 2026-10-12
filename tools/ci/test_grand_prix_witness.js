'use strict';
const fs=require('fs');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const witnessModule=require('../grand_prix/reference_program');
const layout=JSON.parse(fs.readFileSync(0,'utf8'));
const witness=witnessModule.build(layout.useConditionalLoops!==false,layout.strategyLaps,layout.efficient);
const straight=[...Array(3).fill({kind:'move',direction:'forward',distance_m:.4}),{kind:'move',direction:'forward',distance_m:.2}];
const lap={kind:'repeat',count:4,body:[...straight,{kind:'turn',angle_deg:90}]};
const blind={version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.9},{kind:'vertical',direction:'down',distance_m:.5},{kind:'repeat',count:2,body:[lap]},{kind:'repeat',count:3,body:[...straight,{kind:'turn',angle_deg:90}]},...straight,...Array(3).fill({kind:'move',direction:'forward',distance_m:.3}),{kind:'land'}]};
const ast=JSON.parse(JSON.stringify(layout.blind?blind:witness));
// Test-authored ablation: the programme still senses/steers, but never learns
// the number of H. It receives no configuration information.
if(layout.forgetCounts){
 const visit=value=>{if(!value||typeof value!=='object')return;
  if(value.kind==='set_variable'&&['portes','restantes'].includes(value.variable.name))value.value={kind:'number',value:0};
  Object.values(value).forEach(child=>{if(Array.isArray(child))child.forEach(visit);else visit(child);});
 };visit(ast);
}
let p=[0,0,.015],heading=0,time=0,ticks=0,lands=0;
const trace=[],ranges=[],variables=[];
function ray(direction){
 const angle=heading+({front:0,back:Math.PI,left:Math.PI/2,right:-Math.PI/2}[direction]);
 const d=[Math.cos(angle),Math.sin(angle),0],origin=[p[0],p[1],p[2]+.01];let result=Infinity;
 for(const b of layout.boxes){let lo=0,hi=Infinity;
  for(let axis=0;axis<3;axis++){
   const center=[b.x,b.y,b.z][axis],size=[b.sx,b.sy,b.sz][axis];
   if(Math.abs(d[axis])<1e-8){if(origin[axis]<center-size/2||origin[axis]>center+size/2){hi=-1;break;}}
   else{const a=(center-size/2-origin[axis])/d[axis],c=(center+size/2-origin[axis])/d[axis];lo=Math.max(lo,Math.min(a,c));hi=Math.min(hi,Math.max(a,c));}
  }if(hi>=lo)result=Math.min(result,lo);
 }return Math.min(2,result);
}
function sample(velocity=[0,0,0]){ticks+=1;time=ticks*32/1000;trace.push({time,position:p.slice(),velocity});}
async function motion(target){const delta=target.map((v,i)=>v-p[i]);const distance=Math.hypot(...delta),steps=Math.max(1,Math.ceil(distance/.0064));const velocity=delta.map(v=>v/(steps*.032));for(let i=0;i<steps;i++){p=p.map((v,a)=>v+delta[a]/steps);sample(velocity);}sample();}
const backend={
 capabilities:{conditionalLoops:layout.useConditionalLoops!==false,actions:['takeoff','move','turn','vertical','land'],rangeDirections:['front','back','left','right'],moveDirections:['forward','back','left','right'],verticalDirections:['up','down']},
 async takeoff(h){await motion([p[0],p[1],.015+h]);},
 async land(){lands++;await motion([p[0],p[1],.015]);},
 async move(direction,distance){const a=heading+({forward:0,back:Math.PI,left:Math.PI/2,right:-Math.PI/2}[direction]);await motion([p[0]+distance*Math.cos(a),p[1]+distance*Math.sin(a),p[2]]);},
 async vertical(direction,distance){await motion([p[0],p[1],p[2]+(direction==='up'?distance:-distance)]);},
 async turn(angle){heading+=angle*Math.PI/180;sample();},
 async readRange(direction){const value=layout.injectRangeLossBoth&&direction==='front'&&p[1]<-.1?2:(layout.injectRangeLoss&&direction==='front'&&p[2]<.5?2:ray(direction));ranges.push({direction,value,time});sample();return value;}
};
(async()=>{
 Interpreter.validateExecutionBudget(ast,20000);
 const result=await Interpreter.run(ast,backend,{maxSteps:20000,hooks:{onVariables:async c=>variables.push({position:p.slice(),values:c.values})}});
 for(let i=0;i<32;i++)sample();
 process.stdout.write(JSON.stringify({result,trace,ranges,variables,lands}));
})().catch(e=>{console.error('WITNESS_FAILURE '+JSON.stringify({message:e.message,lands,last_position:p}));process.exitCode=1;});
