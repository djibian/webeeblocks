'use strict';
// DRAFT-ONLY: actual Blockly 13 project bytes through authentic Webots WWI,
// against the A5 independent native PID + Floor monitor. NEVER pupil material.
// This module sees NO variant, scene identity, Supervisor node or oracle answer.
export async function runPrivateBlockly(backend,report){
  const response=await fetch('http://127.0.0.1:8765/a5-private-wbb',
    {cache:'no-store'});
  if(!response.ok)throw Error('A5 canonical private .wbb was not served');
  const bytes=await response.text();
  if(bytes.length<100||bytes.length>1048576)
    throw Error('A5 private WBB out of authorized bounds');
  const data=new TextEncoder().encode(bytes);
  const digest=await crypto.subtle.digest('SHA-256',data);
  const sha=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
  const Semantic=WebeeBlocksSemanticAst;
  Semantic.installConditionalLoopBounds(Blockly);
  const p=WebeeBlocksActivities.getProfile('reactive-obstacle-v2');
  p.id='progression-reactive-hg-private-ci-only';
  p.starterVisible=false;
  p.brief={visible:false,title:'PRIVATE CI ONLY',
    goal:'Test real Blockly loop and one memory variable'};
  p.toolbox=Array.from(new Set([...p.toolbox,'controls_whileUntil']));
  p.fieldOptions={...p.fieldOptions,
    webeeblocks_v2_range:{DIRECTION:['left','front']},
    webeeblocks_v2_move:{DIRECTION:['forward']},
    webeeblocks_v2_turn:{DIRECTION:['left','right']}};
  p.parameterBounds={...p.parameterBounds,
    webeeblocks_v2_speed:{SPEED:{min:.2,max:.2,step:.01}}};
  p.runtime.allowedStatementKinds=Array.from(
    new Set([...p.runtime.allowedStatementKinds,'while']));
  p.runtime.rangeDirections=['left','front'];
  p.runtime.moveDirections=['forward'];p.runtime.maxSteps=20000;
  p.runtime.astBounds={...p.runtime.astBounds,
    'move.distance_m':{min:.1,max:1.24},
    'move.forward.distance_m':{min:.1,max:1.24},
    'takeoff.height_m':{min:.5,max:.5},
    'set_speed.speed_m_s':{min:.2,max:.2},
    'turn.angle_deg_abs':{min:90,max:90},
    'while.max_iterations':{min:1,max:32}};
  const activities={version:1,activities:[p]};
  const profile=WebeeBlocksActivityProfiles.resolveById(
    activities,p.id,WebeeBlocksActivities.BLOCK_CATALOG);
  if(WebeeBlocksActivities.DOCUMENT.activities.some(x=>x.id===p.id))
    throw Error('private A5 project ID leaked into pupil catalogue');
  const options={Blockly,profiles:WebeeBlocksActivityProfiles,
    activitiesDocument:activities,
    blockCatalog:WebeeBlocksActivities.BLOCK_CATALOG,
    semanticAst:Semantic,activityContract:WebeeBlocksActivityContract};
  const validated=WebeeBlocksProjectFiles.validateProjectText(bytes,profile,options);
  const workspace=new Blockly.Workspace();
  try{
    Blockly.serialization.workspaces.load(validated.project.workspace,workspace);
    WebeeBlocksActivityContract.preflightWorkspace(profile,workspace);
    const ast=Semantic.compileWorkspace(workspace);
    WebeeBlocksActivityContract.preflightAst(profile,ast);
    if(JSON.stringify(ast)!==JSON.stringify(validated.ast))
      throw Error('A5 serialized AST changed upon reopening');
    const vars=workspace.getVariableMap().getAllVariables().map(x=>x.name).sort();
    if(vars.length!==1||vars[0]!=='destination')
      throw Error('A5 private source has unexpected variables');
    if(ast.program[3]?.kind!=='while')
      throw Error('A5 private source has no genuine bounded loop');
    await report('A5_FACTOR_MOTOR_WBB_REOPENED',{
      sha256:sha,bytes:data.length,one_variable:true,
      fresh_front_loop:true,pupilWbb:false,testOnly:true});
    let early=null,late=null,leftReads=0,frontReads=0;
    let gatePassed=false;
    const native={
      capabilities:{...backend.capabilities,simulationScenes:false},
      takeoff:async height=>{
        await backend.takeoff(height);
        await report('A5_FACTOR_MOTOR_TAKEOFF',{height_m:height,blockly:true});
      },
      setSpeed:s=>backend.setSpeed(s),
      readRange:async direction=>{
        const value=await backend.readRange(direction);
        if(!Number.isFinite(value))throw Error('native range not finite');
        if(direction==='front'){
          frontReads++;
          if(frontReads>33)throw Error('too many native front reads');
          return value;
        }
        if(direction!=='left')throw Error('private AST requests unexpected sensor');
        leftReads++;
        if(leftReads===1){
          early=value;
          await report('A5_FACTOR_MOTOR_H_OBSERVATION',{
            left_m:early,destination:early>.8?'right':'left',
            decision_source:'initial_left_only',blockly:true});
        }else if(leftReads===2){
          late=value;
          if(frontReads<21||frontReads>33)
            throw Error('real Webots front loop was not actually sampled');
          await report('A5_FACTOR_MOTOR_APPROACH',{
            front_reads:frontReads,fresh_condition:true,blockly:true});
          await report('A5_FACTOR_MOTOR_G_OBSERVATION',{
            left_m:late,route:late>1?'left':'right',
            decision_source:'late_left_only',blockly:true});
        }else throw Error('unexpected additional private left read');
        return value;
      },
      turn:angle=>backend.turn(angle),
      move:async(direction,distance)=>{
        await backend.move(direction,distance);
        if(!gatePassed&&late!==null&&Math.abs(distance-.8)<1e-8){
          gatePassed=true;
          await report('A5_FACTOR_MOTOR_GATE_PASSED',{
            route:late>1?'left':'right',blockly:true});
        }
      },
      land:async()=>{
        if(!gatePassed||early===null||late===null)
          throw Error('LAND before native gate and H/G observations');
        await report('A5_FACTOR_MOTOR_PAD_SELECTED',{
          side:early>.8?'right':'left',
          decision_source:'initial_left_only',blockly:true});
        await backend.land();
        await report('A5_FACTOR_MOTOR_LAND_ACK',{nativeReply:true,blockly:true});
      }
    };
    const facts=WebeeBlocksActivityContract.preflightAst(profile,ast);
    WebeeBlocksActivityContract.preflightBackend(profile,facts,native);
    const result=await WebeeBlocksInterpreter.run(ast,native,{
      maxSteps:profile.runtime.maxSteps,motionBounds:profile.runtime.astBounds});
    if(result.variables.destination!==early||frontReads<21||leftReads!==2)
      throw Error('real native .wbb result mismatches observed sensor state');
    await report('A5_FACTOR_MOTOR_TEST_COMPLETE',{
      nativeReply:true,pupilWbb:false,missionOracle:false,
      samePrivateWbb:true,blockly:true,sha256:sha,
      front_reads:frontReads,stored_initial_h:early,testOnly:true});
  }finally{workspace.dispose();}
}
