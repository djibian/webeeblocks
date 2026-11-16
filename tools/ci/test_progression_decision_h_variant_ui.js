'use strict';
// Exercising the REAL product UI under a deterministic fake DOM/backend.
// This checks session-only A/B switching; real motorized R2025a is separately
// proven by the compulsory A4 Runtime suite, not by this test.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
const Activities=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Projects=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/project_files.js'));
const src=fs.readFileSync(path.join(ROOT,'plugins/robot_windows/blockly_v2/project_ui.js'),'utf8');
const mainSrc=fs.readFileSync(path.join(ROOT,'plugins/robot_windows/blockly_v2/main.js'),'utf8');

function element(){
  return {disabled:false,hidden:false,textContent:'',dataset:{},inert:false,
    handlers:{},addEventListener(type,handler){this.handlers[type]=handler}};
}
async function flush(){for(let i=0;i<40;i++)await Promise.resolve();}

async function scenario(startProfileId, options={}){
  const names=['projectActivity','projectOpen','projectSave','projectSaveAs','activityVariant',
    'blocklyDiv','projectFileState','runtimeDetail','activityTitle','activityGoal'];
  const elements=Object.fromEntries(names.map(k=>[k,element()]));
  const callbacks=Object.create(null),events=[];
  const window={addEventListener(type,handler){(callbacks[type]??=[]).push(handler)},
    dispatchEvent(evt){for(const f of callbacks[evt.type]||[])f(evt)}};
  const document={body:{dataset:{}},getElementById(id){return elements[id]}};
  class CustomEvent{constructor(type,options){this.type=type;this.detail=options?.detail}}
  const Blockly={};
  let readOnly=false;
  const workspace={state:{blocks:['students work',42]}};
  if(!options.noReadOnlyApi){
    workspace.isReadOnly=()=>readOnly;
    workspace.setIsReadOnly=value=>{readOnly=value===true};
  }
  function editWouldBeBlocked(){
    return (typeof workspace.isReadOnly==='function' && workspace.isReadOnly()) ||
      elements.blocklyDiv.inert;
  }
  const backendCalls=[],diagnostics=[];
  let holdAck=false,resolveAck=null,failNext=false,saveWrites=0,clearBreakpoints=0;
  let resetCalls=0;
  let manager=null;
  const runtimeBackend={ready:true,capabilities:{simulationScenes:true},
    async waitUntilReady(){},
    prepareActivity(profile){
      backendCalls.push({scene:profile.runtime.scene,id:profile.id});
      if(failNext){failNext=false;return Promise.reject(new Error('NATIVE_SCENE_ACK_REJECT'))}
      if(holdAck)return new Promise(resolve=>{resolveAck=resolve});
      return Promise.resolve();
    }};
  const WebeeBlocksProjectFiles={
    createBrowserTransport:()=>({nativeFileSystemAccess:true,mode:'browser-native'}),
    createManager(options){
      manager={nativeFileSystemAccess:true,hasCurrentTarget:()=>true,
        bytes:()=>JSON.stringify({project:JSON.parse(Projects.createStarterText(options.getProfile().id)),
          studentBlocks:workspace.state}),
        save(){saveWrites++},saveAs(){saveWrites++},open(){saveWrites++},openTemplateText(){saveWrites++}};
      return manager;
    }};
  // A synthetic published activity in another WBT must never leak into the
  // current world's chooser. This tests future A6 publication without changing
  // the real repository's hidden/public activity catalogue.
  const fixtureWorld='worlds/ci-foreign-classroom.wbt';
  const future={...Activities.getProfile('progression-sequence-v1'),
    id:'progression-future-world-v1',world:fixtureWorld,starterVisible:true};
  const localActivities={...Activities,DOCUMENT:{...Activities.DOCUMENT,
    activities:[...Activities.DOCUMENT.activities,future]}};
  const profile=JSON.parse(JSON.stringify(Activities.getProfile(startProfileId)));
  if(options.worldOverride)profile.world=options.worldOverride;
  const inputs={window,document,CustomEvent,Blockly,workspace,
    robotWindow:{send(){},receive(){}},runtimeProfile:profile,
    runtimeBackend,WebeeBlocksProjectFiles,WebeeBlocksActivityProfiles:Profiles,
    WebeeBlocksActivities:localActivities,WebeeBlocksSemanticAst:{},
    WebeeBlocksActivityContract:{applyFieldBounds(){}},
    runtimeRunning:false,runtimeResetPending:false,runtimeStopPending:false,
    runtimeScenePending:false,runtimeTerminal:options.outcomePending===true,
    runtimeOutcomePending:options.outcomePending===true,runtimeProjectPending:false,
    async resetSimulation(){resetCalls++},
    updateRuntimeActions(){},setRuntimeStatus(){},
    setRuntimeFailure(error){diagnostics.push('native:'+error.message)},
    runtimeDebug:{clearBreakpoints(){clearBreakpoints++}},
    console:{error(...args){diagnostics.push(args.map(v=>v?.message||String(v)).join(' '))},
      warn(){},log(){}}};
  const control=new Function(...Object.keys(inputs),src+
    '\nreturn {setOutcomePending(value){runtimeOutcomePending=value;},'+
    'starterIds(){return progressionProfiles().map(p=>p.id);}};')(...Object.values(inputs));
  assert(callbacks.load?.length===1,'actual project UI did not subscribe to window load');
  callbacks.load[0]();await flush();
  assert(manager,'real project UI did not initialize its file manager');
  const choices=control.starterIds();
  assert(choices.every(id=>{
    const p=localActivities.DOCUMENT.activities.find(v=>v.id===id);
    return p&&p.starterVisible!==false&&p.world===profile.world;
  }), 'activity chooser offered a project from another Webots world');
  if(options.worldOverride){
    const expected=options.worldOverride===fixtureWorld?['progression-future-world-v1']:[];
    assert.deepEqual(choices,expected,'incorrect world-bound published choice');
    assert.equal(elements.projectActivity.disabled,expected.length===0,
      'Start must not expose impossible choices');
    if(!expected.length)assert.match(elements.projectActivity.title,/Aucune activité publiée/);
    assert.equal(elements.projectOpen.disabled,false,
      'the chooser filter must not disable opening a compatible existing project');
    assert.equal(saveWrites,0,'world-bound chooser unexpectedly wrote a project');
    return {kind:'world-filter',status:'PASS'};
  }
  assert(!choices.includes('progression-future-world-v1'),
    'foreign published starter shown in normal Webots school world');
  assert(choices.includes(startProfileId),'compatible public activity missing');
  assert.equal(elements.projectActivity.disabled,false,'normal Start unexpectedly disabled');
  const btn=elements.activityVariant;
  assert(typeof btn.handlers.click==='function','real A4 toggle was not bound');
  const bytes=manager.bytes();
  if(!options.outcomePending)
    assert(!editWouldBeBlocked(),'pupil must be able to edit while READY');
  const mini=startProfileId==='progression-mini-grand-prix-v1';
  const nextScene=mini?'mini-grand-prix-r-v1':'decision-h-b-v1';
  const firstScene=mini?'mini-grand-prix-l-v1':'decision-h-a-v1';
  const firstLabel=mini?/Parcours gauche/:/Parcours A/;
  const nextLabel=mini?/Parcours droite/:/Parcours B/;

  if(startProfileId!=='progression-decision-h-v1' && !mini){
    assert(btn.hidden&&btn.disabled,'non-A4 profile must hide and disable A/B control');
    btn.handlers.click();await flush();
    assert.equal(backendCalls.length,0,'non-A4 click attempted a scene mutation');
    assert.equal(manager.bytes(),bytes,'non-A4 variant changed project bytes');
    return {kind:'other-profile',status:'PASS'};
  }
  if(options.outcomePending===true){
    // Deliberately deliver a stale READY event in the interval where Blockly
    // is done but the native evaluator has not yet acknowledged its verdict.
    // Even a synthetic click must never issue SCENE, RESET or Save then.
    window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2',
      {detail:{state:'PRÊT'}}));
    assert(!btn.hidden&&btn.disabled,
      'pending native mission outcome must disable A4 scene selection');
    for(const id of ['projectActivity','projectOpen','projectSave','projectSaveAs'])
      assert(elements[id].disabled,'file operation unlocked before mission verdict: '+id);
    assert(editWouldBeBlocked(),
      'stale READY unlocked Blockly editing before native verdict');
    // Model a pupil edit only when the editor actually permits it.
    if(!editWouldBeBlocked()) workspace.state.blocks.push('unverified edit');
    assert.equal(manager.bytes(),bytes,'pending verdict allowed a student block edit');
    btn.handlers.click();await flush();
    assert.equal(backendCalls.length,0,'pending outcome switched Webots scene');
    assert.equal(resetCalls,0,'pending outcome issued native RESET');
    assert.equal(saveWrites,0,'pending outcome wrote a project file');
    assert.equal(manager.bytes(),bytes,'pending outcome altered pupil .wbb');
    assert.equal(diagnostics.length,0,'pending scene click should be ignored, not fail native');
    // Native adjudication finishes AFTER its terminal status event. Without
    // the explicit settled notification Blockly would remain read-only.
    control.setOutcomePending(false);
    window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2-outcome-settled'));
    assert(!editWouldBeBlocked(),'Blockly stayed locked after native verdict settled');
    assert(!btn.disabled,'scene selector stayed locked after native verdict settled');
    assert.equal(manager.bytes(),bytes,'settled verdict mutated student project');
    return {kind:'pending-verdict',status:'PASS'};
  }
  assert(!btn.hidden&&!btn.disabled,'A4 toggle must be enabled after native initialization');
  assert.match(btn.textContent,firstLabel);
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2',{detail:{state:'EXÉCUTION'}}));
  assert(btn.disabled,'active flight must prevent scene changes');
  assert(editWouldBeBlocked(),'active flight must prevent Blockly editing');
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2',{detail:{state:'PRÊT'}}));
  assert(!btn.disabled,'completed flight state should re-enable A4 selection');
  assert(!editWouldBeBlocked(),'editor must unlock after native completion');

  // Native SCENE_OK is the linearization point: never show B before ACK.
  holdAck=true;btn.handlers.click();await flush();
  assert.equal(backendCalls.length,1);
  assert.equal(backendCalls[0].scene,nextScene);
  assert.match(btn.textContent,firstLabel,'variant was displayed before native ACK');
  assert(btn.disabled,'scene selection must serialize with project operations');
  assert.equal(manager.bytes(),bytes);
  assert(resolveAck,'native ACK was not awaited');
  holdAck=false;resolveAck();await flush();
  assert.match(btn.textContent,nextLabel);
  assert.equal(manager.bytes(),bytes,'A/B scene choice must never alter .wbb');
  assert.equal(saveWrites,0,'A/B scene choice must never auto-save');

  btn.handlers.click();await flush();
  assert.equal(backendCalls[1].scene,firstScene);
  assert.match(btn.textContent,firstLabel);
  assert.equal(manager.bytes(),bytes);

  // A missing/invalid native ACK must fail closed, keep the last profile,
  // not change a single project byte, and not create a Save operation.
  failNext=true;btn.handlers.click();await flush();
  assert.equal(backendCalls[2].scene,nextScene);
  assert.match(btn.textContent,firstLabel);
  assert.match(elements.projectFileState.textContent,/Impossible de changer de parcours/);
  assert(diagnostics.some(s=>s.includes('NATIVE_SCENE_ACK_REJECT')));
  assert.equal(manager.bytes(),bytes);
  assert.equal(saveWrites,0);
  assert(clearBreakpoints>=2,'scene change failed to clear stale debug positions');
  return {kind:'public-A4',status:'PASS',nativeRequests:backendCalls.length};
}
(async()=>{
  assert.match(mainSrc,/runtimeOutcomePending = false;\s*\/\/ The terminal status is emitted before this flag clears; notify the\s*\/\/ project UI so it can restore Blockly editing only after adjudication\.\s*window\.dispatchEvent\(new CustomEvent\('webeeblocks-runtime-v2-outcome-settled'\)\)/,
    'runProgram finally must notify project UI after native verdict');
  assert.equal(Activities.DOCUMENT.activities.filter(p=>p.id==='progression-decision-h-v1').length,1);
  assert.deepEqual(Activities.DOCUMENT.activities.filter(p=>p.id.startsWith('progression-')&&
    p.starterVisible!==false).length,8);
  const a4=await scenario('progression-decision-h-v1');
  const pending=await scenario('progression-decision-h-v1',{outcomePending:true});
  const mini=await scenario('progression-mini-grand-prix-v1');
  const miniPending=await scenario('progression-mini-grand-prix-v1',{outcomePending:true});
  const a4Fallback=await scenario('progression-decision-h-v1',{outcomePending:true,noReadOnlyApi:true});
  const a7Fallback=await scenario('progression-mini-grand-prix-v1',{outcomePending:true,noReadOnlyApi:true});
  const other=await scenario('progression-sequence-v1');
  const foreignNoStarter=await scenario('progression-decision-h-v1',
    {worldOverride:'worlds/unpublished-school.wbt'});
  const foreignPublished=await scenario('progression-decision-h-v1',
    {worldOverride:'worlds/ci-foreign-classroom.wbt'});
  console.log('PASS A4/A7 public variant session UI:',a4.status,pending.status,mini.status,miniPending.status,a4Fallback.status,a7Fallback.status,other.status,
    'nonce ACK needed, pending outcome locked, no .wbb change, no autosave, failure fail-closed');
  assert.equal(foreignNoStarter.status,'PASS');
  assert.equal(foreignPublished.status,'PASS');
  console.log('PASS world-specific activity picker: unknown world disabled; foreign world offers only its own published starter');
})().catch(error=>{console.error(error);process.exitCode=1});
