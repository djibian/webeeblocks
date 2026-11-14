'use strict';
// CI-only ACTIVITY 4 falsification: ONE real serialized Blockly .wbb, unchanged
// across two actual native R2025a scenes. Not an activated pupil profile.
// The scene-local C observer alone decides physical mission success/failure.
let a4Reports=Promise.resolve();
function a4Report(event,detail){
  a4Reports=a4Reports.then(()=>fetch('http://127.0.0.1:8765/event',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({event,detail:detail||null,wall_ms:Date.now()})
  }).then(response=>{if(!response.ok)throw Error('CI refused '+event);}));
  return a4Reports;
}
function a4Assert(value,message){if(!value)throw Error(message);}
function a4Profile(letter){
  const scene='decision-h-'+letter+'-v1';
  return {
    id:'ci-decision-h-conditional-v1',
    world:'worlds/crazyflie_classroom_start.wbt',
    brief:{visible:true,title:'4 — Observer pour décider',
      mission:'Observe la distance devant, franchis les obstacles sans collision et atterris sur le damier.'},
    pedagogy:{objective:'Mesurer une distance, la comparer et adapter la hauteur avec SI/SINON.'},
    toolbox:['webeeblocks_v2_takeoff','webeeblocks_v2_speed',
      'webeeblocks_v2_move','webeeblocks_v2_vertical',
      'webeeblocks_v2_range','controls_if','logic_compare',
      'math_number','webeeblocks_v2_land'],
    parameterBounds:{
      webeeblocks_v2_speed:{SPEED:{min:0.1,max:0.1,step:0.1}}
    },
    fieldOptions:{
      webeeblocks_v2_move:{DIRECTION:['forward']},
      webeeblocks_v2_vertical:{DIRECTION:['up','down']},
      webeeblocks_v2_range:{DIRECTION:['front']}
    },
    hardware:['crazyflie-2.1','flow-deck-v2','multi-ranger-deck'],
    timer:{enabled:false},
    evaluation:{type:'mission-state-v1',oracle:'progression-decision-h-v1'},
    runtime:{
      scene,mode:'ast-v1',
      allowedStatementKinds:['takeoff','set_speed','move','vertical','if','land'],
      rangeDirections:['front'],moveDirections:['forward'],
      verticalDirections:['up','down'],
      astBounds:{
        'takeoff.height_m':{min:0.50,max:0.50},
        'move.distance_m':{min:0.1,max:0.8},
        'vertical.distance_m':{min:0.1,max:0.50},
        'set_speed.speed_m_s':{min:0.1,max:0.1}
      }
    }
  };
}
function a4Number(ws, block, socket, value){
  const literal=ws.newBlock('math_number');
  literal.setFieldValue(String(value),'NUM');
  const input=block.getInput(socket);
  a4Assert(input&&input.connection,'missing value socket '+socket);
  input.connection.connect(literal.outputConnection);
  literal.setShadow(true);
  a4Assert(literal.isShadow(),'numeric literal was not a Blockly shadow');
  return literal;
}
function a4Chain(blocks){
  for(let i=0;i<blocks.length-1;i++){
    a4Assert(blocks[i].nextConnection&&blocks[i+1].previousConnection,
      'invalid statement chain at '+i);
    blocks[i].nextConnection.connect(blocks[i+1].previousConnection);
  }
}
function a4Workspace(){
  const ws=new Blockly.Workspace();
  function block(kind){return ws.newBlock(kind);}
  function move(distance){
    const b=block('webeeblocks_v2_move');
    b.setFieldValue('forward','DIRECTION');
    a4Number(ws,b,'DISTANCE',distance);
    return b;
  }
  function vertical(direction,distance){
    const b=block('webeeblocks_v2_vertical');
    b.setFieldValue(direction,'DIRECTION');
    a4Number(ws,b,'DISTANCE',distance);
    return b;
  }
  const takeoff=block('webeeblocks_v2_takeoff');
  a4Number(ws,takeoff,'HEIGHT',0.50);
  const speed=block('webeeblocks_v2_speed');
  speed.setFieldValue('0.1','SPEED');
  a4Assert(Number(speed.getFieldValue('SPEED'))===0.1,'speed field rounded');
  const initialClimb=vertical('up',0.25);
  const firstMove=move(0.20);
  const decision=block('controls_if');
  a4Assert(typeof decision.updateShape_==='function','Blockly 13 IF mutator missing');
  decision.elseCount_=1;
  decision.updateShape_();
  a4Assert(decision.getInput('ELSE'),'SI/SINON has no ELSE branch');
  const comparison=block('logic_compare');
  comparison.setFieldValue('LT','OP');
  const measured=block('webeeblocks_v2_range');
  measured.setFieldValue('front','DIRECTION');
  const threshold=block('math_number');
  threshold.setFieldValue('0.8','NUM');
  threshold.setShadow(true);
  comparison.getInput('A').connection.connect(measured.outputConnection);
  comparison.getInput('B').connection.connect(threshold.outputConnection);
  decision.getInput('IF0').connection.connect(comparison.outputConnection);
  // Near H in A => low then high; near threshold in B => high then low.
  // Station x=.95 is beyond the first collision envelope and before second.
  const near=[vertical('down',0.35),move(0.75),vertical('up',0.50)];
  const far=[vertical('up',0.10),move(0.75),vertical('down',0.45)];
  a4Chain(near);a4Chain(far);
  decision.getInput('DO0').connection.connect(near[0].previousConnection);
  decision.getInput('ELSE').connection.connect(far[0].previousConnection);
  a4Chain([takeoff,speed,initialClimb,firstMove,decision,move(0.80),block('webeeblocks_v2_land')]);
  return ws;
}
function a4Options(profile){
  return {Blockly,profiles:WebeeBlocksActivityProfiles,
    activitiesDocument:{version:1,activities:[profile]},
    blockCatalog:WebeeBlocksActivities.BLOCK_CATALOG,
    semanticAst:WebeeBlocksSemanticAst,
    activityContract:WebeeBlocksActivityContract};
}
async function a4Outcome(backend,evaluation){
  const until=Date.now()+95000;
  while(Date.now()<until){
    try{
      const result=await backend.readActivityOutcome(evaluation);
      a4Assert(result.status==='achieved',
        'independent native H observer rejected: '+JSON.stringify(result));
      return result;
    }catch(error){
      if(!error||error.code!=='OUTCOME_UNAVAILABLE')throw error;
      await new Promise(resolve=>setTimeout(resolve,200));
    }
  }
  throw Error('independent native H outcome not observed');
}
window.addEventListener('error',e=>a4Report('A4_PUPIL_ERROR',{message:String(e.message)}));
window.addEventListener('unhandledrejection',e=>a4Report('A4_PUPIL_ERROR',{message:String(e.reason)}));
(async()=>{
  let original=null,workspace=null;
  try{
    a4Assert(window.WB_A4_PUPIL_BOOTSTRAP,'missing HTML bootstrap');
    const opened=await window.WB_A4_PUPIL_BOOTSTRAP;
    a4Assert(opened&&opened.ok,'bootstrap refused');
    await a4Report('A4_PUPIL_JS_STARTED',{kind:'Blockly13-real-native-R2025a'});
    const profileA=a4Profile('a'),profileB=a4Profile('b');
    WebeeBlocksActivityProfiles.validateProfile(profileA,WebeeBlocksActivities.BLOCK_CATALOG);
    WebeeBlocksActivityProfiles.validateProfile(profileB,WebeeBlocksActivities.BLOCK_CATALOG);
    original=a4Workspace();
    WebeeBlocksActivityContract.applyFieldBounds(profileA,original);
    const originalAst=WebeeBlocksSemanticAst.compileWorkspace(original);
    WebeeBlocksActivityContract.preflightAst(profileA,originalAst);
    a4Assert(originalAst.program[0].height_m===0.50 &&
      originalAst.program[2].kind==='vertical' &&
      originalAst.program[2].direction==='up' &&
      originalAst.program[2].distance_m===0.25,
      'safe initial low takeoff and relative altitude advance required');
    a4Assert(originalAst.program.length===7&&originalAst.program[4].kind==='if',
      'no genuine Blockly condition in pupil program');
    const condition=originalAst.program[4];
    a4Assert(condition.condition.kind==='compare'&&
      condition.condition.op==='LT'&&
      condition.condition.left.kind==='range'&&
      condition.condition.left.direction==='front'&&
      condition.condition.right.value===0.8&&
      condition.then.length===3&&condition.else.length===3,
      'Blockly program did not compile to front-distance SI/SINON');
    // This serialized text is created exactly ONCE. Both executions reopen
    // these same exact bytes; they do not regenerate a variant-specific file.
    const wbb=WebeeBlocksProjectFiles.encodeProject(profileA,original,a4Options(profileA));
    for(let offset=0,index=0;offset<wbb.length;offset+=1400,index++)
      await a4Report('A4_PUPIL_WBB_CHUNK',{index,text:wbb.slice(offset,offset+1400)});
    await a4Report('A4_PUPIL_WBB_COMPLETE',{chars:wbb.length});
    await a4Report('A4_PUPIL_BLOCKLY_COMPILED',{statementKinds:originalAst.program.map(x=>x.kind),
      branches:2,sensor:'front',threshold_m:0.8});
    const module=await import('../blockly_v2/webots/RobotWindow.js');
    const bridge=new module.default();
    const backend=new WebeeBlocksWwiBackend({send:text=>bridge.send(text)},
      {simulationScenes:true,simulationReset:true,timeoutMs:60000,
       outcomeSettleMs:95000});
    bridge.receive=text=>backend.handleMessage(String(text));
    await backend.waitUntilReady();
    await a4Report('A4_PUPIL_RUNTIME_READY',{native:true});
    for(const letter of ['a','b']){
      const profile=letter==='a'?profileA:profileB;
      const parsed=WebeeBlocksProjectFiles.validateProjectText(
        wbb,profile,a4Options(profile));
      workspace=new Blockly.Workspace();
      Blockly.serialization.workspaces.load(parsed.project.workspace,workspace);
      WebeeBlocksActivityContract.applyFieldBounds(profile,workspace);
      WebeeBlocksActivityContract.preflightWorkspace(profile,workspace);
      const reopened=WebeeBlocksSemanticAst.compileWorkspace(workspace);
      a4Assert(JSON.stringify(reopened)===JSON.stringify(originalAst),
        'A/B .wbb reopen altered the actual semantic program');
      await a4Report('A4_PUPIL_PROJECT_REOPENED',{variant:letter,
        identical_bytes:true,chars:wbb.length});
      // The real Product pipeline chooses scene and executes reopened blocks.
      const executed=await WebeeBlocksActivityContract.execute(
        profile,workspace,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,backend);
      a4Assert(JSON.stringify(executed)===JSON.stringify(originalAst),
        'interpreter did not execute the reopened .wbb program');
      await a4Report('A4_PUPIL_INTERPRETER_LANDED',{variant:letter});
      await backend.completeActivityMission(profile.evaluation);
      const result=await a4Outcome(backend,profile.evaluation);
      await a4Report('A4_PUPIL_NATIVE_ACHIEVED',{variant:letter,
        status:result.status});
      workspace.dispose();workspace=null;
      if(letter==='a'){
        await backend.resetSimulation();
        await a4Report('A4_PUPIL_NATIVE_RESET',{between:'a,b',same_project:true});
      }
    }
    await a4Report('A4_PUPIL_TEST_COMPLETE',{variants:['a','b'],
      same_wbb:true,native_oracle:true});
  }catch(error){
    await a4Report('A4_PUPIL_ERROR',{message:String(error&&(error.stack||error))});
  }finally{
    if(original)original.dispose();
    if(workspace)workspace.dispose();
  }
})();
