/* Real Webots WWI: readiness, admission, native takeoff, LAND, RESET,
 * and second attempt with a deliberately invalid low-altitude traversal.
 * No GUI/browser timing or mission success is inferred from this probe. */
'use strict';
const fs=require('fs'),path=require('path');
const root=path.resolve(process.argv[4]);
const backendClass=require(path.join(root,'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));
const port=Number(process.argv[2]), events=process.argv[3];
if (!Number.isSafeInteger(port)||!events) throw new Error('Usage: node probe PORT events.jsonl extracted-root');
const out=(event,data)=>fs.appendFileSync(events,JSON.stringify({event,data,time:new Date().toISOString()})+'\n');
const socket=new WebSocket('ws://127.0.0.1:'+port+'/');
const backend=new backendClass({send:payload=>socket.send('robot:Crazyflie WebeeBlocks:'+payload)},{
  simulationReset:true,simulationStop:true,simulationAdmission:true,timeoutMs:60000,outcomeSettleMs:60000
});
let ended=false;
const finish=(status)=>{if(ended)return;ended=true;try{socket.close()}catch{} setTimeout(()=>process.exit(status),80);};
socket.onmessage=e=>{
 for(const line of String(e.data).split(/\r?\n/)) {
  if(!line.startsWith('robot:')) continue;
  let info;
  try{info=JSON.parse(line.slice(6));}catch{continue;}
  if(info.name==='Crazyflie WebeeBlocks') {
   out('native-message',info.message);
   backend.handleMessage(info.message);
  }
 }
};
socket.onerror=e=>{out('transport-error',String(e));finish(1)};
socket.onopen=async()=>{
 try{
  socket.send('robot:Crazyflie WebeeBlocks:init robot window');
  await backend.waitUntilReady();out('runtime-ready',true);
  // Only real native flight can satisfy the route admission handshake.
  await backend.takeoff(.4);out('first-takeoff',true);
  // Land independently; the mission need not be achieved at the start.
  await backend.land();out('first-land',true);
  await backend.resetSimulation();out('reset-complete',true);
  await backend.waitUntilReady();out('second-ready',true);
  await backend.takeoff(.4);out('second-takeoff',true);
  // Deliberately fly too low outside an H band: a native fail is expected.
  let nativeRefusal=null;
  try {
    await backend.move('forward',1.5);
    out('dynamic-move-completed',true);
  } catch(error) {
    out('dynamic-command-error',{code:error.code||null,message:String(error)});
  }
  const evaluation={type:'mission-state-v1',oracle:'grand-prix-route-v2'};
  const reasons=['envelope-contact','course-boundary','altitude','low-outside-zone',
                 'wrong-landing','time-limit'];
  // The genuine native evaluator has already terminally classified the
  // deliberate bad traversal. Never issue FAILURE here: once the pilot
  // safety-lands, it must reject new mutating commands with TIME_LIMIT.
  // OUTCOME is expressly permitted after that revocation, read-only and
  // exact-attempt-bound. Poll only for the independent *reasoned* verdict.
  const deadline=Date.now()+10000;
  let lastOutcome=null;
  while(Date.now()<deadline&&!nativeRefusal) {
    try {
      const state=await backend.readActivityOutcome(evaluation);
      lastOutcome=state;
      if(state&&state.status==='not-achieved'&&reasons.includes(state.reason)) {
        nativeRefusal=state.reason;
        out('dynamic-outcome',state);
        break;
      }
      if(state&&state.status!=='not-achieved')
        throw new Error('Unexpected terminal mission outcome: '+JSON.stringify(state));
    } catch(error) {
      if(!(error&&error.code==='OUTCOME_UNAVAILABLE'))
        throw error;
      lastOutcome={error:'OUTCOME_UNAVAILABLE'};
    }
    await new Promise(resolve=>setTimeout(resolve,50));
  }
  if(!nativeRefusal)
    out('dynamic-outcome-unproven',lastOutcome);
  // A timeout, generic failure, transport rejection, or success cannot
  // establish the real native dynamic oracle. Require a concrete reason.
  if(!nativeRefusal)
    throw new Error('Real native route dynamic oracle refusal not established');
  out('dynamic-refusal-confirmed',nativeRefusal);
  out('native-sequence-completed',true);
  finish(0);
 }catch(error){out('error',{code:error.code||null,message:String(error)});finish(1);}
};
setTimeout(()=>{out('wall-timeout',true);finish(1)},500000).unref();
