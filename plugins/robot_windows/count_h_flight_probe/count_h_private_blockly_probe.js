'use strict';
/* CI-ONLY A6 reference: actual saved Blockly 13.2.1 .wbb. This module
 * receives NO variant, scene identity, GPS, supervisor or pupil AST.
 * It does NOT activate the A6 product/pupil profile or authorize hardware.
 */
export async function runPrivateBlockly(backend,report,options={}) {
  const stateless=options.stateless===true;
  const response=await fetch('http://127.0.0.1:8765/a6-private-wbb',{cache:'no-store'});
  if(!response.ok)throw Error('private canonical Blockly file unavailable');
  const bytes=await response.text();
  if(bytes.length<100||bytes.length>1048576)
    throw Error('private Blockly file outside bounded size');
  WebeeBlocksSemanticAst.installConditionalLoopBounds(Blockly);
  const p=WebeeBlocksActivities.getProfile('reactive-obstacle-v2');
  p.id='progression-count-h-private-ci-only';
  p.brief={visible:false,title:'PRIVATE A6 CI ONLY',
    goal:'Validate serialized Blockly without giving students a solution'};
  p.toolbox=Array.from(new Set(p.toolbox.concat(['controls_whileUntil'])));
  p.fieldOptions=Object.assign({},p.fieldOptions,{
    webeeblocks_v2_range:{DIRECTION:['up','front']},
    webeeblocks_v2_move:{DIRECTION:['forward','left','right']}
  });
  p.runtime.allowedStatementKinds=Array.from(
    new Set(p.runtime.allowedStatementKinds.concat(['while'])));
  p.runtime.rangeDirections=['up','front'];
  p.runtime.moveDirections=['forward','left','right'];
  p.runtime.maxSteps=20000;
  p.runtime.astBounds=Object.assign({},p.runtime.astBounds,{
    'move.distance_m':{min:.01,max:.70},
    'move.forward.distance_m':{min:.01,max:.70},
    'move.lateral.distance_m':{min:.01,max:.60},
    'while.max_iterations':{min:1,max:80}
  });
  const doc={version:1,activities:[p]};
  const profile=WebeeBlocksActivityProfiles.resolveById(doc,p.id,
    WebeeBlocksActivities.BLOCK_CATALOG);
  const options={Blockly,profiles:WebeeBlocksActivityProfiles,
    activitiesDocument:doc,blockCatalog:WebeeBlocksActivities.BLOCK_CATALOG,
    semanticAst:WebeeBlocksSemanticAst,
    activityContract:WebeeBlocksActivityContract};
  const parsed=WebeeBlocksProjectFiles.validateProjectText(bytes,profile,options);
  const workspace=new Blockly.Workspace();
  try {
    Blockly.serialization.workspaces.load(parsed.project.workspace,workspace);
    WebeeBlocksActivityContract.preflightWorkspace(profile,workspace);
    WebeeBlocksActivityContract.applyFieldBounds(profile,workspace);
    const reopened=WebeeBlocksSemanticAst.compileWorkspace(workspace);
    WebeeBlocksActivityContract.preflightAst(profile,reopened);
    if(JSON.stringify(reopened)!==JSON.stringify(parsed.ast))
      throw Error('canonical .wbb semantic AST altered after reopening');
    if(stateless &&
      (workspace.getVariableMap().getAllVariables().length!==0||
       !reopened.program.some(node=>node.kind==='if')))
      throw Error('stateless private comparator requires zero variables and actual conditions');
    await report('A6_PRIVATE_WBB_REOPENED',{chars:bytes.length,
      statement_count:reopened.program.length,same_private_project:true,testOnly:true});
    // Native scene admitted already by test adapter. Product A6 registry is
    // NOT enabled. Relay the real motor commands with scene prepare disabled.
    // CI-only command counters prove the physical repeat count without
    // adding a third variable to the two-variable Blockly program.
    let acknowledgedSteps=0;
    let acknowledgedMoves=0;
    const native={
      capabilities:Object.assign({},backend.capabilities,{simulationScenes:false}),
      takeoff:async height=>{
        await backend.takeoff(height);
        await report('A6_TAKEOFF',{height_m:height,blockly:true});
      },
      setSpeed:speed=>backend.setSpeed(speed),
      move:async(direction,distance)=>{
        await backend.move(direction,distance);
        acknowledgedMoves++;
        // CI-only command attestation, NOT a mission oracle or pupil AST rule.
        // The B experiment compares a 4-cm and 8-cm program. Both use the
        // same true native backend and can be counted as fresh MOVE ACKs.
        if(direction==='forward'&&
          (Math.abs(distance-.08)<1e-8||Math.abs(distance-.04)<1e-8))
          acknowledgedSteps++;
      },
      readRange:direction=>backend.readRange(direction),
      land:async()=>{
        await backend.land();
        await report('A6_LANDED',{nativeReply:true,blockly:true});
      }
    };
    let counted=false;
    const executed=await WebeeBlocksActivityContract.execute(
      profile,workspace,WebeeBlocksSemanticAst,WebeeBlocksInterpreter,native,
      {maxSteps:profile.runtime.maxSteps,
       hooks:{beforeStep:async context=>{
         if(context.node.kind!=='land')return;
         const variables=context.variables||{};
         const count=variables.count,steps=acknowledgedSteps;
         if(stateless) {
           // Do not require an absent counter, or infer the target from the
           // private scene. The existing native C oracle alone scores LAND.
           const front=await backend.readRange('front');
           if(acknowledgedMoves<3||acknowledgedMoves>14||
             !Number.isFinite(front)||front<.30||front>.82)
             throw Error('private stateless commands invalid before LAND '+
               'moves='+String(acknowledgedMoves)+' front_m='+String(front));
           counted=true;
           await report('A6_STATELESS_OBSERVATION',{
             moves:acknowledgedMoves,front_m:front,variables:0,testOnly:true
           });
           await report('A6_CORRIDOR_DONE',{stateless:true,moves:acknowledgedMoves});
           await report('A6_PAD_SELECTED',{stateless:true,padByNativeOracle:true});
           return;
         }
         // Independent final native sample only for CI attestation, not
         // passed into the learner AST or used to select the landing pad.
         const front=await backend.readRange('front');
         if(!Number.isInteger(count)||count<1||count>3||
            !Number.isInteger(steps)||steps<20||steps>80||
            !Number.isFinite(front)||front<.30||front>.82)
           throw Error('private Blockly sensor count invalid before native LAND '+
             'count='+String(count)+' steps='+String(steps)+
             ' front_m='+String(front));
         counted=true;
         await report('A6_SENSOR_COUNT',{count,steps,front_m:front,
           sceneBlind:true,testOnly:true,compiledFromPrivateWbb:true});
         await report('A6_CORRIDOR_DONE',{sensorOnly:true,steps,blockly:true});
         await report('A6_PAD_SELECTED',{count,blockly:true});
       }}});
    if(!counted||JSON.stringify(executed)!==JSON.stringify(parsed.ast))
      throw Error('private .wbb was not executed by the real AST interpreter');
    // Only after the entire .wbb and its native LAND have completed may
    // the broker publish the reset-scoped, oracle-bound completion marker.
    await backend.completeActivityMission({type:'mission-state-v1',oracle:'progression-count-h-v1'});
    await report('A6_NATIVE_COMPLETION_ACK',{nativeReply:true,testOnly:true});
    await report('A6_TEST_COMPLETE',{testOnly:true,blockly:true,
      statelessComparator:stateless,
      samePrivateWbb:true,productA6Unqualified:true});
  } finally {workspace.dispose();}
}
