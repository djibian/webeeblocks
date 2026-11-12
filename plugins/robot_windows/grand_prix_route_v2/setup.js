/* Isolated variable-course UI profile; no variable world/evaluator is activated by this file. */
(function(){
'use strict';
const A=window.WebeeBlocksActivities;
const profile={id:'progression-grand-prix-route-v2',world:'worlds/grand_prix_route_v2.wbt',
 brief:{visible:true,title:'Grand Prix — parcours variables (expérimental)',mission:'Explore un parcours à trois segments de 2, 2,5 ou 3 m, avec deux virages indépendants à gauche ou à droite et des coins physiques en L détectables par les capteurs. Observe la scène et les distances, construis et corrige librement ton programme. Franchis les H ouverts dans le bon sens et reste au-dessus de la limite basse hors des bandes jaunes. Devant le H terminal fermé, pose-toi au centre après un H, à 50 cm à gauche après deux, à 50 cm à droite après trois. Sortie de piste, collision, mauvaise pose ou dépassement de 210 secondes Webots : échec irréversible et atterrissage indépendant. Les variantes et leur qualification restent expérimentales.'},
 pedagogy:{objective:'Combiner perceptions, variables, comptage orienté et boucles conditionnelles dans un parcours autonome.'},
 toolbox:['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_vertical','webeeblocks_v2_turn','webeeblocks_v2_speed','webeeblocks_v2_range','controls_if','controls_repeat_ext','procedures_defnoreturn','procedures_callnoreturn','webeeblocks_v2_until','math_number','math_arithmetic','logic_compare','logic_operation','variables_set','variables_get','math_change','webeeblocks_v2_land'],
 parameterBounds:{math_number:{NUM:{min:-1000,max:1000,step:.01}},webeeblocks_v2_turn:{ANGLE:{min:1,max:179,step:1}},webeeblocks_v2_speed:{SPEED:{min:.1,max:.35,step:.05}}},
 fieldOptions:{webeeblocks_v2_move:{DIRECTION:['forward','back','left','right']},webeeblocks_v2_range:{DIRECTION:['front','back','left','right']},math_arithmetic:{OP:['ADD','MINUS','MULTIPLY','DIVIDE']}},
 hardware:['crazyflie-2.1','flow-deck-v2','multi-ranger-deck'],timer:{enabled:true},evaluation:{type:'mission-state-v1',oracle:'grand-prix-route-v2'},
 runtime:{mode:'ast-v1',maxSteps:20000,allowedStatementKinds:['takeoff','move','vertical','turn','set_speed','if','repeat','call','while','set_variable','land'],rangeDirections:['front','back','left','right'],moveDirections:['forward','back','left','right'],verticalDirections:['up','down'],astBounds:{'takeoff.height_m':{min:.3,max:1.0},'move.distance_m':{min:.01,max:1.9},'move.forward.distance_m':{min:.01,max:1.9},'move.lateral.distance_m':{min:.01,max:.6},'vertical.distance_m':{min:.1,max:.5},'set_speed.speed_m_s':{min:.1,max:.35},'repeat.count':{min:1,max:20},'while.max_iterations':{min:1,max:100}}}
};
if(A.BLOCK_CATALOG.controls_whileUntil){profile.toolbox.push('controls_whileUntil');}
if(A.BLOCK_CATALOG.webeeblocks_v2_elapsed){profile.toolbox.push('webeeblocks_v2_elapsed');profile.runtime.elapsedSimulationTime=true;}
window.WebeeBlocksActivities={BLOCK_CATALOG:A.BLOCK_CATALOG,DOCUMENT:{version:1,activities:[profile]},getProfile:id=>{if(id!==profile.id)throw new Error('unknown variable Grand Prix activity');return JSON.parse(JSON.stringify(profile));}};
window.WebeeBlocksInitialActivityId=profile.id;
const inject=Blockly.inject;
Blockly.inject=function(element,options){return inject(element,Object.assign({},options,{media:'../blockly_v2/vendor/media/'}));};
const OriginalBackend=WebeeBlocksWwiBackend;
window.WebeeBlocksWwiBackend=function(robotWindow,options){
 // A stale localhost cache can serve another 200/JS asset in place of
 // activity_contract.js. Runtime READY alone must not enable a pupil flight.
 const contract=window.WebeeBlocksActivityContract;
 if (!contract || typeof contract.execute!=='function' ||
     typeof contract.preflightWorkspace!=='function' ||
     typeof contract.applyFieldBounds!=='function') {
  const error=new Error('Module Blockly activity_contract.js absent ou invalide : vérifier le cache et le paquet Grand Prix.');
  error.code='BLOCKLY_ASSET_MISMATCH';
  throw error;
 }
 const backend=new OriginalBackend(robotWindow,
   Object.assign({},options,{simulationScenes:false,simulationAdmission:true}));
 // Only this simulated Grand Prix host recognizes read-only clock notifications.
 // They are never Runtime v2 responses, commands, mission outcomes or flight data.
 if (backend && typeof backend.handleMessage==='function') {
  const receive=backend.handleMessage.bind(backend);
  backend.handleMessage=function(message) {
   if (typeof message==='string' && message.indexOf('GP_ROUTE_CLOCK_V1 ')===0) {
    window.dispatchEvent(new CustomEvent('webeeblocks-route-native-clock',{detail:{raw:message}}));
    return true;
   }
   return receive(message);
  };
 }
 return backend;
};
const originalOutcome=window.WebeeBlocksRuntimeOutcome;
window.WebeeBlocksRuntimeOutcome=Object.assign({},originalOutcome,{
 classify(error){return error&&error.code==='TIME_LIMIT'?{state:'ARRÊTÉ',detail:'Vol interrompu — résultat de mission non confirmé',machineCode:'TIME_LIMIT'}:originalOutcome.classify(error);}
});
// This isolated profile makes a real unexpected GUI error observable on the
// existing debug row. Runtime/mission verdicts and the generic pupil status
// remain unchanged; the deferred write runs after the interpreter's onFinish.
if (typeof window.addEventListener === 'function') {
 window.addEventListener('webeeblocks-runtime-v2-diagnostic', function(event) {
  const detail = event && event.detail;
  if (!detail || detail.studentState !== 'ERREUR') return;
  const code = typeof detail.machineCode === 'string'
    ? detail.machineCode.replace(/\s+/g, ' ').trim().slice(0, 40) : '';
  const message = typeof detail.technicalMessage === 'string'
    ? detail.technicalMessage.replace(/\s+/g, ' ').trim().slice(0, 240) : '';
  const diagnostic = 'Diagnostic : ' + (code ? code + ' — ' : '') +
    (message || 'erreur technique sans message');
  Promise.resolve().then(function() {
   const state = document.getElementById('runtimeState');
   const output = document.getElementById('debugState');
   if (state && state.textContent === 'ERREUR' && output)
    output.textContent = diagnostic;
  });
 });
}

// Read-only Grand Prix route clock. The native ELAPSED command observes Webots
// time since admitted TAKEOFF; it is never an outcome, oracle or deadline source.
(function installRouteClock() {
  if (typeof window.addEventListener !== 'function') return;
  var element = null, interval = null, generation = 0;
  var running = false, pending = false, last = null;
  // Per-run unpredictable nonce: a delayed notification from an earlier
  // STOP/RESET/attempt must never be attached to a new student run.
  var clockNonce = null, clockAttempt = null;
  function newNonce() {
    if (!window.crypto || typeof window.crypto.getRandomValues!=='function') return null;
    var raw=new Uint8Array(16);window.crypto.getRandomValues(raw);
    return Array.from(raw,function(n){return n.toString(16).padStart(2,'0');}).join('');
  }
  function subscribe() {
    if (!running || !clockNonce || clockAttempt!==null) return;
    var backend=window.runtimeBackend;
    if (!backend || !backend.ready || !backend.robotWindow ||
        typeof backend.robotWindow.send!=='function') return;
    backend.robotWindow.send('GP_ROUTE_CLOCK_V1 SUBSCRIBE nonce='+clockNonce);
  }
  function mount() {
    if (!element && typeof document !== 'undefined' && document &&
        typeof document.getElementById === 'function' &&
        typeof document.createElement === 'function') {
      var panel = document.getElementById('observationReadouts');
      if (panel) {
        element = document.createElement('div');
        element.id = 'grandPrixElapsedClock';
        element.setAttribute('aria-live', 'off');
        element.style.fontVariantNumeric = 'tabular-nums';
        element.style.whiteSpace = 'nowrap';
        panel.appendChild(element);
      }
    }
    return !!element;
  }
  function format(seconds) {
    var whole = Math.floor(seconds + 1e-9); // Native Webots elapsed; never extrapolate from wall time.
    return String(Math.floor(whole / 60)).padStart(2, '0') + 'min ' +
      String(whole % 60).padStart(2, '0') + 's';
  }
  function face(value) { return format(value === null ? 0 : value) + ' / 03min 30s'; }
  function show(text) {
    if (mount()) element.textContent = text;
  }
  function empty() { show(face(null)); }
  function clear() {
    generation += 1;
    running = false;
    pending = false;
    if (interval !== null) window.clearInterval(interval);
    interval = null;
    clockNonce=null;clockAttempt=null;
  }
  function reset() {
    clear();
    last = null;
    empty();
  }
  function finish() {
    clear();
    show(face(last));
  }
  function sample() {
    // Once native ticks are bound, do not overwrite their per-simulation-second
    // cadence with slower one-second wall-clock observations.
    if (!running || pending || clockAttempt!==null) return;
    var backend = window.runtimeBackend;
    if (!backend || !backend.ready || typeof backend.readElapsedTime !== 'function') {
      if (last !== null) show(face(last));
      return;
    }
    var bound = generation;
    pending = true;
    Promise.resolve().then(function() { return backend.readElapsedTime(); }).then(function(seconds) {
      if (bound !== generation || !running) return;
      if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0 ||
          (last !== null && seconds < last)) {
        show(face(last));
        return;
      }
      last = seconds;
      show(face(seconds));
    }, function() {
      if (bound !== generation || !running) return;
      // TIME_UNAVAILABLE is expected before TAKEOFF completes and after LAND.
      show(face(last));
    }).finally(function() {
      if (bound === generation) pending = false;
    });
  }
  function start() {
    if (running) return;
    reset();
    running = true;
    clockNonce=newNonce();
    subscribe();
    sample();
    interval = window.setInterval(function() {
      subscribe();
      sample();
    }, 1000); // Bounded fallback while native subscription is unavailable.
  }
  window.addEventListener('webeeblocks-route-native-clock', function(event) {
    var raw=event && event.detail && event.detail.raw;
    if (!running || !clockNonce || typeof raw!=='string') return;
    var ack=/^GP_ROUTE_CLOCK_V1 ACK nonce=([0-9a-f]{32}) attempt=([1-9][0-9]*)$/.exec(raw);
    if (ack) {
      var attempt=Number(ack[2]);
      if (ack[1]===clockNonce && Number.isSafeInteger(attempt))
        clockAttempt=attempt;
      return;
    }
    var tick=/^GP_ROUTE_CLOCK_V1 TICK nonce=([0-9a-f]{32}) attempt=([1-9][0-9]*) seconds=(0|[1-9][0-9]*)$/.exec(raw);
    if (!tick || tick[1]!==clockNonce || clockAttempt===null ||
        Number(tick[2])!==clockAttempt) return;
    var second=Number(tick[3]);
    if (!Number.isSafeInteger(second) || second<0 || second>210 ||
        (last!==null && second<last)) return;
    last=second;
    show(face(second));
  });
  window.addEventListener('webeeblocks-ui-ready', empty);
  window.addEventListener('webeeblocks-runtime-v2', function(event) {
    var state = event && event.detail && event.detail.state;
    if (state === 'EXÉCUTION') start();
    else if (state === 'PRÊT' || state === 'INITIALISATION' || state === 'RÉINITIALISATION') reset();
    else if (state) finish();
  });
})();

})();
