'use strict';
// Ideal kinematics for falsification only. Never a native/physical timing oracle.
const Demo=require('../blockly/compact_u_demo');
const I=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
async function run(layout,{scale=1,yawError=0}={}){
 const r=Demo.build();let p=[0,0,.015],yaw=0,tick=0,completed=false,commands=0;
 const trace=[];
 function sample(velocity=[0,0,0]){trace.push({time:++tick*.032,position:p.slice(),velocity,completed});}
 async function motion(target,speed=.35){
  const start=p.slice(),distance=Math.hypot(...target.map((x,i)=>x-start[i]));
  const steps=Math.max(1,Math.ceil(distance/speed/.032));
  const velocity=target.map((x,i)=>(x-start[i])/(steps*.032));
  for(let i=1;i<=steps;i++){p=target.map((x,j)=>start[j]+(x-start[j])*i/steps);sample(velocity);}
  for(let i=0;i<16;i++)sample();commands++;
 }
 const backend={capabilities:{conditionalLoops:true,guardedMove:true,actions:['takeoff','vertical','move','turn','land'],rangeDirections:['front'],moveDirections:['forward','back','left','right']},getMotionEpoch:()=> 'ideal-1',
  async takeoff(height){await motion([0,0,.015+height],.2);},
  async vertical(direction,distance){await motion([p[0],p[1],p[2]+(direction==='up'?distance:-distance)],.2);},
  async move(direction,distance){const angle=yaw+({forward:0,back:Math.PI,left:Math.PI/2,right:-Math.PI/2})[direction];await motion([p[0]+distance*scale*Math.cos(angle),p[1]+distance*scale*Math.sin(angle),p[2]]);return null;},
  async turn(degrees){yaw+=(degrees+yawError)*Math.PI/180;for(let i=0;i<80;i++)sample();commands++;},
  async readRange(){
   const origin=[p[0],p[1],p[2]+.01],ray=[Math.cos(yaw),Math.sin(yaw),0];let result=2;
   for(const box of [...layout.walls,...layout.gate_boxes]){
    let lo=0,hi=Infinity;
    for(let i=0;i<3;i++){const c=box[['x','y','z'][i]],half=box[['sx','sy','sz'][i]]/2;
     if(Math.abs(ray[i])<1e-10){if(origin[i]<c-half||origin[i]>c+half){hi=-1;break;}}
     else{const a=(c-half-origin[i])/ray[i],b=(c+half-origin[i])/ray[i];lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));}
    }if(hi>=lo)result=Math.min(result,lo);
   }sample();return result;
  },
  async land(){await motion([p[0],p[1],.015],.2);completed=true;for(let i=0;i<64;i++)sample();}
 };
 let result,error=null;try{result=await I.run(r.ast,backend,{maxSteps:20000});}catch(e){error={message:e.message,code:e.code};}
 r.workspace.dispose();return{seed:layout.seed,scale,yawError,variables:result?.variables,error,commands,trace};
}
module.exports={run};
if(require.main===module){const cases=JSON.parse(require('fs').readFileSync(0,'utf8'));(async()=>{for(const c of cases)console.log(JSON.stringify(await run(c.layout,c.options)));})().catch(e=>{console.error(e);process.exitCode=1;});}
