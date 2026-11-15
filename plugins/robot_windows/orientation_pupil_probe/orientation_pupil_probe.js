'use strict';
// Activity 3 R2025a native pupil-catalog integration witness (CI only).
// Real Blockly 13 -> exact .wbb serialization -> preflight -> interpreter ->
// WWI -> original native school flight -> independent Webots C orientation oracle.
let a3ReportChain=Promise.resolve();
function a3Report(event,detail){
  a3ReportChain=a3ReportChain.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw new Error('A3 event observer rejected '+event);}));
  return a3ReportChain;
}
function a3Fail(message){throw new Error(message);}
function a3MotionNumber(block,input,value){
  const number=block.workspace.newBlock('math_number');
  number.setFieldValue(String(value),'NUM');
  const parent=block.getInput(input);
  if(!parent||!parent.connection)a3Fail('missing Blockly motion socket '+input);
  parent.connection.connect(number.outputConnection);
  number.setShadow(true);
  if(!number.isShadow())a3Fail('numeric movement literal is not a shadow');
}
function a3BuildProfile(){
  // Exercise the exact published pupil profile and complete catalog.
  // This probe remains a CI runner and is never an algorithm supplied to pupils.
  return WebeeBlocksActivityProfiles.resolveById(
    WebeeBlocksActivities.DOCUMENT,
    'progression-orientation-3d-v1',
    WebeeBlocksActivities.BLOCK_CATALOG);
}
function a3BuildWorkspace(profile){
  const ws=new Blockly.Workspace();
  function block(type){return ws.newBlock(type);}
  function move(m){const b=block('webeeblocks_v2_move');b.setFieldValue('forward','DIRECTION');a3MotionNumber(b,'DISTANCE',m);return b;}
  function vertical(dir,m){const b=block('webeeblocks_v2_vertical');b.setFieldValue(dir,'DIRECTION');a3MotionNumber(b,'DISTANCE',m);return b;}
  function turn(dir){const b=block('webeeblocks_v2_turn');b.setFieldValue(dir,'DIRECTION');b.setFieldValue('90','ANGLE');return b;}
  const takeoff=block('webeeblocks_v2_takeoff');a3MotionNumber(takeoff,'HEIGHT',0.63);
  const speed=block('webeeblocks_v2_speed');
  // A genuine six-command recurrent geometric motif: first traversal
  // reaches A/B, second traversal reaches C and the pad. This is not a
  // cosmetic repeat of two halves of a single forward instruction.
  const repeat=block('controls_repeat_ext');
  const count=block('math_number');count.setFieldValue('2','NUM');
  repeat.getInput('TIMES').connection.connect(count.outputConnection);
  const motif=[
    move(0.45),turn('right'),vertical('up',0.16),move(0.45),
    turn('left'),vertical('down',0.16)
  ];
  repeat.getInput('DO').connection.connect(motif[0].previousConnection);
  for(let i=0;i<motif.length-1;i++)
    motif[i].nextConnection.connect(motif[i+1].previousConnection);
  const statements=[takeoff,speed,repeat,block('webeeblocks_v2_land')];
  for(let i=0;i<statements.length-1;i++)
    statements[i].nextConnection.connect(statements[i+1].previousConnection);
  WebeeBlocksActivityContract.applyFieldBounds(profile,ws);
  // Blockly's generic speed field loads at 0.1 precision. Use an exact
  // representable value, rather than silently losing 0.12 during .wbb Open.
  speed.setFieldValue('0.10','SPEED');
  if(Number(speed.getFieldValue('SPEED'))!==0.10)
    a3Fail('speed 0.10 rounded away from valid profile value');
  return ws;
}
async function a3Outcome(backend){
  const end=Date.now()+80000;
  while(Date.now()<end){
    try{
      const state=await backend.readActivityOutcome({
        type:'mission-state-v1',oracle:'progression-orientation-3d-v1'});
      if(state.status!=='achieved')a3Fail('C orientation oracle rejected: '+JSON.stringify(state));
      return state;
    }catch(e){
      if(!e||e.code!=='OUTCOME_UNAVAILABLE')throw e;
      await new Promise(r=>setTimeout(r,200));
    }
  }
  a3Fail('native orientation outcome never arrived');
}
window.addEventListener('error',e=>a3Report('A3_PUPIL_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>a3Report('A3_PUPIL_ERROR',{message:String(e.reason)}));
(async()=>{
  let source=null,reopened=null;
  try{
    if(!window.WB_ORIENT_PUPIL_BOOTSTRAP)a3Fail('missing HTML bootstrap');
    const boot=await window.WB_ORIENT_PUPIL_BOOTSTRAP;
    if(!boot||!boot.ok)a3Fail('HTML observer denied bootstrap');
    await a3Report('A3_PUPIL_JS_STARTED',{kind:'Blockly13-native-R2025a'});
    const profile=a3BuildProfile();
    const doc=WebeeBlocksActivities.DOCUMENT; // exact public pupil catalogue
    source=a3BuildWorkspace(profile);
    const opts={
      Blockly,profiles:WebeeBlocksActivityProfiles,
      activitiesDocument:doc,blockCatalog:WebeeBlocksActivities.BLOCK_CATALOG,
      semanticAst:WebeeBlocksSemanticAst,activityContract:WebeeBlocksActivityContract
    };
    const original=WebeeBlocksSemanticAst.compileWorkspace(source);
    WebeeBlocksActivityContract.preflightAst(profile,original);
    if(original.program.length!==4||original.program[2].kind!=='repeat'||
       original.program[2].count!==2||original.program[2].body.length!==6)
      a3Fail('six-command recurring motif did not compile as repeat(2)');
    if(JSON.stringify(original.program[2].body.map(s=>s.kind))!==
        JSON.stringify(['move','turn','vertical','move','turn','vertical']))
      a3Fail('loop body does not preserve actual 3D trajectory pattern');
    const text=WebeeBlocksProjectFiles.encodeProject(profile,source,opts);
    const parsed=WebeeBlocksProjectFiles.validateProjectText(text,profile,opts);
    reopened=new Blockly.Workspace();
    // Replay the project's real, public Blockly serialization API. The
    // project validator has already loaded and preflighted these exact bytes
    // into a temporary workspace. No private file-manager helper exists.
    Blockly.serialization.workspaces.load(parsed.project.workspace,reopened);
    WebeeBlocksActivityContract.applyFieldBounds(profile,reopened);
    WebeeBlocksActivityContract.preflightWorkspace(profile,reopened);
    const actual=WebeeBlocksSemanticAst.compileWorkspace(reopened);
    if(JSON.stringify(original)!==JSON.stringify(actual)||
       parsed.project.activity.id!==profile.id)
      a3Fail('Activity 3 .wbb roundtrip changed semantic AST: before='+
        JSON.stringify(original.program).slice(0,900)+' after='+
        JSON.stringify(actual.program).slice(0,900));
    await a3Report('A3_PUPIL_BLOCKLY_ROUNDTRIP',{
      id:profile.id,statements:actual.program.length,
      repeat:actual.program[2],bytes:text.length
    });
    const module=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new module.default();
    const backend=new WebeeBlocksWwiBackend({send:s=>bridge.send(s)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000});
    bridge.receive=s=>backend.handleMessage(String(s));
    await backend.waitUntilReady();
    await a3Report('A3_PUPIL_RUNTIME_READY',{native:true});
    const executed=await WebeeBlocksActivityContract.execute(
      profile,reopened,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,backend);
    if(JSON.stringify(executed)!==JSON.stringify(actual))
      a3Fail('Interpreter did not execute the reopened Blockly AST');
    await a3Report('A3_PUPIL_INTERPRETER_LANDED',{statements:executed.program.length});
    await backend.completeActivityMission(profile.evaluation);
    await a3Outcome(backend);
    await a3Report('A3_PUPIL_NATIVE_ACHIEVED',{status:'achieved'});
    await a3Report('A3_PUPIL_TEST_COMPLETE',{status:'achieved',same_wbb:true});
  }catch(e){
    await a3Report('A3_PUPIL_ERROR',{message:String(e&&(e.stack||e))});
  }finally{
    if(source)source.dispose();
    if(reopened)reopened.dispose();
  }
})();
