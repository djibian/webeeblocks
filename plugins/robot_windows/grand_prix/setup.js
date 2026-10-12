/* Simulation-only candidate window. Configuration identity stays in the world. */
(function(){
'use strict';
const A=window.WebeeBlocksActivities;
const profile={id:'progression-grand-prix-v1',world:'worlds/grand_prix_v2.wbt',
 brief:{visible:true,title:'Grand Prix autonome — prototype',mission:'Parcours trois fois la boucle à quatre virages gauches, puis continue tout droit à la dernière jonction. Découvre et mémorise le nombre de portiques au premier tour. Adapte la hauteur aux traverses et aux obstacles bas, reste dans la piste et termine posé devant le dernier portique fermé de la ligne finale. Une collision invalide l’essai.'},
 pedagogy:{objective:'Combiner perceptions, variables, comptage orienté et boucles conditionnelles dans un parcours autonome.'},
 toolbox:['webeeblocks_v2_takeoff','webeeblocks_v2_move','webeeblocks_v2_vertical','webeeblocks_v2_turn','webeeblocks_v2_speed','webeeblocks_v2_range','controls_if','controls_repeat_ext','math_number','math_arithmetic','logic_compare','logic_operation','variables_set','variables_get','math_change','webeeblocks_v2_land'],
 parameterBounds:{webeeblocks_v2_takeoff:{HEIGHT:{min:.3,max:1.0,step:.1}},webeeblocks_v2_move:{DISTANCE:{min:.1,max:.4,step:.1}},webeeblocks_v2_vertical:{DISTANCE:{min:.1,max:.5,step:.1}},webeeblocks_v2_turn:{ANGLE:{min:1,max:179,step:1}},webeeblocks_v2_speed:{SPEED:{min:.1,max:.2,step:.05}}},
 fieldOptions:{webeeblocks_v2_range:{DIRECTION:['front','back','left','right']},math_arithmetic:{OP:['ADD','MINUS','MULTIPLY','DIVIDE']}},
 hardware:['crazyflie-2.1','flow-deck-v2','multi-ranger-deck'],timer:{enabled:true},evaluation:{type:'mission-state-v1',oracle:'grand-prix-v1'},
 runtime:{mode:'ast-v1',maxSteps:20000,allowedStatementKinds:['takeoff','move','vertical','turn','set_speed','if','repeat','set_variable','land'],rangeDirections:['front','back','left','right'],moveDirections:['forward','back','left','right'],verticalDirections:['up','down'],astBounds:{'takeoff.height_m':{min:.3,max:1.0},'move.distance_m':{min:.1,max:.4},'vertical.distance_m':{min:.1,max:.5},'set_speed.speed_m_s':{min:.1,max:.2},'repeat.count':{min:1,max:20}}}
};
if(A.BLOCK_CATALOG.controls_whileUntil){profile.toolbox.push('controls_whileUntil');profile.runtime.allowedStatementKinds.push('while');profile.runtime.astBounds['while.max_iterations']={min:1,max:100};}
window.WebeeBlocksActivities={BLOCK_CATALOG:A.BLOCK_CATALOG,DOCUMENT:{version:1,activities:[profile]},getProfile:id=>{if(id!==profile.id)throw new Error('unknown Grand Prix activity');return JSON.parse(JSON.stringify(profile));}};
window.WebeeBlocksInitialActivityId=profile.id;
const inject=Blockly.inject;
Blockly.inject=function(element,options){return inject(element,Object.assign({},options,{media:'../blockly_v2/vendor/media/'}));};
const OriginalBackend=WebeeBlocksWwiBackend;
window.WebeeBlocksWwiBackend=function(robotWindow,options){
 const backend=new OriginalBackend(robotWindow,Object.assign({},options,{simulationScenes:false}));
 const takeoff=backend.takeoff.bind(backend);
 backend.takeoff=async function(height){await backend._request(['GP_MODE',document.getElementById('stepMode').checked?'1':'0']);return takeoff(height);};
 return backend;
};
})();
