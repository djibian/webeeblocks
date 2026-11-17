'use strict';
// A7 CI-ONLY real Blockly 13 + native PID. ONE serialized .wbb across L and R.
// This pedagogical validation probe is deliberately NOT in the student menu.
// The read-only C evaluator, not any JS event, awards physical mission success.
let reports=Promise.resolve();
function report(event,detail){
  reports=reports.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(r=>{if(!r.ok)throw Error('CI refused '+event);}));
  return reports;
}
function check(ok,msg){if(!ok)throw Error(msg);}
function profile(letter){
  // Run the very same public pupil profile and project semantics as the
  // student interface: only the native scene changes between L and R.
  const pupil=WebeeBlocksActivities.getProfile('progression-mini-grand-prix-v1');
  check(pupil.runtime.scene==='mini-grand-prix-l-v1' &&
    pupil.evaluation.oracle==='progression-mini-grand-prix-v1',
    'public Mini Grand Prix pupil profile drifted from native oracle');
  check(letter==='l'||letter==='r','invalid native Mini GP variant');
  pupil.runtime.scene='mini-grand-prix-'+letter+'-v1';
  return pupil;
}
function number(ws,parent,socket,value){
  const literal=ws.newBlock('math_number');
  literal.setFieldValue(String(value),'NUM');
  const input=parent.getInput(socket);
  check(input&&input.connection,'missing Blockly value socket '+socket);
  input.connection.connect(literal.outputConnection);
  literal.setShadow(true);
  check(literal.isShadow(),'Blockly numeric literal must be a shadow');
}
function chain(blocks){
  for(let i=0;i<blocks.length-1;i++){
    check(blocks[i].nextConnection&&blocks[i+1].previousConnection,
      'broken Blockly statement connections at '+i);
    blocks[i].nextConnection.connect(blocks[i+1].previousConnection);
  }
}
function workspace(){
  const ws=new Blockly.Workspace();
  function create(type){return ws.newBlock(type);}
  function move(m){
    const b=create('webeeblocks_v2_move');
    b.setFieldValue('forward','DIRECTION');number(ws,b,'DISTANCE',m);
    return b;
  }
  function vertical(direction,m){
    const b=create('webeeblocks_v2_vertical');
    b.setFieldValue(direction,'DIRECTION');number(ws,b,'DISTANCE',m);
    return b;
  }
  function turn(direction){
    const b=create('webeeblocks_v2_turn');
    b.setFieldValue(direction,'DIRECTION');b.setFieldValue('90','ANGLE');
    return b;
  }
  const takeoff=create('webeeblocks_v2_takeoff');
  number(ws,takeoff,'HEIGHT',0.50);
  const speed=create('webeeblocks_v2_speed');
  speed.setFieldValue('0.1','SPEED');
  check(Number(speed.getFieldValue('SPEED'))===0.1,'flight speed changed');
  const climb=vertical('up',0.25);
  const decision=create('controls_if');
  check(typeof decision.updateShape_==='function','Blockly 13 IF missing');
  decision.elseCount_=1;decision.updateShape_();
  check(decision.getInput('ELSE'),'Blockly SI/SINON missing ELSE');
  const compare=create('logic_compare');compare.setFieldValue('LT','OP');
  const sensor=create('webeeblocks_v2_range');sensor.setFieldValue('front','DIRECTION');
  const threshold=create('math_number');
  threshold.setFieldValue('0.75','NUM');threshold.setShadow(true);
  compare.getInput('A').connection.connect(sensor.outputConnection);
  compare.getInput('B').connection.connect(threshold.outputConnection);
  decision.getInput('IF0').connection.connect(compare.outputConnection);
  // High frontal ray: L~0.615 m to the H bar, R~0.915 m. Both branches
  // descend to .40 m before crossing the real H and land on a distinct pad.
  const near=[vertical('down',0.35),move(0.80),move(0.80),
              turn('left'),move(0.80),move(0.15)];
  const far=[vertical('down',0.35),move(0.80),move(0.80),move(0.30),
             turn('right'),move(0.80),move(0.15)];
  chain(near);chain(far);
  decision.getInput('DO0').connection.connect(near[0].previousConnection);
  decision.getInput('ELSE').connection.connect(far[0].previousConnection);
  chain([takeoff,speed,climb,decision,create('webeeblocks_v2_land')]);
  return ws;
}
/* CI-only independent negative pupil program: short authentic motor flight,
 * premature LAND before reaching H. The C oracle, never Blockly, judges it. */
function failingWorkspace(){
  const ws=new Blockly.Workspace();
  function create(kind){return ws.newBlock(kind);}
  const takeoff=create('webeeblocks_v2_takeoff');
  number(ws,takeoff,'HEIGHT',0.50);
  const speed=create('webeeblocks_v2_speed');
  speed.setFieldValue('0.1','SPEED');
  const forward=create('webeeblocks_v2_move');
  forward.setFieldValue('forward','DIRECTION');
  number(ws,forward,'DISTANCE',0.20);
  chain([takeoff,speed,forward,create('webeeblocks_v2_land')]);
  return ws;
}
function options(profile){
  return{Blockly,profiles:WebeeBlocksActivityProfiles,
    activitiesDocument:WebeeBlocksActivities.DOCUMENT,
    blockCatalog:WebeeBlocksActivities.BLOCK_CATALOG,
    semanticAst:WebeeBlocksSemanticAst,
    activityContract:WebeeBlocksActivityContract};
}
async function nativeOutcome(backend,evaluation){
  const deadline=Date.now()+95000;
  while(Date.now()<deadline){
    try{
      const result=await backend.readActivityOutcome(evaluation);
      check(result.status==='achieved',
        'native A7 outcome is not success: '+JSON.stringify(result));
      return result;
    }catch(error){
      if(!error||error.code!=='OUTCOME_UNAVAILABLE')throw error;
      await new Promise(resolve=>setTimeout(resolve,200));
    }
  }
  throw Error('native Mini Grand Prix mission outcome absent');
}
window.addEventListener('error',e=>report('A7_PUPIL_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>report('A7_PUPIL_ERROR',{message:String(e.reason)}));
(async()=>{
  let original=null,reopened=null;
  try{
    check(window.WB_A7_PUPIL_BOOTSTRAP,'HTML startup missing');
    const boot=await window.WB_A7_PUPIL_BOOTSTRAP;
    check(boot&&boot.ok,'HTML browser bootstrap rejected');
    await report('A7_PUPIL_JS_STARTED',{kind:'genuine-Blockly-13-and-native-R2025a'});
    const left=profile('l'),right=profile('r');
    WebeeBlocksActivityProfiles.validateProfile(left,WebeeBlocksActivities.BLOCK_CATALOG);
    WebeeBlocksActivityProfiles.validateProfile(right,WebeeBlocksActivities.BLOCK_CATALOG);
    original=workspace();
    WebeeBlocksActivityContract.applyFieldBounds(left,original);
    const ast=WebeeBlocksSemanticAst.compileWorkspace(original);
    WebeeBlocksActivityContract.preflightAst(left,ast);
    const program=ast.program;
    check(program.length===5 && program[0].kind==='takeoff' &&
      program[1].kind==='set_speed' && program[2].kind==='vertical' &&
      program[3].kind==='if' && program[4].kind==='land',
      'incorrect Blockly semantic program');
    const statement=program[3],condition=statement.condition;
    check(condition.kind==='compare' && condition.op==='LT' &&
      condition.left.kind==='range' && condition.left.direction==='front' &&
      condition.right.value===0.75 &&
      statement.then.length===6 && statement.else.length===7 &&
      statement.then[3].kind==='turn' && statement.then[3].angle_deg===90 &&
      statement.else[4].kind==='turn' && statement.else[4].angle_deg===-90,
      'Blockly did not produce sensor-controlled left and right 90-degree turns');
    // Encode ONCE, report the bytes, and reopen the SAME bytes twice.
    const wbb=WebeeBlocksProjectFiles.encodeProject(left,original,options(left));
    for(let offset=0,index=0;offset<wbb.length;offset+=1400,index++)
      await report('A7_PUPIL_WBB_CHUNK',{index,text:wbb.slice(offset,offset+1400)});
    await report('A7_PUPIL_WBB_COMPLETE',{chars:wbb.length});
    await report('A7_PUPIL_BLOCKLY_COMPILED',{
      statementKinds:program.map(x=>x.kind),sensor:'front',threshold_m:0.75});
    const module=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new module.default();
    const backend=new WebeeBlocksWwiBackend({send:text=>bridge.send(text)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000,
       outcomeSettleMs:95000});
    bridge.receive=text=>backend.handleMessage(String(text));
    await backend.waitUntilReady();
    await report('A7_PUPIL_RUNTIME_READY',{native:true});
    // Give the real physics time to settle at the blue origin. No scripted
    // teleport, fake pose, forged sensor or bypass of START validation.
    await new Promise(resolve=>setTimeout(resolve,1600));
    for(const letter of ['l','r']){
      const current=letter==='l'?left:right;
      const decoded=WebeeBlocksProjectFiles.validateProjectText(
        wbb,current,options(current));
      reopened=new Blockly.Workspace();
      Blockly.serialization.workspaces.load(decoded.project.workspace,reopened);
      WebeeBlocksActivityContract.applyFieldBounds(current,reopened);
      WebeeBlocksActivityContract.preflightWorkspace(current,reopened);
      const reconstructed=WebeeBlocksSemanticAst.compileWorkspace(reopened);
      check(JSON.stringify(reconstructed)===JSON.stringify(ast),
        'reopened L/R .wbb modified semantic AST');
      await report('A7_PUPIL_PROJECT_REOPENED',{variant:letter,
        identical_bytes:true,chars:wbb.length});
      const executed=await WebeeBlocksActivityContract.execute(
        current,reopened,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,backend);
      check(JSON.stringify(executed)===JSON.stringify(ast),
        'interpreter did not run the reopened Blockly .wbb');
      await report('A7_PUPIL_INTERPRETER_LANDED',{variant:letter});
      await backend.completeActivityMission(current.evaluation);
      const result=await nativeOutcome(backend,current.evaluation);
      await report('A7_PUPIL_NATIVE_ACHIEVED',{variant:letter,status:result.status});
      reopened.dispose();reopened=null;
      if(letter==='l'){
        await backend.resetSimulation();
        await report('A7_PUPIL_NATIVE_RESET',{between:'l,r',same_project:true});
      }
    }
    /* Third native attempt: a separate genuine Blockly program takes off,
     * moves, then lands before H. Read an independently published C verdict,
     * never synthesize the negative reason from these program blocks. */
    await backend.resetSimulation();
    await backend.prepareActivity(left);
    await new Promise(resolve=>setTimeout(resolve,1600));
    reopened=failingWorkspace();
    WebeeBlocksActivityContract.applyFieldBounds(left,reopened);
    WebeeBlocksActivityContract.preflightWorkspace(left,reopened);
    const failingAst=WebeeBlocksSemanticAst.compileWorkspace(reopened);
    check(failingAst.program.length===4 &&
      failingAst.program[2].kind==='move' &&
      failingAst.program[2].distance_m===0.20 &&
      failingAst.program[3].kind==='land',
      'negative case does not move and land using genuine Blockly');
    const failingExecuted=await WebeeBlocksActivityContract.execute(
      left,reopened,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,backend);
    check(JSON.stringify(failingExecuted)===JSON.stringify(failingAst),
      'negative pupil AST was not run by the real interpreter');
    await backend.completeActivityMission(left.evaluation);
    const negativeRaw=await backend.readActivityOutcome(left.evaluation);
    const feedback=WebeeBlocksRuntimeOutcome.classifyMission(
      negativeRaw,left.evaluation);
    const expected='Mission non accomplie — Programme terminé avant la fin du parcours';
    check(negativeRaw.status==='not-achieved' &&
      negativeRaw.reason==='early-finish' &&
      feedback.state==='MISSION NON RÉUSSIE' &&
      feedback.detail===expected,
      'native failure reason did not reach the real product classifier');
    const visible=document.createElement('p');
    visible.id='a7NativeReason';
    visible.setAttribute('role','status');
    visible.textContent=feedback.state+' — '+feedback.detail;
    document.body.appendChild(visible);
    check(document.getElementById('a7NativeReason')===visible &&
      visible.isConnected && visible.textContent.includes(expected),
      'French A7 feedback was not rendered in the real Chrome window');
    await report('A7_PUPIL_NEGATIVE_NATIVE_REASON',{
      variant:'l',status:negativeRaw.status,reason:negativeRaw.reason,
      detail:feedback.detail,visible:true,scripted_solution:false});
    reopened.dispose();reopened=null;
    await report('A7_PUPIL_TEST_COMPLETE',{variants:['l','r'],
      same_wbb:true,native_oracle:true,negative_native_reason:true});
  }catch(error){
    await report('A7_PUPIL_ERROR',{message:String(error&&(error.stack||error))});
  }finally{
    if(original)original.dispose();
    if(reopened)reopened.dispose();
  }
})();
