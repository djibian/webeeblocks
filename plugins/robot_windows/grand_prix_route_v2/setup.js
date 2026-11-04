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
 return new OriginalBackend(robotWindow,Object.assign({},options,{simulationScenes:false}));
};
const originalOutcome=window.WebeeBlocksRuntimeOutcome;
window.WebeeBlocksRuntimeOutcome=Object.assign({},originalOutcome,{
 classify(error){return error&&error.code==='TIME_LIMIT'?{state:'MISSION ÉCHOUÉE',detail:'Temps écoulé — atterrissage imposé',machineCode:'TIME_LIMIT'}:originalOutcome.classify(error);}
});
})();
