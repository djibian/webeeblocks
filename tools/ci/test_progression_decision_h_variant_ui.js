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
  const inputs={window,document,CustomEvent,Blockly,workspace,
    robotWindow:{send(){},receive(){}},runtimeProfile:Activities.getProfile(startProfileId),
    runtimeBackend,WebeeBlocksProjectFiles,WebeeBlocksActivityProfiles:Profiles,
    WebeeBlocksActivities:Activities,WebeeBlocksSemanticAst:{},
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
    '\nreturn {setOutcomePending(value){runtimeOutcomePending=value;}};')(...Object.values(inputs));
  assert(callbacks.load?.length===1,'actual project UI did not subscribe to window load');
  callbacks.load[0]();await flush();
  assert(manager,'real project UI did not initialize its file manager');
  const btn=elements.activityVariant;
  assert(typeof btn.handlers.click==='function','real A4 toggle was not bound');
  const selectable = Activities.DOCUMENT.activities.filter(a=>
    a.id.startsWith('progression-') && a.starterVisible!==false &&
    a.world===Activities.getProfile(startProfileId).world);
  assert.equal(elements.projectActivity.disabled,
    options.outcomePending===true || selectable.length===0,
    'Start activity must be disabled while locked or when all starters belong to another Webots world');
  if(selectable.length===0)
    assert.match(elements.projectActivity.title,/Aucune activité disponible dans ce monde/);
  const bytes=manager.bytes();
  if(!options.outcomePending)
    assert(!editWouldBeBlocked(),'pupil must be able to edit while READY');
  const mini=startProfileId==='progression-mini-grand-prix-v1';
  const count=startProfileId==='progression-count-h-v1';
  const scenes=count?['count-h-1-v1','count-h-2-v1','count-h-3-v1']:
    mini?['mini-grand-prix-l-v1','mini-grand-prix-r-v1']:
      ['decision-h-a-v1','decision-h-b-v1'];
  const labels=count?[/Parcours A/,/Parcours B/,/Parcours C/]:
    mini?[/Parcours gauche/,/Parcours droite/]:[/Parcours A/,/Parcours B/];
  const [firstScene,nextScene]=scenes;
  const [firstLabel,nextLabel]=labels;

  if(startProfileId!=='progression-decision-h-v1' && !mini && !count){
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
  if(count) assert.doesNotMatch(btn.textContent,/\b[123]\s*H\b/,
    'A6 pupil variant button must never disclose number of H');
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
  if(count) {
    assert.doesNotMatch(btn.textContent,/\b[123]\s*H\b/,
      'A6 changed-scene label disclosed number of H');
    assert.doesNotMatch(elements.projectFileState.textContent,/\b[123]\s*H\b/,
      'A6 project-status message disclosed number of H');
  }
  assert.equal(manager.bytes(),bytes,'A/B scene choice must never alter .wbb');
  assert.equal(saveWrites,0,'A/B scene choice must never auto-save');

  btn.handlers.click();await flush();
  const secondIndex=2%scenes.length;
  assert.equal(backendCalls[1].scene,scenes[secondIndex]);
  assert.match(btn.textContent,labels[secondIndex]);
  if(count) {
    assert.doesNotMatch(btn.textContent,/\b[123]\s*H\b/,
      'A6 third-variant label disclosed number of H');
    assert.doesNotMatch(elements.projectFileState.textContent,/\b[123]\s*H\b/,
      'A6 third-variant status disclosed number of H');
  }
  assert.equal(manager.bytes(),bytes);

  // A missing/invalid native ACK must fail closed, keep the last profile,
  // not change a single project byte, and not create a Save operation.
  failNext=true;btn.handlers.click();await flush();
  assert.equal(backendCalls[2].scene,scenes[(secondIndex+1)%scenes.length]);
  assert.match(btn.textContent,labels[secondIndex]);
  if(count) {
    assert.doesNotMatch(btn.textContent,/\b[123]\s*H\b/,
      'A6 third-variant label disclosed number of H');
    assert.doesNotMatch(elements.projectFileState.textContent,/\b[123]\s*H\b/,
      'A6 third-variant status disclosed number of H');
  }
  assert.match(elements.projectFileState.textContent,/Impossible de changer de parcours/);
  assert(diagnostics.some(s=>s.includes('NATIVE_SCENE_ACK_REJECT')));
  assert.equal(manager.bytes(),bytes);
  assert.equal(saveWrites,0);
  assert(clearBreakpoints>=2,'scene change failed to clear stale debug positions');
  return {kind:count?'draft-A6':mini?'public-A7':'public-A4',
    status:'PASS',nativeRequests:backendCalls.length};
}
(async()=>{
  // Evaluate the actual picker selection function, not a duplicated filter.
  const start=src.indexOf('  function progressionProfiles() {');
  const end=src.indexOf('\n  function chooseActivityProfile() {',start);
  assert(start>=0&&end>start,'actual chooser source was not found');
  const realPicker=new Function('WebeeBlocksActivities','runtimeProfile',
    src.slice(start,end)+'\nreturn progressionProfiles();');
  const regular=Activities.getProfile('progression-sequence-v1');
  const school=Activities.getProfile('progression-count-h-v1');
  assert.equal(realPicker(Activities,regular).length,8,
    'ordinary classroom must retain all eight currently published starters');
  assert.deepEqual(realPicker(Activities,school),[],
    'hidden A6 Draft must not offer starters from the ordinary classroom world');
  const future=JSON.parse(JSON.stringify(Activities.DOCUMENT));
  future.activities.find(p=>p.id===school.id).starterVisible=true;
  assert.deepEqual(realPicker({DOCUMENT:future},school).map(p=>p.id),[school.id],
    'when A6 is explicitly published, Start must offer only its own school-world project');
  assert.equal(realPicker({DOCUMENT:future},regular).some(p=>p.id===school.id),false,
    'publishing A6 must not leak that starter into ordinary Webots scenes');
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
  const a6=await scenario('progression-count-h-v1');
  const a6Pending=await scenario('progression-count-h-v1',{outcomePending:true});
  const a6Fallback=await scenario('progression-count-h-v1',{outcomePending:true,noReadOnlyApi:true});
  const other=await scenario('progression-sequence-v1');
  console.log('PASS A4/A7 and hidden draft A6 variant session UI:',
    a4.status,pending.status,mini.status,miniPending.status,
    a4Fallback.status,a7Fallback.status,a6.status,a6Pending.status,a6Fallback.status,
    other.status,'two/three-world cycling, nonce ACK, pending outcome locked, unchanged .wbb, no autosave, rejection fail-closed');
})().catch(error=>{console.error(error);process.exitCode=1});
