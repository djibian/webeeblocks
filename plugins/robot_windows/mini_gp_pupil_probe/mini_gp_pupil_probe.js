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
  return{
    id:'ci-mini-grand-prix-conditional-v1',
    world:'worlds/ci_classroom_mini_gp_pupil.wbt',
    brief:{visible:true,title:'7 — Mini Grand Prix',
      mission:'Franchis le H ouvert, tourne à angle droit et atterris avant le H fermé.'},
    pedagogy:{objective:'Mesurer, comparer, franchir un obstacle, tourner de 90° et atterrir.'},
    toolbox:['webeeblocks_v2_takeoff','webeeblocks_v2_speed',
      'webeeblocks_v2_vertical','webeeblocks_v2_move','webeeblocks_v2_turn',
      'webeeblocks_v2_range','controls_if','logic_compare','math_number',
      'webeeblocks_v2_land'],
    parameterBounds:{webeeblocks_v2_speed:{SPEED:{min:0.1,max:0.1,step:0.1}}},
    fieldOptions:{
      webeeblocks_v2_vertical:{DIRECTION:['up','down']},
      webeeblocks_v2_move:{DIRECTION:['forward']},
      webeeblocks_v2_turn:{DIRECTION:['left','right']},
      webeeblocks_v2_range:{DIRECTION:['front']}
    },
    hardware:['crazyflie-2.1','flow-deck-v2','multi-ranger-deck'],
    timer:{enabled:false},
    evaluation:{type:'mission-state-v1',oracle:'progression-mini-grand-prix-v1'},
    runtime:{
      scene:'mini-grand-prix-'+letter+'-v1',mode:'ast-v1',
      allowedStatementKinds:['takeoff','set_speed','vertical','move','turn','if','land'],
      rangeDirections:['front'],moveDirections:['forward'],verticalDirections:['up','down'],
      astBounds:{
        'takeoff.height_m':{min:0.50,max:0.50},
        'move.distance_m':{min:0.15,max:0.80},
        'vertical.distance_m':{min:0.25,max:0.35},
        'set_speed.speed_m_s':{min:0.1,max:0.1},
        'turn.angle_deg_abs':{min:90,max:90}
      }
    }
  };
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
function options(profile){
  return{Blockly,profiles:WebeeBlocksActivityProfiles,
    activitiesDocument:{version:1,activities:[profile]},
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
    await report('A7_PUPIL_TEST_COMPLETE',{variants:['l','r'],
      same_wbb:true,native_oracle:true});
  }catch(error){
    await report('A7_PUPIL_ERROR',{message:String(error&&(error.stack||error))});
  }finally{
    if(original)original.dispose();
    if(reopened)reopened.dispose();
  }
})();
