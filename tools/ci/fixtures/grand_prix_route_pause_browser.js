/* TEST-ONLY: appended to a temporary byte-identical Grand Prix Route HTML copy.
 * Uses the real Webots RobotWindow, real Blockly interpreter/debug controls,
 * production route backend, native clock and real flight controller.
 * Never loaded from the shipped route UI; never supplies native success.
 */
(function () {
  'use strict';
  const endpoint = 'http://127.0.0.1:__TRACE_PORT__/trace';
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
    const original=backend.handleMessage.bind(backend);
    backend.handleMessage=function(message) {
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
    await until(()=>pauseCount===2 && nativePauseCount===2,300000,
      'INFLIGHT_NATIVE_PAUSE_NOT_ACKED');
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
    let resetObserved=false;
    window.addEventListener('webeeblocks-runtime-v2-reset',()=>{resetObserved=true;},{once:true});
    resetButton.click();
    await until(()=>resetObserved,180000,'NATIVE_STRICT_RESET_NOT_CONFIRMED');
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
