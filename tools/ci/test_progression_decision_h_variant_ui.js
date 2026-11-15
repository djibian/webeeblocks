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
  const workspace={state:{blocks:['students work',42]},isReadOnly:()=>false,
    setIsReadOnly(){}};
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
  new Function(...Object.keys(inputs),src)(...Object.values(inputs));
  assert(callbacks.load?.length===1,'actual project UI did not subscribe to window load');
  callbacks.load[0]();await flush();
  assert(manager,'real project UI did not initialize its file manager');
  const btn=elements.activityVariant;
  assert(typeof btn.handlers.click==='function','real A4 toggle was not bound');
  const bytes=manager.bytes();

  if(startProfileId!=='progression-decision-h-v1'){
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
    btn.handlers.click();await flush();
    assert.equal(backendCalls.length,0,'pending outcome switched Webots scene');
    assert.equal(resetCalls,0,'pending outcome issued native RESET');
    assert.equal(saveWrites,0,'pending outcome wrote a project file');
    assert.equal(manager.bytes(),bytes,'pending outcome altered pupil .wbb');
    assert.equal(diagnostics.length,0,'pending scene click should be ignored, not fail native');
    return {kind:'pending-verdict',status:'PASS'};
  }
  assert(!btn.hidden&&!btn.disabled,'A4 toggle must be enabled after native initialization');
  assert.match(btn.textContent,/Parcours A/);
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2',{detail:{state:'EXÉCUTION'}}));
  assert(btn.disabled,'active flight must prevent scene changes');
  window.dispatchEvent(new CustomEvent('webeeblocks-runtime-v2',{detail:{state:'PRÊT'}}));
  assert(!btn.disabled,'completed flight state should re-enable A4 selection');

  // Native SCENE_OK is the linearization point: never show B before ACK.
  holdAck=true;btn.handlers.click();await flush();
  assert.equal(backendCalls.length,1);
  assert.equal(backendCalls[0].scene,'decision-h-b-v1');
  assert.match(btn.textContent,/Parcours A/,'A4 B was displayed before native ACK');
  assert(btn.disabled,'scene selection must serialize with project operations');
  assert.equal(manager.bytes(),bytes);
  assert(resolveAck,'native ACK was not awaited');
  holdAck=false;resolveAck();await flush();
  assert.match(btn.textContent,/Parcours B/);
  assert.equal(manager.bytes(),bytes,'A/B scene choice must never alter .wbb');
  assert.equal(saveWrites,0,'A/B scene choice must never auto-save');

  btn.handlers.click();await flush();
  assert.equal(backendCalls[1].scene,'decision-h-a-v1');
  assert.match(btn.textContent,/Parcours A/);
  assert.equal(manager.bytes(),bytes);

  // A missing/invalid native ACK must fail closed, keep the last profile,
  // not change a single project byte, and not create a Save operation.
  failNext=true;btn.handlers.click();await flush();
  assert.equal(backendCalls[2].scene,'decision-h-b-v1');
  assert.match(btn.textContent,/Parcours A/);
  assert.match(elements.projectFileState.textContent,/Impossible de changer de parcours/);
  assert(diagnostics.some(s=>s.includes('NATIVE_SCENE_ACK_REJECT')));
  assert.equal(manager.bytes(),bytes);
  assert.equal(saveWrites,0);
  assert(clearBreakpoints>=2,'scene change failed to clear stale debug positions');
  return {kind:'public-A4',status:'PASS',nativeRequests:backendCalls.length};
}
(async()=>{
  assert.equal(Activities.DOCUMENT.activities.filter(p=>p.id==='progression-decision-h-v1').length,1);
  assert.deepEqual(Activities.DOCUMENT.activities.filter(p=>p.id.startsWith('progression-')&&
    p.starterVisible!==false).length,8);
  const a4=await scenario('progression-decision-h-v1');
  const pending=await scenario('progression-decision-h-v1',{outcomePending:true});
  const other=await scenario('progression-sequence-v1');
  console.log('PASS A4 public A/B session UI:',a4.status,pending.status,other.status,
    'nonce ACK needed, pending outcome locked, no .wbb change, no autosave, failure fail-closed');
})().catch(error=>{console.error(error);process.exitCode=1});
