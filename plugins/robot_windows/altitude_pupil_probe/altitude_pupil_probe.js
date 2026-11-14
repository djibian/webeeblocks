'use strict';
// CI-only real Blockly 13 → serialized .wbb → AST/preflight → interpreter
// → WWI → native Crazyflie classroom controller and independent C evaluator.
// No product file broker or Windows GUI is claimed by the in-memory roundtrip.
let pupilReportChain=Promise.resolve();
function pupilReport(event,detail){
  pupilReportChain=pupilReportChain.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw new Error('event observer rejected '+event);}));
  return pupilReportChain;
}
function pupilFail(message){throw new Error(message);}
function pupilNumber(block,input,n){
  const child=block.workspace.newBlock('math_number');
  child.setFieldValue(String(n),'NUM');
  block.getInput(input).connection.connect(child.outputConnection);
}
function pupilBuild(){
  const profile=WebeeBlocksActivityProfiles.resolveById(
    WebeeBlocksActivities.DOCUMENT,'progression-altitude-v1',
    WebeeBlocksActivities.BLOCK_CATALOG);
  if(profile.runtime.scene!=='altitude-v1' ||
      profile.evaluation.oracle!=='progression-altitude-3d-v1')pupilFail('wrong school profile');
  const workspace=new Blockly.Workspace();
  const takeoff=workspace.newBlock('webeeblocks_v2_takeoff');
  const speed=workspace.newBlock('webeeblocks_v2_speed');
  const forward1=workspace.newBlock('webeeblocks_v2_move');
  const up=workspace.newBlock('webeeblocks_v2_vertical');
  const forward2=workspace.newBlock('webeeblocks_v2_move');
  const land=workspace.newBlock('webeeblocks_v2_land');
  const blocks=[takeoff,speed,forward1,up,forward2,land];
  pupilNumber(takeoff,'HEIGHT',0.45);
  forward1.setFieldValue('forward','DIRECTION');
  pupilNumber(forward1,'DISTANCE',0.32);
  up.setFieldValue('up','DIRECTION');
  pupilNumber(up,'DISTANCE',0.36);
  forward2.setFieldValue('forward','DIRECTION');
  pupilNumber(forward2,'DISTANCE',1.03);
  for(let i=0;i<blocks.length-1;i++)
    blocks[i].nextConnection.connect(blocks[i+1].previousConnection);
  WebeeBlocksActivityContract.applyFieldBounds(profile,workspace);
  speed.setFieldValue('0.14','SPEED');
  if(Number(speed.getFieldValue('SPEED'))!==0.14)pupilFail('speed precision rounded');
  return {profile,workspace};
}
async function pupilOutcome(backend){
  const until=Date.now()+80000;
  while(Date.now()<until){
    try{
      const state=await backend.readActivityOutcome({
        type:'mission-state-v1',oracle:'progression-altitude-3d-v1'
      });
      if(state.status!=='achieved')pupilFail('native mission refused: '+JSON.stringify(state));
      return state;
    }catch(e){
      if(!e||e.code!=='OUTCOME_UNAVAILABLE')throw e;
      await new Promise(r=>setTimeout(r,200));
    }
  }
  pupilFail('no native Activity 2 outcome');
}
window.addEventListener('error',e=>pupilReport('PUPIL_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>pupilReport('PUPIL_ERROR',{message:String(e.reason)}));
(async()=>{
  let source=null,reopened=null;
  try{
    await pupilReport('PUPIL_JS_STARTED',{kind:'Blockly13-native-R2025a'});
    const p=pupilBuild();source=p.workspace;
    const opts={
      Blockly,profiles:WebeeBlocksActivityProfiles,
      activitiesDocument:WebeeBlocksActivities.DOCUMENT,
      blockCatalog:WebeeBlocksActivities.BLOCK_CATALOG,
      semanticAst:WebeeBlocksSemanticAst,
      activityContract:WebeeBlocksActivityContract
    };
    const original=WebeeBlocksSemanticAst.compileWorkspace(source);
    WebeeBlocksActivityContract.preflightAst(p.profile,original);
    const text=WebeeBlocksProjectFiles.encodeProject(p.profile,source,opts);
    const validated=WebeeBlocksProjectFiles.validateProjectText(text,p.profile,opts);
    reopened=new Blockly.Workspace();
    Blockly.serialization.workspaces.load(validated.project.workspace,reopened);
    const actual=WebeeBlocksSemanticAst.compileWorkspace(reopened);
    if(JSON.stringify(original)!==JSON.stringify(actual) ||
       validated.project.activity.id!==p.profile.id ||
       actual.program.length!==6)pupilFail('pupil project roundtrip or program malformed');
    await pupilReport('PUPIL_BLOCKLY_PROJECT_ROUNDTRIP',{activity:validated.project.activity.id,statements:actual.program.length,program:actual.program});

    const module=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new module.default();
    const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000});
    bridge.receive=s=>backend.handleMessage(String(s));
    await backend.waitUntilReady();
    await pupilReport('PUPIL_RUNTIME_READY',{native:true});
    const executed=await WebeeBlocksActivityContract.execute(
      p.profile,reopened,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,backend);
    if(JSON.stringify(executed)!==JSON.stringify(actual))
      pupilFail('executed AST not equal to saved Blockly AST');
    await pupilReport('PUPIL_INTERPRETER_LANDED',{statements:executed.program.length});
    // The evaluator must receive terminal completion after the real LAND ACK.
    await backend.completeActivityMission(p.profile.evaluation);
    await pupilOutcome(backend);
    await pupilReport('PUPIL_NATIVE_ACHIEVED',{status:'achieved'});
    await pupilReport('PUPIL_TEST_COMPLETE',{profile:p.profile.id,mission:'achieved'});
  }catch(e){
    await pupilReport('PUPIL_ERROR',{message:String(e&&e.stack||e)});
  }finally{
    if(source)source.dispose();
    if(reopened)reopened.dispose();
  }
})();
