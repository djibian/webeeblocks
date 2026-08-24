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
  function context(node,path,role,extra){return Object.assign({node:node,path:(path||[]).slice(),role:role,variables:null},extra||{});}

  function validateExpression(expression,depth){
    if(!expression||typeof expression.kind!=='string')fail('invalid expression');
    if(depth>20)fail('expression nesting too deep');
    switch(expression.kind){
      case 'number':finite(expression.value,'number');return;
      case 'range':if(SENSOR_DIRECTIONS.indexOf(String(expression.direction))<0||expression.unit!=='m')fail('unsupported range expression');return;
      case 'compare':if(COMPARE_OPS.indexOf(String(expression.op))<0)fail('unsupported comparison '+expression.op);validateExpression(expression.left,depth+1);validateExpression(expression.right,depth+1);return;
      case 'logic':if(expression.op!=='AND'&&expression.op!=='OR')fail('unsupported logic operation '+expression.op);validateExpression(expression.left,depth+1);validateExpression(expression.right,depth+1);return;
      default:fail('unsupported expression kind '+expression.kind);
    }
  }

  function validateSequence(sequence,depth,nested){
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
        case 'if':validateExpression(statement.condition,depth+1);validateSequence(statement.then,depth+1,true);validateSequence(statement.else||[],depth+1,true);break;
        case 'repeat':{var count=Number(statement.count);if(!Number.isInteger(count)||count<1||count>20)fail('repeat count out of bounds');validateSequence(statement.body,depth+1,true);break;}
        default:fail('unsupported statement kind '+statement.kind);
      }
    });
  }

  function validateProgram(ast){
    if(!ast||ast.version!==1||ast.semantics!=='webeeblocks-ast-v1')fail('unsupported AST envelope');
    if(!Array.isArray(ast.program)||ast.program.length<2)fail('program must contain at least takeoff and land');
    if(ast.program[0].kind!=='takeoff'||ast.program[ast.program.length-1].kind!=='land')fail('program must start with takeoff and end with land');
    for(var i=1;i<ast.program.length-1;i++)if(ast.program[i].kind==='takeoff'||ast.program[i].kind==='land')fail('takeoff and land are only allowed at top-level boundaries');
    validateSequence(ast.program,0,false);
  }

  async function evaluate(expression,backend,budget,depth,options,path){
    budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');
    var current=context(expression,path,'expression');
    await hook(options,'onNode',current);
    switch(expression.kind){
      case 'number':
        await hook(options,'beforeStep',current);
        return Number(expression.value);
      case 'range':{
        await hook(options,'beforeStep',current);
        var value=finite(await requireMethod(backend,'readRange')(String(expression.direction)),'range('+expression.direction+')');
        await hook(options,'onSensor',{node:expression,path:(path||[]).slice(),role:'expression',variables:null,direction:String(expression.direction),value:value});
        return value;
      }
      case 'compare':{
        var left=await evaluate(expression.left,backend,budget,depth+1,options,(path||[]).concat('left'));
        var right=await evaluate(expression.right,backend,budget,depth+1,options,(path||[]).concat('right'));
        await hook(options,'beforeStep',current);
        if(expression.op==='LT')return left<right;
        if(expression.op==='LTE')return left<=right;
        if(expression.op==='GT')return left>right;
        if(expression.op==='GTE')return left>=right;
        if(expression.op==='EQ')return left===right;
        return left!==right;
      }
      case 'logic':{
        var first=Boolean(await evaluate(expression.left,backend,budget,depth+1,options,(path||[]).concat('left')));
        var second;
        if(expression.op==='AND'){
          if(!first){await hook(options,'beforeStep',current);return false;}
          second=Boolean(await evaluate(expression.right,backend,budget,depth+1,options,(path||[]).concat('right')));
          await hook(options,'beforeStep',current);
          return first&&second;
        }
        if(first){await hook(options,'beforeStep',current);return true;}
        second=Boolean(await evaluate(expression.right,backend,budget,depth+1,options,(path||[]).concat('right')));
        await hook(options,'beforeStep',current);
        return first||second;
      }
    }
  }

  async function executeSequence(sequence,backend,budget,depth,options,prefix){
    for(var i=0;i<sequence.length;i++){
      budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');
      var statement=sequence[i];
      var path=(prefix||[]).concat(i);
      var current=context(statement,path,'statement');
      await hook(options,'onNode',current);
      switch(statement.kind){
        case 'takeoff':await hook(options,'beforeStep',current);await requireMethod(backend,'takeoff')(Number(statement.height_m));break;
        case 'land':await hook(options,'beforeStep',current);await requireMethod(backend,'land')();break;
        case 'move':await hook(options,'beforeStep',current);await requireMethod(backend,'move')(String(statement.direction),Number(statement.distance_m));break;
        case 'vertical':await hook(options,'beforeStep',current);await requireMethod(backend,'vertical')(String(statement.direction),Number(statement.distance_m));break;
        case 'turn':await hook(options,'beforeStep',current);await requireMethod(backend,'turn')(Number(statement.angle_deg));break;
        case 'wait':await hook(options,'beforeStep',current);await requireMethod(backend,'wait')(Number(statement.seconds));break;
        case 'set_speed':await hook(options,'beforeStep',current);await requireMethod(backend,'setSpeed')(Number(statement.speed_m_s));break;
        case 'if':{
          var condition=Boolean(await evaluate(statement.condition,backend,budget,depth+1,options,path.concat('condition')));
          await hook(options,'beforeStep',context(statement,path,'statement',{decision:true}));
          await executeSequence(condition?statement.then:(statement.else||[]),backend,budget,depth+1,options,path.concat(condition?'then':'else'));
          break;
        }
        case 'repeat':
          for(var repeat=0;repeat<statement.count;repeat++){
            await hook(options,'beforeStep',context(statement,path,'statement',{iteration:repeat}));
            await executeSequence(statement.body,backend,budget,depth+1,options,path.concat('body'));
          }
          break;
      }
    }
  }

  async function run(ast,backend,options){validateProgram(ast);var maxSteps=options&&Number.isInteger(options.maxSteps)?options.maxSteps:1000;if(maxSteps<1||maxSteps>100000)fail('invalid execution budget');var budget={remaining:maxSteps};await executeSequence(ast.program,backend,budget,0,options||{},['program']);return{remainingBudget:budget.remaining};}
  return{run:run,evaluate:evaluate,validateProgram:validateProgram};
});
