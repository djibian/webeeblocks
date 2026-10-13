'use strict';
const fs=require('fs');
const Backend=require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const Witness=require('../grand_prix/reference_program_u.js');
const port=Number(process.argv[2]),mode=process.argv[3]||'witness',output=process.argv[4];
function report(event,detail){const item={event,detail};console.log('GP_U_NODE '+JSON.stringify(item));if(output)fs.appendFileSync(output,JSON.stringify(item)+'\n');}
const socket=new WebSocket('ws://127.0.0.1:'+port+'/');
const backend=new Backend({send:m=>{report('request',m);socket.send('robot:Crazyflie WebeeBlocks:'+m);}},{simulationReset:true,simulationStop:true,timeoutMs:35000,outcomeSettleMs:5000});
socket.onmessage=e=>{
 for(const line of String(e.data).split(/\r?\n/)){
  if(line.startsWith('robot:')){
   const data=JSON.parse(line.slice(6));
   if(data.name==='Crazyflie WebeeBlocks'){report('response',data.message);backend.handleMessage(data.message);}
  }
 }
};
socket.onopen=async()=>{
 try{
  socket.send('robot:Crazyflie WebeeBlocks:init robot window');
  await backend.waitUntilReady();
  let program=Witness.build();
  if(mode==='timeout'||mode==='timeout-gate')program={version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.4},{kind:'vertical',direction:'up',distance_m:.4},
   ...(mode==='timeout-gate'?[{kind:'move',direction:'forward',distance_m:.4},{kind:'move',direction:'forward',distance_m:.2},{kind:'vertical',direction:'down',distance_m:.4},{kind:'move',direction:'forward',distance_m:.3}]:[]),
   {kind:'repeat',count:10,body:[{kind:'repeat',count:10,body:[{kind:'wait',seconds:3}]}]},{kind:'land'}]};
  if(mode==='short')program={version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.4},{kind:'vertical',direction:'up',distance_m:.4},{kind:'wait',seconds:1},{kind:'land'}]};
  if(mode==='low-outside')program={version:1,semantics:'webeeblocks-ast-v1',program:[{kind:'takeoff',height_m:.4},{kind:'vertical',direction:'up',distance_m:.4},{kind:'move',direction:'forward',distance_m:.3},{kind:'vertical',direction:'down',distance_m:.4},{kind:'land'}]};
  if(mode==='wrong-landing'){
   const alter=o=>{if(Array.isArray(o))o.forEach(alter);else if(o&&typeof o==='object'){
    if(o.kind==='compare'&&o.op==='EQ'&&o.left.kind==='variable_get'&&o.left.variable.name==='portes'&&o.right.kind==='number')o.right.value=999;
    Object.values(o).forEach(alter);
   }};alter(program);
  }
  report('program',program);
  await Interpreter.run(program,backend,{maxSteps:20000,hooks:{onSensor:c=>report('sensor',{direction:c.direction,value:c.value}),onVariables:c=>{if(c.variable.name==='portes')report('count',c.values);}}});
  const evaluation={type:'mission-state-v1',oracle:'grand-prix-u-v1'};
  await backend.completeActivityMission(evaluation);
  report('outcome',await backend.readActivityOutcome(evaluation));
 }catch(error){report('error',{message:String(error),code:error.code||null});
  if(mode.startsWith('timeout')){
   try{await backend._request(['STOP']);report('late-stop-accepted',{});}catch(e){report('late-stop-rejected',{code:e.code});}
   try{await backend._request(['OUTCOME','grand-prix-u-v1']);report('late-outcome-read',{});}catch(e){report('late-outcome-error',{code:e.code});}
  }
 }finally{socket.close();setTimeout(()=>process.exit(0),30);}
};
socket.onerror=e=>{report('transport-error',{message:String(e)});process.exit(1);};
setTimeout(()=>{report('wall-timeout',{});process.exit(1);},300000).unref();
