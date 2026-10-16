'use strict';
const fs=require('fs');
const Backend=require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter.js');
const WorkspaceWitness=require('../grand_prix/witness_workspace_u.js');
const Witness={build:()=>WorkspaceWitness.build().ast};
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
  if(mode==='collision')program={version:1,semantics:'webeeblocks-ast-v1',program:[
   {kind:'takeoff',height_m:.4},{kind:'vertical',direction:'up',distance_m:.4},
   {kind:'move',direction:'forward',distance_m:.4},{kind:'move',direction:'forward',distance_m:.4},{kind:'land'}]};
  if(mode==='reverse')program={version:1,semantics:'webeeblocks-ast-v1',program:[
   {kind:'takeoff',height_m:.4},{kind:'vertical',direction:'up',distance_m:.4},
   {kind:'move',direction:'forward',distance_m:.4},{kind:'move',direction:'forward',distance_m:.2},
   {kind:'vertical',direction:'down',distance_m:.4},{kind:'move',direction:'forward',distance_m:.4},
   {kind:'move',direction:'forward',distance_m:.35},{kind:'move',direction:'back',distance_m:.4},
   {kind:'move',direction:'back',distance_m:.3},{kind:'land'}]};
  if(mode==='unavailable'){
   const read=backend.readRange.bind(backend);let injected=false;
   backend.readRange=async direction=>{const actual=await read(direction);
    if(!injected){injected=true;report('injected-range',{direction,actual,value:null});return NaN;}
    return actual;
   };
  }
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
  if(mode==='reset'){
   await backend.resetSimulation();report('reset-completed',{});
   await Interpreter.run(program,backend,{maxSteps:20000});
   await backend.completeActivityMission(evaluation);
   report('second-outcome',await backend.readActivityOutcome(evaluation));
  }
 }catch(error){report('error',{message:String(error),code:error.code||null});
  if(mode==='unavailable'){
   await backend._request(['STOP']);
   await backend.probeActivityMissionFailure({type:'mission-state-v1',oracle:'grand-prix-u-v1'});
   report('outcome',await backend.readActivityOutcome({type:'mission-state-v1',oracle:'grand-prix-u-v1'}));
  }
  if(mode.startsWith('timeout')){
   // Observe the expired attempt BEFORE trying its separately permitted recovery.
   // RESET after confirmed native landing creates a new attempt; putting it in
   // this loop made the later MOVE/STOP/OUTCOME assertions depend on wall timing.
   for(const command of [['COMPLETE','grand-prix-u-v1'],['FAILURE','grand-prix-u-v1'],['MOVE','forward','0.1']]){
    try{await backend._request(command);report('late-command-accepted',{command:command[0]});}
    catch(e){report('late-command-rejected',{command:command[0],code:e.code});}
   }
   try{await backend._request(['STOP']);report('late-stop-accepted',{});}catch(e){report('late-stop-rejected',{code:e.code});}
   try{const status=await backend._request(['OUTCOME','grand-prix-u-v1']);report('late-outcome-read',{status});}catch(e){report('late-outcome-error',{code:e.code});}
   try{
    await backend.resetSimulation();report('recovery-reset-accepted',{});
    try{const status=await backend._request(['OUTCOME','grand-prix-u-v1']);report('recovery-stale-outcome',{status});}
    catch(e){report('recovery-outcome-error',{code:e.code});}
   }catch(e){report('recovery-reset-rejected',{code:e.code});}
  }
 }finally{socket.close();setTimeout(()=>process.exit(0),30);}
};
socket.onerror=e=>{report('transport-error',{message:String(e)});process.exit(1);};
setTimeout(()=>{report('wall-timeout',{});process.exit(1);},600000).unref();
