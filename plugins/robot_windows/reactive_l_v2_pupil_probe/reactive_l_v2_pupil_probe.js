'use strict';
// Native R2025a A5 Draft witness: one pre-produced genuine .wbb, same bytes
// across all variants, loaded through public Blockly 13 project APIs.
// TEST ONLY: never displayed as lesson solution or accepted for hardware flight.
let pupilA5Events=Promise.resolve();
function pupilA5Report(event,detail) {
 pupilA5Events=pupilA5Events.then(()=>fetch('http://127.0.0.1:8765/event',{
  method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
 }).then(r=>{if(!r.ok)throw Error('A5 event refused: '+event);}));
 return pupilA5Events;
}
function pupilA5Fail(message){throw Error(message);}
async function pupilA5Outcome(backend,profile){
 const deadline=Date.now()+90000;
 while(Date.now()<deadline){
  try{
   const state=await backend.readActivityOutcome(profile.evaluation);
   if(state.status!=='achieved')
    pupilA5Fail('independent A5 C oracle refused actual Blockly flight: '+JSON.stringify(state));
   return state;
  }catch(e){
   if(!e||e.code!=='OUTCOME_UNAVAILABLE')throw e;
   await new Promise(resolve=>setTimeout(resolve,250));
  }
 }
 pupilA5Fail('native A5 outcome unavailable after full Blockly execution');
}
window.addEventListener('error',e=>pupilA5Report('A5_PUPIL_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>pupilA5Report('A5_PUPIL_ERROR',{message:String(e.reason)}));
(async()=>{
 let workspace=null;
 try{
  const b=await window.WB_A5_PUPIL_BOOTSTRAP;
  if(!b||!b.ok)pupilA5Fail('A5 browser bootstrap absent');
  await pupilA5Report('A5_PUPIL_JS_STARTED',{kind:'Blockly13-native-R2025a'});
  const fetched=await fetch('http://127.0.0.1:8765/fixture').then(r=>{
   if(!r.ok)pupilA5Fail('test-only common .wbb unavailable');
   return r.json();
  });
  if(!fetched||!['A','B','C'].includes(fetched.variant)||
     typeof fetched.wbb!=='string'||!/^[0-9a-f]{64}$/.test(fetched.sha256))
   pupilA5Fail('untrusted variant/.wbb identity in local CI fixture');
  const bytes=new TextEncoder().encode(fetched.wbb);
  const rawHash=await crypto.subtle.digest('SHA-256',bytes);
  const hash=Array.from(new Uint8Array(rawHash))
   .map(v=>v.toString(16).padStart(2,'0')).join('');
  if(hash!==fetched.sha256)pupilA5Fail('same .wbb SHA does not match CI fixture');
  const base=WebeeBlocksActivityProfiles.resolveById(
   WebeeBlocksActivities.DOCUMENT,'progression-reactive-L-v2',
   WebeeBlocksActivities.BLOCK_CATALOG);
  if(base.starterVisible!==false||base.evaluation.oracle!=='progression-reactive-L-v2')
   pupilA5Fail('A5 unqualified pupil profile unexpectedly visible or changed');
  const profile=JSON.parse(JSON.stringify(base));
  profile.runtime.scene='reactive-L-'+fetched.variant.toLowerCase()+'-v2';
  if(!WebeeBlocksActivityProfiles.validateProfile(
    profile,WebeeBlocksActivities.BLOCK_CATALOG))pupilA5Fail('variant profile invalid');
  const opts={Blockly,profiles:WebeeBlocksActivityProfiles,
   activitiesDocument:WebeeBlocksActivities.DOCUMENT,
   blockCatalog:WebeeBlocksActivities.BLOCK_CATALOG,
   semanticAst:WebeeBlocksSemanticAst,activityContract:WebeeBlocksActivityContract};
  WebeeBlocksSemanticAst.installConditionalLoopBounds(Blockly);
  const validated=WebeeBlocksProjectFiles.validateProjectText(fetched.wbb,profile,opts);
  workspace=new Blockly.Workspace();
  Blockly.serialization.workspaces.load(validated.project.workspace,workspace);
  WebeeBlocksActivityContract.applyFieldBounds(profile,workspace);
  const ast=WebeeBlocksSemanticAst.compileWorkspace(workspace);
  if(ast.program.filter(s=>s.kind==='while').length!==2||
     ast.program.filter(s=>s.kind==='set_variable').length!==1||
     ast.program.filter(s=>s.kind==='if').length!==1||
     JSON.stringify(ast)!==JSON.stringify(validated.ast))
   pupilA5Fail('real .wbb had wrong reactive loop/variable/branch AST');
  await pupilA5Report('A5_PUPIL_SAME_WBB_REOPENED',{
   sha256:hash,id:profile.id,variant:fetched.variant,
   loops:2,state_assignments:1,branch_count:1});
  const mod=await import('../blockly_v2/webots/RobotWindow.js');
  const bridge=new mod.default();
  const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
   {simulationScenes:true,simulationReset:true,timeoutMs:90000});
  bridge.receive=s=>backend.handleMessage(String(s));
  await backend.waitUntilReady();
  await pupilA5Report('A5_PUPIL_RUNTIME_READY',{variant:fetched.variant});
  // The activity contract itself performs preflight, SCENE/SCENE_OK, then the
  // existing interpreter executes the exact unmodified reopened Blockly AST.
  const executed=await WebeeBlocksActivityContract.execute(
   profile,workspace,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,backend);
  if(JSON.stringify(executed)!==JSON.stringify(ast))
   pupilA5Fail('real interpreter changed reopened pupil AST');
  await pupilA5Report('A5_PUPIL_INTERPRETER_LANDED',{variant:fetched.variant,sha256:hash});
  await backend.completeActivityMission(profile.evaluation);
  await pupilA5Outcome(backend,profile);
  await pupilA5Report('A5_PUPIL_NATIVE_ACHIEVED',{variant:fetched.variant,sha256:hash});
  if(fetched.variant==='A') {
    // A5 CI-only genuine host RESET replay, not merely a new attempt ID.
    // The original Blockly workspace and exact .wbb SHA are not rebuilt.
    await backend.resetSimulation();
    await pupilA5Report('A5_PUPIL_NATIVE_RESET',{variant:'A',same_fixture:true,sha256:hash});
    await backend.prepareActivity(profile);
    try {
      const stale=await backend.readActivityOutcome(profile.evaluation);
      pupilA5Fail('RESET exposed a result before the new attempt: '+JSON.stringify(stale));
    }catch(error) {
      if(!error||error.code!=='OUTCOME_UNAVAILABLE')throw error;
    }
    await pupilA5Report('A5_PUPIL_RESET_CLEAN',{variant:'A',prior_outcome:'unavailable'});
    const rerun=await WebeeBlocksActivityContract.execute(
      profile,workspace,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,backend);
    if(JSON.stringify(rerun)!==JSON.stringify(ast))
      pupilA5Fail('RESET replay changed the original pupil AST');
    await backend.completeActivityMission(profile.evaluation);
    const rerunOutcome=await pupilA5Outcome(backend,profile);
    await pupilA5Report('A5_PUPIL_NATIVE_REPLAY_ACHIEVED',{
      variant:'A',sha256:hash,status:rerunOutcome.status});
  }
  await pupilA5Report('A5_PUPIL_TEST_COMPLETE',{
   variant:fetched.variant,wbb_sha256:hash,same_fixture:true,
   status:'achieved',physical_flight:false});
 }catch(e){
  await pupilA5Report('A5_PUPIL_ERROR',{message:String(e&&(e.stack||e.message)||e)});
 }finally{if(workspace)workspace.dispose();}
})();
