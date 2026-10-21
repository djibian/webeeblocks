'use strict';
const fs=require('fs'),path=require('path'),root=path.resolve(__dirname,'../..');
const Backend=require(path.join(root,'plugins/robot_windows/blockly/webeeblocks/wwi_backend'));
const Interpreter=require(path.join(root,'plugins/robot_windows/blockly/webeeblocks/interpreter'));
const Workspace=require('./negative_workspace');
const port=Number(process.argv[2]),mode=process.argv[3],output=process.argv[4];
function report(event,detail){const item={event,detail};console.log('GP_U_NODE '+JSON.stringify(item));if(output)fs.appendFileSync(output,JSON.stringify(item)+'\n');}
const socket=new WebSocket('ws://127.0.0.1:'+port+'/');
const backend=new Backend({send:m=>{report('request',m);socket.send('robot:Crazyflie WebeeBlocks:'+m);}},{simulationReset:true,simulationStop:true,timeoutMs:35000,outcomeSettleMs:5000});
socket.onmessage=e=>{for(const line of String(e.data).split(/\r?\n/)){if(line.startsWith('robot:')){const data=JSON.parse(line.slice(6));if(data.name==='Crazyflie WebeeBlocks'){report('response',data.message);backend.handleMessage(data.message);}}}};
socket.onopen=async()=>{
 try{
  socket.send('robot:Crazyflie WebeeBlocks:init robot window');await backend.waitUntilReady();
  const program=Workspace.build().ast;report('program',program);
  await Interpreter.run(program,backend,{maxSteps:20000,hooks:{onSensor:c=>report('sensor',{direction:c.direction,value:c.value})}});
  const evaluation={type:'mission-state-v1',oracle:'grand-prix-u-v1'};
  await backend.completeActivityMission(evaluation);report('outcome',await backend.readActivityOutcome(evaluation));
 }catch(error){
  report('error',{message:String(error),code:error.code||null});
  if(mode==='deadline'){
   for(const command of [['COMPLETE','grand-prix-u-v1'],['FAILURE','grand-prix-u-v1'],['MOVE','forward','0.1'],['STOP']]){
    try{await backend._request(command);report('late-command-accepted',{command:command[0]});}
    catch(e){report('late-command-rejected',{command:command[0],code:e.code});}
   }
   try{report('late-outcome-read',{status:await backend._request(['OUTCOME','grand-prix-u-v1'])});}
   catch(e){report('late-outcome-error',{code:e.code});}
  }
 }finally{socket.close();setTimeout(()=>process.exit(0),30);}
};
socket.onerror=e=>{report('transport-error',{message:String(e)});process.exit(1);};
setTimeout(()=>{report('wall-timeout',{});process.exit(1);},600000).unref();
