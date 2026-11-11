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
 return new OriginalBackend(robotWindow,Object.assign({},options,{simulationScenes:false,simulationAdmission:true}));
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
  function mount() {
    if (!element && typeof document !== 'undefined' && document &&
        typeof document.getElementById === 'function' &&
        typeof document.createElement === 'function') {
      var panel = document.getElementById('statusPanel');
      if (panel) {
        element = document.createElement('span');
        element.id = 'grandPrixElapsedClock';
        element.setAttribute('aria-live', 'off');
        element.style.fontVariantNumeric = 'tabular-nums';
        element.style.whiteSpace = 'nowrap';
        // Keep the clock visible on narrow classroom Robot Windows.
        if (panel.style) panel.style.flexWrap = 'wrap';
        panel.appendChild(element);
      }
    }
    return !!element;
  }
  function format(seconds) {
    var tenths = Math.floor(seconds * 10 + 1e-8);
    var minutes = Math.floor(tenths / 600);
    var remainder = (tenths % 600) / 10;
    return String(minutes).padStart(2, '0') + ':' + remainder.toFixed(1).padStart(4, '0');
  }
  function show(text) {
    if (mount()) element.textContent = text;
  }
  function empty() { show('Temps simulé : — / 03:30'); }
  function clear() {
    generation += 1;
    running = false;
    pending = false;
    if (interval !== null) window.clearInterval(interval);
    interval = null;
  }
  function reset() {
    clear();
    last = null;
    empty();
  }
  function finish() {
    clear();
    show(last === null ? 'Temps simulé : — / 03:30' :
      'Dernière mesure : ' + format(last) + ' / 03:30');
  }
  function sample() {
    if (!running || pending) return;
    var backend = window.runtimeBackend;
    if (!backend || !backend.ready || typeof backend.readElapsedTime !== 'function') {
      if (last !== null) show('Dernière mesure : ' + format(last) + ' / 03:30');
      return;
    }
    var bound = generation;
    pending = true;
    Promise.resolve().then(function() { return backend.readElapsedTime(); }).then(function(seconds) {
      if (bound !== generation || !running) return;
      if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0 ||
          (last !== null && seconds < last)) {
        show('Temps simulé : indisponible');
        return;
      }
      last = seconds;
      show('Temps simulé : ' + format(seconds) + ' / 03:30');
    }, function() {
      if (bound !== generation || !running) return;
      // TIME_UNAVAILABLE is expected before TAKEOFF completes and after LAND.
      show(last === null ? 'Temps simulé : — / 03:30' :
        'Dernière mesure : ' + format(last) + ' / 03:30');
    }).finally(function() {
      if (bound === generation) pending = false;
    });
  }
  function start() {
    if (running) return;
    reset();
    running = true;
    sample();
    interval = window.setInterval(sample, 1000); // <= 1 request/s; never overlap.
  }
  window.addEventListener('webeeblocks-ui-ready', empty);
  window.addEventListener('webeeblocks-runtime-v2', function(event) {
    var state = event && event.detail && event.detail.state;
    if (state === 'EXÉCUTION') start();
    else if (state === 'PRÊT' || state === 'INITIALISATION' || state === 'RÉINITIALISATION') reset();
    else if (state) finish();
  });
})();

})();
