(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksInterpreter = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var SENSOR_DIRECTIONS=['front','back','left','right','up'];
  var MOVE_DIRECTIONS=['forward','back','left','right'];
  var VERTICAL_DIRECTIONS=['up','down'];
  var COMPARE_OPS=['LT','LTE','GT','GTE','EQ','NEQ'];
  function fail(message){throw new Error('runtime v2: '+message);}
  function finite(value,name){var n=Number(value);if(!Number.isFinite(n))fail(name+' must be finite');return n;}
  function requireMethod(backend,name){if(!backend||typeof backend[name]!=='function')fail('backend is missing '+name+'()');return backend[name].bind(backend);}
  async function hook(options,name,payload){var hooks=options&&options.hooks;if(hooks&&typeof hooks[name]==='function')await hooks[name](payload);}
  function variableRef(variable){if(!variable||typeof variable.id!=='string'||!variable.id||typeof variable.name!=='string'||!variable.name.trim())fail('invalid variable reference');return{id:variable.id,name:variable.name};}
  function cloneSet(source){return new Set(Array.from(source));}
  function environment(){return{values:Object.create(null),names:Object.create(null)};}
  function snapshot(env){var out={};Object.keys(env.values).forEach(function(id){var name=env.names[id];if(name)out[name]=env.values[id];});return out;}
  function context(node,path,role,env,extra){return Object.assign({node:node,path:(path||[]).slice(),role:role,variables:env?snapshot(env):{}},extra||{});}
  function rememberVariable(variables,variable){var ref=variableRef(variable);if(Object.prototype.hasOwnProperty.call(variables,ref.id)&&variables[ref.id]!==ref.name)fail('variable id/name mismatch: '+ref.id);variables[ref.id]=ref.name;return ref;}

  function validateExpression(expression,depth,assigned,variables){
    if(!expression||typeof expression.kind!=='string')fail('invalid expression');
    if(depth>20)fail('expression nesting too deep');
    switch(expression.kind){
      case 'number':finite(expression.value,'number');return;
      case 'range':if(SENSOR_DIRECTIONS.indexOf(String(expression.direction))<0||expression.unit!=='m')fail('unsupported range expression');return;
      case 'variable_get':{var ref=rememberVariable(variables,expression.variable);if(!assigned.has(ref.id))fail('variable read before assignment: '+ref.name);return;}
      case 'compare':if(COMPARE_OPS.indexOf(String(expression.op))<0)fail('unsupported comparison '+expression.op);validateExpression(expression.left,depth+1,assigned,variables);validateExpression(expression.right,depth+1,assigned,variables);return;
      case 'logic':if(expression.op!=='AND'&&expression.op!=='OR')fail('unsupported logic operation '+expression.op);validateExpression(expression.left,depth+1,assigned,variables);validateExpression(expression.right,depth+1,assigned,variables);return;
      default:fail('unsupported expression kind '+expression.kind);
    }
  }

  function validateSequence(sequence,depth,nested,assigned,variables){
    if(!Array.isArray(sequence))fail('statement sequence must be an array');
    if(depth>20)fail('statement nesting too deep');
    sequence.forEach(function(statement){
      if(!statement||typeof statement.kind!=='string')fail('invalid statement');
      if(nested&&(statement.kind==='takeoff'||statement.kind==='land'))fail('takeoff and land are only allowed at top-level boundaries');
      switch(statement.kind){
        case 'takeoff':finite(statement.height_m,'height_m');break;
        case 'land':break;
        case 'move':if(MOVE_DIRECTIONS.indexOf(String(statement.direction))<0)fail('unsupported move direction '+statement.direction);finite(statement.distance_m,'distance_m');break;
        case 'vertical':if(VERTICAL_DIRECTIONS.indexOf(String(statement.direction))<0)fail('unsupported vertical direction '+statement.direction);finite(statement.distance_m,'distance_m');break;
        case 'turn':finite(statement.angle_deg,'angle_deg');break;
        case 'wait':finite(statement.seconds,'seconds');break;
        case 'set_speed':finite(statement.speed_m_s,'speed_m_s');break;
        case 'set_variable':{var ref=rememberVariable(variables,statement.variable);validateExpression(statement.value,depth+1,assigned,variables);assigned.add(ref.id);break;}
        case 'if':{
          validateExpression(statement.condition,depth+1,assigned,variables);
          var thenAssigned=cloneSet(assigned),elseAssigned=cloneSet(assigned);
          validateSequence(statement.then,depth+1,true,thenAssigned,variables);
          validateSequence(statement.else||[],depth+1,true,elseAssigned,variables);
          Array.from(assigned).forEach(function(id){if(!thenAssigned.has(id)||!elseAssigned.has(id))assigned.delete(id);});
          thenAssigned.forEach(function(id){if(elseAssigned.has(id))assigned.add(id);});
          break;
        }
        case 'repeat':{var count=Number(statement.count);if(!Number.isInteger(count)||count<1||count>20)fail('repeat count out of bounds');validateSequence(statement.body,depth+1,true,assigned,variables);break;}
        default:fail('unsupported statement kind '+statement.kind);
      }
    });
  }

  function validateProgram(ast){
    if(!ast||ast.version!==1||ast.semantics!=='webeeblocks-ast-v1')fail('unsupported AST envelope');
    if(!Array.isArray(ast.program)||ast.program.length<2)fail('program must contain at least takeoff and land');
    if(ast.program[0].kind!=='takeoff'||ast.program[ast.program.length-1].kind!=='land')fail('program must start with takeoff and end with land');
    for(var i=1;i<ast.program.length-1;i++)if(ast.program[i].kind==='takeoff'||ast.program[i].kind==='land')fail('takeoff and land are only allowed at top-level boundaries');
    validateSequence(ast.program,0,false,new Set(),Object.create(null));
  }

  async function evaluate(expression,backend,budget,depth,options,path,env){
    env=env||environment();
    budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');
    var current=context(expression,path,'expression',env);
    await hook(options,'onNode',current);
    switch(expression.kind){
      case 'number':await hook(options,'beforeStep',current);return Number(expression.value);
      case 'variable_get':{var ref=variableRef(expression.variable);await hook(options,'beforeStep',current);if(!Object.prototype.hasOwnProperty.call(env.values,ref.id))fail('variable read before assignment: '+ref.name);if(env.names[ref.id]&&env.names[ref.id]!==ref.name)fail('variable id/name mismatch: '+ref.id);return env.values[ref.id];}
      case 'range':{
        await hook(options,'beforeStep',current);
        var value=finite(await requireMethod(backend,'readRange')(String(expression.direction)),'range('+expression.direction+')');
        await hook(options,'onSensor',{node:expression,path:(path||[]).slice(),role:'expression',variables:snapshot(env),direction:String(expression.direction),value:value});
        return value;
      }
      case 'compare':{
        var left=await evaluate(expression.left,backend,budget,depth+1,options,(path||[]).concat('left'),env);
        var right=await evaluate(expression.right,backend,budget,depth+1,options,(path||[]).concat('right'),env);
        await hook(options,'beforeStep',context(expression,path,'expression',env));
        if(expression.op==='LT')return left<right;if(expression.op==='LTE')return left<=right;if(expression.op==='GT')return left>right;if(expression.op==='GTE')return left>=right;if(expression.op==='EQ')return left===right;return left!==right;
      }
      case 'logic':{
        var first=Boolean(await evaluate(expression.left,backend,budget,depth+1,options,(path||[]).concat('left'),env));var second;
        if(expression.op==='AND'){if(!first){await hook(options,'beforeStep',context(expression,path,'expression',env));return false;}second=Boolean(await evaluate(expression.right,backend,budget,depth+1,options,(path||[]).concat('right'),env));await hook(options,'beforeStep',context(expression,path,'expression',env));return first&&second;}
        if(first){await hook(options,'beforeStep',context(expression,path,'expression',env));return true;}second=Boolean(await evaluate(expression.right,backend,budget,depth+1,options,(path||[]).concat('right'),env));await hook(options,'beforeStep',context(expression,path,'expression',env));return first||second;
      }
    }
  }

  async function executeSequence(sequence,backend,budget,depth,options,prefix,env){
    for(var i=0;i<sequence.length;i++){
      budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');
      var statement=sequence[i],path=(prefix||[]).concat(i),current=context(statement,path,'statement',env);
      await hook(options,'onNode',current);
      switch(statement.kind){
        case 'takeoff':await hook(options,'beforeStep',current);await requireMethod(backend,'takeoff')(Number(statement.height_m));break;
        case 'land':await hook(options,'beforeStep',current);await requireMethod(backend,'land')();break;
        case 'move':await hook(options,'beforeStep',current);await requireMethod(backend,'move')(String(statement.direction),Number(statement.distance_m));break;
        case 'vertical':await hook(options,'beforeStep',current);await requireMethod(backend,'vertical')(String(statement.direction),Number(statement.distance_m));break;
        case 'turn':await hook(options,'beforeStep',current);await requireMethod(backend,'turn')(Number(statement.angle_deg));break;
        case 'wait':await hook(options,'beforeStep',current);await requireMethod(backend,'wait')(Number(statement.seconds));break;
        case 'set_speed':await hook(options,'beforeStep',current);await requireMethod(backend,'setSpeed')(Number(statement.speed_m_s));break;
        case 'set_variable':{
          var ref=variableRef(statement.variable),stored=await evaluate(statement.value,backend,budget,depth+1,options,path.concat('value'),env);
          await hook(options,'beforeStep',context(statement,path,'statement',env));env.values[ref.id]=stored;env.names[ref.id]=ref.name;
          await hook(options,'onVariables',{node:statement,path:path.slice(),role:'statement',variables:snapshot(env),variable:ref,values:snapshot(env)});break;
        }
        case 'if':{var condition=Boolean(await evaluate(statement.condition,backend,budget,depth+1,options,path.concat('condition'),env));await hook(options,'beforeStep',context(statement,path,'statement',env));await executeSequence(condition?statement.then:(statement.else||[]),backend,budget,depth+1,options,path.concat(condition?'then':'else'),env);break;}
        case 'repeat':for(var repeat=0;repeat<statement.count;repeat++){await hook(options,'beforeStep',context(statement,path,'statement',env,{iteration:repeat}));await executeSequence(statement.body,backend,budget,depth+1,options,path.concat('body'),env);}break;
      }
    }
  }

  async function run(ast,backend,options){validateProgram(ast);var maxSteps=options&&Number.isInteger(options.maxSteps)?options.maxSteps:1000;if(maxSteps<1||maxSteps>100000)fail('invalid execution budget');var budget={remaining:maxSteps},env=environment();await executeSequence(ast.program,backend,budget,0,options||{},['program'],env);return{remainingBudget:budget.remaining,variables:snapshot(env)};}
  return{run:run,evaluate:evaluate,validateProgram:validateProgram};
});
