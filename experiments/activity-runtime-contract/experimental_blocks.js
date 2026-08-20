/* Frozen experimental block definitions from draft #46/#44. A2 seam proof only. */
(function(){'use strict';Blockly.defineBlocksWithJsonArray([
{type:'webeeblocks_exp_takeoff',message0:'décoller à %1 m',args0:[{type:'field_number',name:'HEIGHT',value:0.5,min:0.2,max:1.5,precision:0.1}],previousStatement:null,nextStatement:null,colour:20},
{type:'webeeblocks_exp_land',message0:'atterrir',previousStatement:null,nextStatement:null,colour:20},
{type:'webeeblocks_exp_move',message0:'%1 de %2 m',args0:[{type:'field_dropdown',name:'DIRECTION',options:[['avancer','forward'],['reculer','back'],['aller à gauche','left'],['aller à droite','right']]},{type:'field_number',name:'DISTANCE',value:0.3,min:0.1,max:2.0,precision:0.1}],previousStatement:null,nextStatement:null,colour:20},
{type:'webeeblocks_exp_range',message0:'distance %1',args0:[{type:'field_dropdown',name:'DIRECTION',options:[['devant','front'],['derrière','back'],['à gauche','left'],['à droite','right'],['au-dessus','up']]}],output:'Number',colour:60}
]);})();
