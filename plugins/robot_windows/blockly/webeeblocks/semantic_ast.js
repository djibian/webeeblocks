(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksSemanticAst = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var LIMITS = Object.freeze({height_m:{min:0.2,max:1.5},distance_m:{min:0.1,max:2.0},vertical_m:{min:0.1,max:0.8},wait_s:{min:0.1,max:5.0},speed_m_s:{min:0.1,max:0.6},repeat:{min:1,max:20}});
  var SENSOR_DIRECTIONS = Object.freeze(['front','back','left','right','up']);
  var LIGHT_COLORS = Object.freeze(['off','red','green','blue','yellow','white']);
  var ARITHMETIC_OPS = Object.freeze(['ADD','MINUS','MULTIPLY','DIVIDE']);
  function fail(message){throw new Error('semantic AST: '+message);}
  function studentFail(message,detail){var error=new Error('semantic AST: '+message);error.code='PROGRAM_INVALID';error.studentDetail=detail;throw error;}
  function finite(value,name){var n=Number(value);if(!Number.isFinite(n))fail(name+' must be finite');return n;}
  function bounded(value,name,limits){var n=finite(value,name);if(n<limits.min||n>limits.max)fail(name+' out of bounds: '+n);return n;}
  function field(block,name){if(!block||typeof block.getFieldValue!=='function')fail('invalid Blockly block');return block.getFieldValue(name);}
  function statementChildren(block,inputName,procedures){if(!block||typeof block.getInputTargetBlock!=='function')fail('block does not expose statement input '+inputName);return compileSequence(block.getInputTargetBlock(inputName),procedures);}
  function valueChild(block,inputName){if(!block||typeof block.getInputTargetBlock!=='function')fail('block does not expose value input '+inputName);var child=block.getInputTargetBlock(inputName);if(!child)fail('missing value input '+inputName);return compileExpression(child);}
  function variableReference(block){
    if(!block||typeof block.getField!=='function')fail('variable block does not expose VAR field');
    var variableField=block.getField('VAR');
    var model=variableField&&typeof variableField.getVariable==='function'?variableField.getVariable():null;
    if(!model)fail('variable model unavailable');
    var id=typeof model.getId==='function'?String(model.getId()):String(model.id_||'');
    var name=String(model.name||'').trim();
    if(!id)fail('variable id must be non-empty');
    if(!name)fail('variable name must be non-empty');
    return{id:id,name:name};
  }

  function compileExpression(block){
    switch(block.type){
      case 'webeeblocks_v2_elapsed':return{kind:'elapsed_time',unit:'s'};
      case 'webeeblocks_v2_range':{var direction=String(field(block,'DIRECTION'));if(SENSOR_DIRECTIONS.indexOf(direction)<0)fail('unsupported range direction: '+direction);return{kind:'range',direction:direction,unit:'m'};}
      case 'math_number':return{kind:'number',value:finite(field(block,'NUM'),'number')};
      case 'math_arithmetic':{var arithmetic=String(field(block,'OP'));if(ARITHMETIC_OPS.indexOf(arithmetic)<0)fail('unsupported arithmetic operation: '+arithmetic);return{kind:'arithmetic',op:arithmetic,left:valueChild(block,'A'),right:valueChild(block,'B')};}
      case 'variables_get':return{kind:'variable_get',variable:variableReference(block)};
      case 'logic_compare':{var compare=String(field(block,'OP'));if(['LT','LTE','GT','GTE','EQ','NEQ'].indexOf(compare)<0)fail('unsupported comparison: '+compare);return{kind:'compare',op:compare,left:valueChild(block,'A'),right:valueChild(block,'B')};}
      case 'logic_operation':{var logic=String(field(block,'OP'));if(logic!=='AND'&&logic!=='OR')fail('unsupported logic operation: '+logic);return{kind:'logic',op:logic,left:valueChild(block,'A'),right:valueChild(block,'B')};}
      default:fail('unsupported expression block: '+block.type);
    }
  }

  function repeatCount(block){if(typeof block.getInputTargetBlock==='function'&&block.getInputTargetBlock('TIMES')){var expression=valueChild(block,'TIMES');if(expression.kind!=='number'||Math.floor(expression.value)!==expression.value)fail('repeat count must be an integer literal');return bounded(expression.value,'repeat',LIMITS.repeat);}return bounded(field(block,'TIMES'),'repeat',LIMITS.repeat);}

  function procedureName(name){
    if(typeof name!=='string'||!name.trim()||name.trim().length>80)
      studentFail('invalid procedure name','Donnez à chaque procédure un nom de 1 à 80 caractères.');
    return name.trim();
  }
  function procedureKey(name){return procedureName(name).toLowerCase();}
  function procedureBody(block,procedures){
    if(!procedures)fail('procedure call requires a workspace');
    var name=procedureName(block.getProcedureCall()),key=procedureKey(name);
    if(block.arguments_&&block.arguments_.length)
      studentFail('procedure parameters unsupported','Utilisez une procédure sans paramètre.');
    if(!procedures.definitions.has(key))
      studentFail('undefined procedure: '+name,'Définissez la procédure appelée avant de lancer.');
    if(procedures.stack.indexOf(key)>=0)
      studentFail('recursive procedure cycle: '+name,'Une procédure ne peut pas se rappeler, même par une autre procédure.');
    procedures.stack.push(key);
    try{return statementChildren(procedures.definitions.get(key),'STACK',procedures);}
    finally{procedures.stack.pop();}
  }
  function compileStatement(block,procedures){
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
      case 'webeeblocks_v2_light':{var color=String(field(block,'COLOR'));if(LIGHT_COLORS.indexOf(color)<0)fail('unsupported light color: '+color);return{kind:'set_light',color:color};}
      case 'variables_set':return{kind:'set_variable',variable:variableReference(block),value:valueChild(block,'VALUE')};
      case 'math_change':{var changedVariable=variableReference(block);return{kind:'set_variable',variable:changedVariable,value:{kind:'arithmetic',op:'ADD',left:{kind:'variable_get',variable:changedVariable},right:valueChild(block,'DELTA')}};}
      case 'webeeblocks_v2_until':return{kind:'while',mode:'UNTIL',condition:valueChild(block,'BOOL'),body:statementChildren(block,'DO',procedures),max_iterations:25};
      case 'procedures_callnoreturn':return{kind:'call',name:procedureName(block.getProcedureCall()),body:procedureBody(block,procedures)};
      case 'controls_whileUntil':{var mode=String(field(block,'MODE'));if(mode!=='WHILE'&&mode!=='UNTIL')fail('unsupported loop mode');var rawLimit=field(block,'MAX_ITERATIONS');var max=rawLimit==null||rawLimit===''?100:finite(rawLimit,'max_iterations');if(Math.floor(max)!==max||max<1||max>100)studentFail('invalid conditional loop limit','La limite de boucle doit être un entier de 1 à 100.');return{kind:'while',mode:mode,condition:valueChild(block,'BOOL'),body:statementChildren(block,'DO',procedures),max_iterations:max};}
      case 'controls_repeat_ext':return{kind:'repeat',count:repeatCount(block),body:statementChildren(block,'DO',procedures)};
      case 'controls_if':{if(block.elseifCount_&&block.elseifCount_!==0)fail('else-if branches are not part of AST v1');var result={kind:'if',condition:valueChild(block,'IF0'),then:statementChildren(block,'DO0',procedures)};if(block.getInputTargetBlock('ELSE'))result.else=statementChildren(block,'ELSE',procedures);return result;}
      default:fail('unsupported statement block: '+block.type);
    }
  }

  function compileSequence(first,procedures){
    if(procedures&&++procedures.depth>20)fail('procedure expansion nesting too deep');
    try{
      var result=[],block=first,guard=0;
      while(block){
        guard+=1;if(guard>200)fail('program too large');
        if(procedures&&++procedures.nodes>2000)fail('procedure expansion too large');
        result.push(compileStatement(block,procedures));
        block=typeof block.getNextBlock==='function'?block.getNextBlock():null;
      }
      return result;
    }finally{if(procedures)procedures.depth-=1;}
  }

  function rejectNestedFlightBoundaries(sequence){(sequence||[]).forEach(function(statement){if(statement.kind==='takeoff'||statement.kind==='land')fail('takeoff and land are only allowed at top-level boundaries');if(statement.kind==='repeat'||statement.kind==='while'||statement.kind==='call')rejectNestedFlightBoundaries(statement.body);if(statement.kind==='if'){rejectNestedFlightBoundaries(statement.then);rejectNestedFlightBoundaries(statement.else);}});}
  function validateFlightBoundaries(program){
    if(program.length<2||program[0].kind!=='takeoff'||program[program.length-1].kind!=='land')studentFail('program must start with takeoff and end with land','Le programme doit commencer par « décoller » et se terminer par « atterrir ».');
    for(var i=0;i<program.length;i++){
      var statement=program[i];
      if(statement.kind==='takeoff'&&i!==0)fail('takeoff is only allowed as the first top-level statement');
      if(statement.kind==='land'&&i!==program.length-1)fail('land is only allowed as the final top-level statement');
      if(statement.kind==='repeat'||statement.kind==='while'||statement.kind==='call')rejectNestedFlightBoundaries(statement.body);
      if(statement.kind==='if'){rejectNestedFlightBoundaries(statement.then);rejectNestedFlightBoundaries(statement.else);}
    }
  }

  function compileWorkspace(workspace){
    if(!workspace||typeof workspace.getTopBlocks!=='function')fail('invalid Blockly workspace');
    var allTops=workspace.getTopBlocks(true),procedures={definitions:new Map(),stack:[],nodes:0,depth:0};
    var tops=allTops.filter(function(block){
      if(block.type!=='procedures_defnoreturn')return true;
      var signature=block.getProcedureDef(),key=procedureKey(signature[0]);
      if(signature[1].length||signature[2])studentFail('procedure parameters unsupported','Utilisez une procédure sans paramètre ni résultat.');
      if(procedures.definitions.has(key))studentFail('duplicate procedure: '+signature[0],'Donnez des noms différents aux procédures.');
      procedures.definitions.set(key,block);return false;
    });
    if(tops.length===0)studentFail('Crazyflie program must have exactly one top-level sequence','Construisez un programme relié avant de lancer.');
    if(tops.length!==1)studentFail('Crazyflie program must have exactly one top-level sequence','Des blocs sont détachés du programme principal. Reliez-les ou supprimez-les avant de lancer.');
    // Check even unused definitions: invalid calls/cycles must not hide outside main.
    procedures.definitions.forEach(function(block,key){
      procedures.stack.push(key);
      try{rejectNestedFlightBoundaries(statementChildren(block,'STACK',procedures));}
      finally{procedures.stack.pop();}
    });
    var program=compileSequence(tops[0],procedures);validateFlightBoundaries(program);return{version:1,semantics:'webeeblocks-ast-v1',program:program};
  }


  function installConditionalLoopBounds(Blockly){
    var definition=Blockly&&Blockly.Blocks&&Blockly.Blocks.controls_whileUntil;
    if(!definition||definition.webeeblocksBoundedLoop||typeof definition.init!=='function'||typeof Blockly.FieldNumber!=='function')return;
    var original=definition.init;
    definition.init=function(){
      original.call(this);
      this.appendDummyInput('WEBEEBLOCKS_LOOP_BOUND').appendField('limite :')
        .appendField(new Blockly.FieldNumber(100,1,100,1),'MAX_ITERATIONS').appendField('itérations');
    };
    definition.webeeblocksBoundedLoop=true;
  }
  if(typeof Blockly!=='undefined')installConditionalLoopBounds(Blockly);

  return{installConditionalLoopBounds:installConditionalLoopBounds,LIMITS:LIMITS,SENSOR_DIRECTIONS:SENSOR_DIRECTIONS,LIGHT_COLORS:LIGHT_COLORS,ARITHMETIC_OPS:ARITHMETIC_OPS,compileExpression:compileExpression,compileStatement:compileStatement,compileSequence:compileSequence,compileWorkspace:compileWorkspace,validateFlightBoundaries:validateFlightBoundaries};
});
