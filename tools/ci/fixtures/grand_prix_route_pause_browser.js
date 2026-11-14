/* TEST-ONLY: appended to a temporary byte-identical Grand Prix Route HTML copy.
 * Uses the real Webots RobotWindow, real Blockly interpreter/debug controls,
 * production route backend, native clock and real flight controller.
 * Never loaded from the shipped route UI; never supplies native success.
 */
(function () {
  'use strict';
  const endpoint = 'http://127.0.0.1:__TRACE_PORT__/trace';
  // This build-time replacement applies only to the temporary CI page, never
  // the shipped student UI. The second native run deliberately loses Chrome.
  const nativeWindowLossProbe = '__WINDOW_LOSS_MODE__' === 'true';
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  function record(stage, value) {
    const event = JSON.stringify({schema:'gp-route-native-pause-browser-v1',
      stage, wall_ms:Math.round(performance.now()), value:value===undefined?null:value});
    fetch(endpoint, {method:'POST',mode:'no-cors',headers:{'Content-Type':'text/plain'},
      body:event,keepalive:true}).catch(()=>{});
  }
  async function until(check, limitMs, failure) {
    const stop=Date.now()+limitMs;
    while(Date.now()<stop) {
      const value=check();
      if(value) return value;
      await delay(100);
    }
    throw Error(failure || 'BROWSER_PROBE_TIMEOUT');
  }
  let pauseCount=0;
  let resumeCount=0;
  let nativePauseCount=0;
  let nativeResumeCount=0;
  let takeoffRequestId=null;
  let resetRequestId=null,resetStarted=false,resetDiagnostic=null;
  window.addEventListener('webeeblocks-debug-paused', function() {
    pauseCount++;
    record('UI_PAUSED',pauseCount);
  });
  window.addEventListener('webeeblocks-debug-resumed', function() {
    resumeCount++;
    record('UI_RESUMED',resumeCount);
  });
  async function experiment() {
    await until(()=>window.runtimeBackend && window.runtimeBackend.ready &&
      window.runtimeDebug && window.workspace &&
      document.getElementById('runtimeState').textContent==='PRÊT',65000,
      'REAL_GRAND_PRIX_BROWSER_NOT_READY');
    record('REAL_UI_READY', {nativePauseGated:window.runtimeDebug.nativePauseGated,
      activity:window.runtimeProfile && window.runtimeProfile.id});
    if(!window.runtimeDebug.nativePauseGated ||
       window.runtimeProfile.id!=='progression-grand-prix-route-v2')
      throw Error('ROUTE_NATIVE_DEBUG_NOT_BOUND');
    const backend=window.runtimeBackend;
    const realSend=backend.robotWindow.send.bind(backend.robotWindow);
    backend.robotWindow.send=function(message) {
      const m=typeof message==='string' &&
        /^WEBEEBLOCKS_RUNTIME_V2 REQUEST ([1-9][0-9]*) TAKEOFF(?:\s|$)/.exec(message);
      if(m) {
        takeoffRequestId=Number(m[1]);
        record('TAKEOFF_REQUEST_SENT', {id:takeoffRequestId,
          pendingBeforeSend:!!backend.pending[takeoffRequestId]});
      }
      const reset=typeof message==='string' &&
        /^WEBEEBLOCKS_RUNTIME_V2 REQUEST ([1-9][0-9]*) RESET(?:\s|$)/.exec(message);
      if(reset) {
        resetRequestId=Number(reset[1]);
        record('RESET_NATIVE_REQUEST_SENT', {id:resetRequestId,
          pendingBeforeSend:!!backend.pending[resetRequestId]});
      }
      return realSend(message);
    };
    const original=backend.handleMessage.bind(backend);
    backend.handleMessage=function(message) {
      const reply=typeof message==='string' &&
        /^WEBEEBLOCKS_RUNTIME_V2 RESPONSE ([1-9][0-9]*) (OK|ERR\b.*)/.exec(message);
      if(reply && Number(reply[1])===takeoffRequestId) {
        record('TAKEOFF_NATIVE_RESPONSE_RECEIVED', {id:takeoffRequestId,
          raw:message.slice(0,240),pendingAtArrival:!!backend.pending[takeoffRequestId],
          runtimeRunning:window.runtimeRunning===true});
      }
      if(reply && resetRequestId!==null && Number(reply[1])===resetRequestId) {
        record('RESET_NATIVE_RESPONSE_RECEIVED', {id:resetRequestId,
          raw:message.slice(0,240),pendingAtArrival:!!backend.pending[resetRequestId]});
      }
      if(typeof message==='string' && message.indexOf('GP_ROUTE_PAUSE_V1 ')===0) {
        const m=/^GP_ROUTE_PAUSE_V1 (PAUSED|RESUMED) nonce=([0-9a-f]{32}) attempt=([1-9][0-9]*) seq=([1-9][0-9]*)$/.exec(message);
        if(!m) record('NATIVE_MALFORMED_ACK',message);
        else if(m[1]==='PAUSED') {
          nativePauseCount++;record('NATIVE_PAUSED',message);
        } else {
          nativeResumeCount++;record('NATIVE_RESUMED',message);
        }
      }
      return original(message);
    };
    window.addEventListener('webeeblocks-runtime-v2-diagnostic', function(event) {
      if(!resetStarted)return;
      const detail=event&&event.detail||{};
      resetDiagnostic={studentState:detail.studentState||null,
        machineCode:detail.machineCode||null,
        technicalMessage:detail.technicalMessage||null};
      record('RESET_UI_DIAGNOSTIC',resetDiagnostic);
    });
    function resetSnapshot(button) {
      return {runtimeState:document.getElementById('runtimeState').textContent,
        debugState:document.getElementById('debugState').textContent,
        runtimeRunning:window.runtimeRunning===true,
        runtimeTerminal:window.runtimeTerminal===true,
        runtimeResetPending:window.runtimeResetPending===true,
        runtimeStopPending:window.runtimeStopPending===true,
        runtimeOutcomePending:window.runtimeOutcomePending===true,
        backendReady:backend.ready===true,
        backendSimulationStopped:backend.simulationStopped===true,
        resetDisabled:button.disabled,resetHidden:button.hidden,
        pendingIds:Object.keys(backend.pending||{}),resetRequestId};
    }
    const root=window.workspace;
    root.clear();
    const takeoff=root.newBlock('webeeblocks_v2_takeoff');
    const height=root.newBlock('math_number');
    height.setFieldValue('0.4','NUM');
    takeoff.getInput('HEIGHT').connection.connect(height.outputConnection);
    const speed=root.newBlock('webeeblocks_v2_speed');
    const land=root.newBlock('webeeblocks_v2_land');
    takeoff.nextConnection.connect(speed.previousConnection);
    speed.nextConnection.connect(land.previousConnection);
    for(const block of [takeoff,height,speed,land]) {
      block.initSvg();block.render();
    }
    document.getElementById('stepMode').checked=true;
    record('BLOCKLY_PROGRAM_BUILT', {blocks:root.getAllBlocks(false).map(b=>b.type)});
    document.getElementById('submit').click();
    await until(()=>pauseCount===1 && nativePauseCount===1,75000,
      'FIRST_NATIVE_PAUSE_BEFORE_TAKEOFF_NOT_ACKED');
    if(window.runtimeRunning!==true || window.runtimeDebug.waiter.ready!==true)
      throw Error('FIRST_PAUSE_NOT_GATED');
    record('BEFORE_TAKEOFF_PAUSED');
    await delay(1350); // Wall time passes while physics must remain frozen.
    document.getElementById('stepNext').click();
    await until(()=>nativeResumeCount===1 && resumeCount===1,65000,
      'FIRST_NATIVE_POSITIVE_STEP_RESUME_MISSING');
    record('BEFORE_TAKEOFF_RESUMED');
    // The 35 s UI request budget is separate from the 210 s Webots mission
    // clock. If the interpreter fails, retain a short observation window for
    // any *late* native TAKEOFF ACK before refusing the missing second pause.
    let terminalSince=null;
    await until(()=>{
      if(pauseCount===2 && nativePauseCount===2)return true;
      if(window.runtimeRunning!==true){
        if(terminalSince===null){
          terminalSince=Date.now();
          record('PROGRAM_ENDED_BEFORE_SECOND_PAUSE', {
            runtimeState:document.getElementById('runtimeState').textContent,
            debugState:document.getElementById('debugState').textContent,
            requestId:takeoffRequestId,
            requestPending:takeoffRequestId!==null && !!backend.pending[takeoffRequestId],
            nativePauseCount,nativeResumeCount});
        }
        if(Date.now()-terminalSince>=22000){
          record('TAKEOFF_ACK_DIAGNOSTIC_CLOSED', {
            requestId:takeoffRequestId,
            requestPending:takeoffRequestId!==null && !!backend.pending[takeoffRequestId],
            runtimeState:document.getElementById('runtimeState').textContent});
          throw Error('PROGRAM_ENDED_WITHOUT_SECOND_NATIVE_PAUSE');
        }
      }
      return false;
    },90000,'INFLIGHT_NATIVE_PAUSE_NOT_ACKED');
    if(nativeWindowLossProbe) {
      // Host CI will terminate the *actual* Chrome process after this fsynced
      // event. No synthetic STOP, RESUME, PING loss or controller hook is sent.
      // The native 15s wall-clock watchdog must unpause and LAND independently.
      record('NATIVE_WINDOW_LOSS_READY', {
        nativePauseCount,nativeResumeCount,
        runtimeRunning:window.runtimeRunning===true,
        paused:window.runtimeDebug.waiter &&
          window.runtimeDebug.waiter.ready===true
      });
      return; // Keep the live native PAUSE and browser heartbeat until killed.
    }
    const elapsedA=await backend.readElapsedTime();
    record('FROZEN_CLOCK_START',elapsedA);
    await delay(1600);
    const elapsedB=await backend.readElapsedTime();
    record('FROZEN_CLOCK_END',elapsedB);
    if(!Number.isFinite(elapsedA)||elapsedA<0||
       elapsedB!==elapsedA) throw Error('NATIVE_CLOCK_MOVED_WHILE_PAUSED');
    if(window.runtimeDebug.waiter.ready!==true)
      throw Error('UI_PAUSE_NOT_READY');
    document.getElementById('stepNext').click();
    await until(()=>nativeResumeCount===2 && resumeCount===2,65000,
      'SECOND_NATIVE_RESUME_AFTER_POSITIVE_STEP_MISSING');
    record('INFLIGHT_RESUMED');
    await until(()=>pauseCount===3 && nativePauseCount===3,120000,
      'SECOND_INFLIGHT_PAUSE_NOT_ACKED');
    record('STOP_WHILE_TRULY_PAUSED');
    document.getElementById('submit').click(); // Real STOP, not synthetic RESUME.
    await until(()=>window.runtimeRunning===false,120000,
      'STOP_DID_NOT_RELEASE_INTERPRETER');
    record('STOP_RELEASED',{runtimeState:document.getElementById('runtimeState').textContent,
      resumeCount, nativeResumeCount});
    if(nativeResumeCount!==2)throw Error('STOP_WRONGLY_RESUMED_BLOCKLY');
    // Strict UI RESET: never bypass the normal landing precondition.
    const resetButton=document.getElementById('resetSimulation');
    await until(()=>!resetButton.disabled && !resetButton.hidden,120000,
      'RESET_NOT_OFFERED_AFTER_STOP');
    // The native STOP ACK is not a touchdown certificate. Do not submit
    // RESET immediately against a still-descending Crazyflie; allow the
    // unchanged native controller to finish its own ground confirmation.
    await delay(45000);
    record('RESET_BEFORE_CLICK',resetSnapshot(resetButton));
    if(resetButton.disabled||resetButton.hidden)
      throw Error('RESET_BECAME_UNAVAILABLE_BEFORE_CLICK');
    let resetObserved=false,resetBackendError=null;
    const realReset=backend.resetSimulation.bind(backend);
    backend.resetSimulation=function() {
      record('RESET_BACKEND_INVOKED',resetSnapshot(resetButton));
      let task;
      try {task=realReset();}
      catch(error) {
        resetBackendError={code:error&&error.code||null,message:String(error)};
        record('RESET_BACKEND_SYNC_ERROR',resetBackendError);
        throw error;
      }
      return task.then(function(value) {
        record('RESET_BACKEND_RESOLVED',resetSnapshot(resetButton));return value;
      },function(error) {
        resetBackendError={code:error&&error.code||null,
          message:error&&error.message||String(error)};
        record('RESET_BACKEND_REJECTED',resetBackendError);
        throw error;
      });
    };
    window.addEventListener('webeeblocks-runtime-v2-reset',()=>{resetObserved=true;},{once:true});
    resetStarted=true;
    resetButton.click();
    record('RESET_CLICKED',resetSnapshot(resetButton));
    await until(()=>{
      if(resetObserved)return true;
      if(resetBackendError||resetDiagnostic) {
        record('RESET_REFUTED', {backendError:resetBackendError,
          uiDiagnostic:resetDiagnostic,state:resetSnapshot(resetButton)});
        throw Error('NATIVE_STRICT_RESET_REJECTED');
      }
      return false;
    },180000,'NATIVE_STRICT_RESET_NOT_CONFIRMED');
    record('RESET_CONFIRMED',{state:document.getElementById('runtimeState').textContent,
      nativeResumeCount});
    if(document.getElementById('runtimeState').textContent!=='PRÊT')
      throw Error('RESET_NOT_READY');
    record('PASS');
  }
  experiment().catch(function(error) {
    record('FAIL',{message:String(error),stack:String(error.stack||'').slice(0,1600)});
  });
})();
