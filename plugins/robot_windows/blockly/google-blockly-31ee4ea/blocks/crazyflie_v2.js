/* Product Blockly definitions for the WebeeBlocks semantic Runtime v2. No Python generators. */
(function(){'use strict';Blockly.defineBlocksWithJsonArray([
{type:'webeeblocks_v2_takeoff',message0:'décoller à %1 m',args0:[{type:'field_number',name:'HEIGHT',value:0.5,min:0.2,max:1.5,precision:0.1}],previousStatement:null,nextStatement:null,style:'flight_blocks'},
{type:'webeeblocks_v2_land',message0:'atterrir',previousStatement:null,nextStatement:null,style:'flight_blocks'},
{type:'webeeblocks_v2_move',message0:'%1 de %2 m',args0:[{type:'field_dropdown',name:'DIRECTION',options:[['avancer','forward'],['reculer','back'],['aller à gauche','left'],['aller à droite','right']]},{type:'field_number',name:'DISTANCE',value:0.3,min:0.1,max:2.0,precision:0.1}],previousStatement:null,nextStatement:null,style:'flight_blocks'},
{type:'webeeblocks_v2_vertical',message0:'%1 de %2 m',args0:[{type:'field_dropdown',name:'DIRECTION',options:[['monter','up'],['descendre','down']]},{type:'field_number',name:'DISTANCE',value:0.2,min:0.1,max:0.8,precision:0.1}],previousStatement:null,nextStatement:null,style:'flight_blocks'},
{type:'webeeblocks_v2_turn',message0:'tourner à %1 de %2 °',args0:[{type:'field_dropdown',name:'DIRECTION',options:[['gauche','left'],['droite','right']]},{type:'field_number',name:'ANGLE',value:90,min:1,max:179,precision:1}],previousStatement:null,nextStatement:null,style:'flight_blocks'},
{type:'webeeblocks_v2_wait',message0:'attendre %1 s',args0:[{type:'field_number',name:'SECONDS',value:0.5,min:0.1,max:5.0,precision:0.1}],previousStatement:null,nextStatement:null,style:'control_blocks'},
{type:'webeeblocks_v2_speed',message0:'régler la vitesse à %1 m/s',args0:[{type:'field_number',name:'SPEED',value:0.2,min:0.1,max:0.6,precision:0.1}],previousStatement:null,nextStatement:null,style:'flight_blocks'},
{type:'webeeblocks_v2_light',message0:'lumière %1',args0:[{type:'field_dropdown',name:'COLOR',options:[['éteinte','off'],['rouge','red'],['verte','green'],['bleue','blue'],['jaune','yellow'],['blanche','white']]}],previousStatement:null,nextStatement:null,style:'flight_blocks'},
{type:'webeeblocks_v2_range',message0:'distance %1',args0:[{type:'field_dropdown',name:'DIRECTION',options:[['devant','front'],['derrière','back'],['à gauche','left'],['à droite','right'],['au-dessus','up']]}],output:'Number',style:'sensor_blocks'}
]);})();
