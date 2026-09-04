(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksSemanticAst = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var LIMITS = Object.freeze({height_m:{min:0.2,max:1.5},distance_m:{min:0.1,max:2.0},vertical_m:{min:0.1,max:0.8},wait_s:{min:0.1,max:5.0},speed_m_s:{min:0.1,max:0.6},repeat:{min:1,max:20}});
  var SENSOR_DIRECTIONS = Object.freeze(['front','back','left','right','up']);
  function fail(message){throw new Error('semantic AST: '+message);}
  function studentFail(message,detail){var error=new Error('semantic AST: '+message);error.code='PROGRAM_INVALID';error.studentDetail=detail;throw error;}
  function finite(value,name){var n=Number(value);if(!Number.isFinite(n))fail(name+' must be finite');return n;}
  function bounded(value,name,limits){var n=finite(value,name);if(n<limits.min||n>limits.max)fail(name+' out of bounds: '+n);return n;}
  function field(block,name){if(!block||typeof block.getFieldValue!=='function')fail('invalid Blockly block');return block.getFieldValue(name);}
  function statementChildren(block,inputName){if(!block||typeof block.getInputTargetBlock!=='function')fail('block does not expose statement input '+inputName);return compileSequence(block.getInputTargetBlock(inputName));}
  function valueChild(block,inputName){if(!block||typeof block.getInputTargetBlock!=='function')fail('block does not expose value input '+inputName);var child=block.getInputTargetBlock(inputName);if(!child)fail('missing value input '+inputName);return compileExpression(child);}

  function compileExpression(block){
    switch(block.type){
      case 'webeeblocks_v2_range':{var direction=String(field(block,'DIRECTION'));if(SENSOR_DIRECTIONS.indexOf(direction)<0)fail('unsupported range direction: '+direction);return{kind:'range',direction:direction,unit:'m'};}
      case 'math_number':return{kind:'number',value:finite(field(block,'NUM'),'number')};
      case 'logic_compare':{var compare=String(field(block,'OP'));if(['LT','LTE','GT','GTE','EQ','NEQ'].indexOf(compare)<0)fail('unsupported comparison: '+compare);return{kind:'compare',op:compare,left:valueChild(block,'A'),right:valueChild(block,'B')};}
      case 'logic_operation':{var logic=String(field(block,'OP'));if(logic!=='AND'&&logic!=='OR')fail('unsupported logic operation: '+logic);return{kind:'logic',op:logic,left:valueChild(block,'A'),right:valueChild(block,'B')};}
      default:fail('unsupported expression block: '+block.type);
    }
  }

  function repeatCount(block){if(typeof block.getInputTargetBlock==='function'&&block.getInputTargetBlock('TIMES')){var expression=valueChild(block,'TIMES');if(expression.kind!=='number'||Math.floor(expression.value)!==expression.value)fail('repeat count must be an integer literal');return bounded(expression.value,'repeat',LIMITS.repeat);}return bounded(field(block,'TIMES'),'repeat',LIMITS.repeat);}

  function compileStatement(block){
    switch(block.type){
      case 'webeeblocks_takeoff':return{kind:'takeoff',height_m:1.0};
      case 'webeeblocks_forward':return{kind:'move',direction:'forward',distance_m:bounded(field(block,'DISTANCE'),'distance_m',LIMITS.distance_m)};
      case 'webeeblocks_turn':{var legacyAngle=bounded(field(block,'ANGLE'),'angle_deg',{min:-179,max:179});if(legacyAngle===0)fail('turn angle must be non-zero');return{kind:'turn',angle_deg:legacyAngle};}
      case 'webeeblocks_land':return{kind:'land'};
      case 'webeeblocks_v2_takeoff':return{kind:'takeoff',height_m:bounded(field(block,'HEIGHT'),'height_m',LIMITS.height_m)};
      case 'webeeblocks_v2_land':return{kind:'land'};
      case 'webeeblocks_v2_move':{var direction=String(field(block,'DIRECTION'));if(['forward','back','left','right'].indexOf(direction)<0)fail('unsupported move direction: '+direction);return{kind:'move',direction:direction,distance_m:bounded(field(block,'DISTANCE'),'distance_m',LIMITS.distance_m)};}
      case 'webeeblocks_v2_vertical':{var verticalDirection=String(field(block,'DIRECTION'));if(verticalDirection!=='up'&&verticalDirection!=='down')fail('unsupported vertical direction: '+verticalDirection);return{kind:'vertical',direction:verticalDirection,distance_m:bounded(field(block,'DISTANCE'),'vertical_m',LIMITS.vertical_m)};}
      case 'webeeblocks_v2_turn':{var turnDirection=String(field(block,'DIRECTION'));var degrees=bounded(field(block,'ANGLE'),'angle_deg',{min:1,max:179});if(turnDirection!=='left'&&turnDirection!=='right')fail('unsupported turn direction: '+turnDirection);return{kind:'turn',angle_deg:turnDirection==='left'?degrees:-degrees};}
      case 'webeeblocks_v2_wait':return{kind:'wait',seconds:bounded(field(block,'SECONDS'),'wait_s',LIMITS.wait_s)};
      case 'webeeblocks_v2_speed':return{kind:'set_speed',speed_m_s:bounded(field(block,'SPEED'),'speed_m_s',LIMITS.speed_m_s)};
      case 'controls_repeat_ext':return{kind:'repeat',count:repeatCount(block),body:statementChildren(block,'DO')};
      case 'controls_if':{if(block.elseifCount_&&block.elseifCount_!==0)fail('else-if branches are not part of AST v1');var result={kind:'if',condition:valueChild(block,'IF0'),then:statementChildren(block,'DO0')};if(block.getInputTargetBlock('ELSE'))result.else=statementChildren(block,'ELSE');return result;}
      default:fail('unsupported statement block: '+block.type);
    }
  }

  function compileSequence(first){var result=[],block=first,guard=0;while(block){guard+=1;if(guard>200)fail('program too large');result.push(compileStatement(block));block=typeof block.getNextBlock==='function'?block.getNextBlock():null;}return result;}

  function rejectNestedFlightBoundaries(sequence){(sequence||[]).forEach(function(statement){if(statement.kind==='takeoff'||statement.kind==='land')fail('takeoff and land are only allowed at top-level boundaries');if(statement.kind==='repeat')rejectNestedFlightBoundaries(statement.body);if(statement.kind==='if'){rejectNestedFlightBoundaries(statement.then);rejectNestedFlightBoundaries(statement.else);}});}
  function validateFlightBoundaries(program){
    if(program.length<2||program[0].kind!=='takeoff'||program[program.length-1].kind!=='land')studentFail('program must start with takeoff and end with land','Le programme doit commencer par « décoller » et se terminer par « atterrir ».');
    for(var i=0;i<program.length;i++){
      var statement=program[i];
      if(statement.kind==='takeoff'&&i!==0)fail('takeoff is only allowed as the first top-level statement');
      if(statement.kind==='land'&&i!==program.length-1)fail('land is only allowed as the final top-level statement');
      if(statement.kind==='repeat')rejectNestedFlightBoundaries(statement.body);
      if(statement.kind==='if'){rejectNestedFlightBoundaries(statement.then);rejectNestedFlightBoundaries(statement.else);}
    }
  }

  function compileWorkspace(workspace){
    if(!workspace||typeof workspace.getTopBlocks!=='function')fail('invalid Blockly workspace');
    var tops=workspace.getTopBlocks(true);
    if(tops.length===0)studentFail('Crazyflie program must have exactly one top-level sequence','Construisez un programme relié avant de lancer.');
    if(tops.length!==1)studentFail('Crazyflie program must have exactly one top-level sequence','Des blocs sont détachés du programme principal. Reliez-les ou supprimez-les avant de lancer.');
    var program=compileSequence(tops[0]);validateFlightBoundaries(program);return{version:1,semantics:'webeeblocks-ast-v1',program:program};
  }

  return{LIMITS:LIMITS,SENSOR_DIRECTIONS:SENSOR_DIRECTIONS,compileExpression:compileExpression,compileStatement:compileStatement,compileSequence:compileSequence,compileWorkspace:compileWorkspace,validateFlightBoundaries:validateFlightBoundaries};
});
