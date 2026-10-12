(async function(){
 const events=[];
 async function report(event,detail){events.push({event,detail});await fetch('http://127.0.0.1:8765/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event,detail})});}
 let backend;
 try{
  const module=await import('../blockly_v2/webots/RobotWindow.js');
  const robotWindow=new module.default();
  backend=new WebeeBlocksWwiBackend(robotWindow,{simulationReset:true,timeoutMs:35000,outcomeSettleMs:5000});
  robotWindow.receive=m=>backend.handleMessage(String(m));await backend.waitUntilReady();
  await backend._request(['GP_MODE','0']);
  const ranges=[], program=WebeeBlocksGrandPrixWitness.build(true,window.GP_TEST_STRATEGY_LAPS||1);
  await report('GP_PROGRAM',program);
  await WebeeBlocksInterpreter.run(program,backend,{maxSteps:20000,hooks:{onSensor:async c=>ranges.push({direction:c.direction,value:c.value}),onVariables:async c=>{if(c.variable.name==='tour')await report('GP_VARIABLES',c.values);}}});
  const evaluation={type:'mission-state-v1',oracle:'grand-prix-v1'};
  await backend.completeActivityMission(evaluation);
  await report('GP_OUTCOME',await backend.readActivityOutcome(evaluation));
  await report('GP_RANGES',ranges);
 }catch(error){if(backend&&backend.ready){try{await backend.stopSimulation();}catch(stopError){await report('GP_STOP_ERROR',{message:String(stopError)});}}await report('GP_ERROR',{message:String(error),code:error.code||null});}
})();
