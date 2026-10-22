/* Only the U candidate is active in this dedicated simulation window. */
(function(){
'use strict';
const A=window.WebeeBlocksActivities;
const profile={id:'progression-grand-prix-u-v1',world:'worlds/grand_prix_u_seed4.wbt',
 brief:{visible:true,title:'Grand Prix autonome — prototype U',mission:'Parcours une seule fois les trois côtés du carré et ses deux virages à gauche. Franchis les portiques ouverts en restant dans les bandes jaunes quand tu descends sous 0,60 m. Le sol ne contient aucun obstacle bas. Devant le portique fermé, pose-toi au centre après 1 passage, à 50 cm à gauche après 2 passages, à 50 cm à droite après 3 passages. Une mauvaise pose ou une sortie de zone échoue. À 210 secondes Webots, la mission échoue et le drone reçoit un ordre indépendant d’atterrissage immédiat. Les dimensions et bandes du prototype restent expérimentales.'},
 pedagogy:{objective:'Combiner perceptions, variables, comptage orienté et boucles conditionnelles dans un parcours autonome.'},
 toolbox:['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_vertical','webeeblocks_v2_turn','webeeblocks_v2_speed','webeeblocks_v2_range','controls_if','controls_repeat_ext','webeeblocks_v2_until','math_number','math_arithmetic','logic_compare','logic_operation','variables_set','variables_get','math_change','webeeblocks_v2_land'],
 parameterBounds:{webeeblocks_v2_takeoff:{HEIGHT:{min:.3,max:1.0,step:.1}},webeeblocks_v2_move:{DISTANCE:{min:.1,max:.4,step:.1}},webeeblocks_v2_vertical:{DISTANCE:{min:.1,max:.5,step:.1}},webeeblocks_v2_turn:{ANGLE:{min:1,max:179,step:1}},webeeblocks_v2_speed:{SPEED:{min:.1,max:.35,step:.05}}},
 fieldOptions:{webeeblocks_v2_range:{DIRECTION:['front','back','left','right']},math_arithmetic:{OP:['ADD','MINUS','MULTIPLY','DIVIDE']}},
 hardware:['crazyflie-2.1','flow-deck-v2','multi-ranger-deck'],timer:{enabled:true},evaluation:{type:'mission-state-v1',oracle:'grand-prix-u-v1'},
 runtime:{mode:'ast-v1',maxSteps:20000,allowedStatementKinds:['takeoff','move','vertical','turn','set_speed','if','repeat','while','set_variable','land'],rangeDirections:['front','back','left','right'],moveDirections:['forward','back','left','right'],verticalDirections:['up','down'],astBounds:{'takeoff.height_m':{min:.3,max:1.0},'move.distance_m':{min:.1,max:.4},'vertical.distance_m':{min:.1,max:.5},'set_speed.speed_m_s':{min:.1,max:.35},'repeat.count':{min:1,max:20},'while.max_iterations':{min:1,max:100}}}
};
if(A.BLOCK_CATALOG.webeeblocks_v2_guarded_move){
 profile.toolbox.push('webeeblocks_v2_guarded_move');profile.runtime.allowedStatementKinds.push('guarded_move');
 profile.parameterBounds.webeeblocks_v2_guarded_move={DISTANCE:{min:.1,max:.4,step:.1},THRESHOLD:{min:.25,max:1.5,step:.01}};
 profile.runtime.astBounds['guarded_move.max_distance_m']={min:.1,max:.4};
 profile.runtime.astBounds['guarded_move.threshold_m']={min:.25,max:1.5};
}
if(A.BLOCK_CATALOG.controls_whileUntil){profile.toolbox.push('controls_whileUntil');}
if(A.BLOCK_CATALOG.webeeblocks_v2_elapsed){profile.toolbox.push('webeeblocks_v2_elapsed');profile.runtime.elapsedSimulationTime=true;}
window.WebeeBlocksActivities={BLOCK_CATALOG:A.BLOCK_CATALOG,DOCUMENT:{version:1,activities:[profile]},getProfile:id=>{if(id!==profile.id)throw new Error('unknown Grand Prix activity');return JSON.parse(JSON.stringify(profile));}};
window.WebeeBlocksInitialActivityId=profile.id;
const inject=Blockly.inject;
Blockly.inject=function(element,options){return inject(element,Object.assign({},options,{media:'../blockly_v2/vendor/media/'}));};
const OriginalBackend=WebeeBlocksWwiBackend;
window.WebeeBlocksWwiBackend=function(robotWindow,options){
 return new OriginalBackend(robotWindow,Object.assign({},options,{simulationScenes:false}));
};
const originalOutcome=window.WebeeBlocksRuntimeOutcome;
window.WebeeBlocksRuntimeOutcome=Object.assign({},originalOutcome,{
 classify(error){return error&&error.code==='TIME_LIMIT'?{state:'MISSION ÉCHOUÉE',detail:'Temps écoulé — atterrissage imposé',machineCode:'TIME_LIMIT'}:originalOutcome.classify(error);}
});
})();
