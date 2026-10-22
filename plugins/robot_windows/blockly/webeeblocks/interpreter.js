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
  var LIGHT_COLORS=['off','red','green','blue','yellow','white'];
  var COMPARE_OPS=['LT','LTE','GT','GTE','EQ','NEQ'];
  var ARITHMETIC_OPS=['ADD','MINUS','MULTIPLY','DIVIDE'];
  function fail(message){throw new Error('runtime v2: '+message);}
  function studentFail(message,detail){var error=new Error('runtime v2: '+message);error.code='PROGRAM_INVALID';error.studentDetail=detail;throw error;}
  function finite(value,name){var n=Number(value);if(!Number.isFinite(n))fail(name+' must be finite');return n;}
  function numeric(value,name){if(typeof value!=='number'||!Number.isFinite(value))studentFail(name+' must be a finite number','Vérifiez les valeurs utilisées dans le calcul.');return value;}
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
      case 'elapsed_time':if(expression.unit!=='s')fail('unsupported elapsed time unit');return;
      case 'range':if(SENSOR_DIRECTIONS.indexOf(String(expression.direction))<0||expression.unit!=='m')fail('unsupported range expression');return;
      case 'variable_get':{var ref=rememberVariable(variables,expression.variable);if(!assigned.has(ref.id))fail('variable read before assignment: '+ref.name);return;}
      case 'arithmetic':if(ARITHMETIC_OPS.indexOf(String(expression.op))<0)fail('unsupported arithmetic operation '+expression.op);validateExpression(expression.left,depth+1,assigned,variables);validateExpression(expression.right,depth+1,assigned,variables);return;
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
        case 'guarded_move':{
          var max=statement.max_distance_m,threshold=statement.threshold_m;
          if(typeof max!=='number'||!Number.isFinite(max)||max<0.1||max>2||Math.abs(max*10-Math.round(max*10))>1e-9)fail('guarded maximum must be 0.1 to 2 m in 0.1 m increments');
          if(typeof threshold!=='number'||!Number.isFinite(threshold)||threshold<0.25||threshold>1.5)fail('guarded threshold out of bounds');
          var progress=rememberVariable(variables,statement.progress);
          if(!assigned.has(progress.id))fail('variable read before assignment: '+progress.name);
          validateSequence(statement.on_sensor,depth+1,true,cloneSet(assigned),variables);
          break; // The sensor body can execute zero times; it grants no assignments.
        }
        case 'takeoff':finite(statement.height_m,'height_m');break;
        case 'land':break;
        case 'move':if(MOVE_DIRECTIONS.indexOf(String(statement.direction))<0)fail('unsupported move direction '+statement.direction);finite(statement.distance_m,'distance_m');break;
        case 'vertical':if(VERTICAL_DIRECTIONS.indexOf(String(statement.direction))<0)fail('unsupported vertical direction '+statement.direction);finite(statement.distance_m,'distance_m');break;
        case 'turn':finite(statement.angle_deg,'angle_deg');break;
        case 'wait':finite(statement.seconds,'seconds');break;
        case 'set_speed':finite(statement.speed_m_s,'speed_m_s');break;
        case 'set_light':if(LIGHT_COLORS.indexOf(String(statement.color))<0)fail('unsupported light color '+statement.color);break;
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
        case 'while':{
          if(statement.mode!=='WHILE'&&statement.mode!=='UNTIL')fail('unsupported loop mode');
          if(!Number.isInteger(statement.max_iterations)||statement.max_iterations<1||statement.max_iterations>100)fail('loop iteration limit out of bounds');
          validateExpression(statement.condition,depth+1,assigned,variables);
          validateSequence(statement.body,depth+1,true,cloneSet(assigned),variables);
          break; // A conditional loop can execute zero times.
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

  // Conservative cost only: no expression evaluation or branch selection.
  // The physical host must prove the existing runtime budget before takeoff.
  function validateExecutionBudget(ast,maxSteps){
    validateProgram(ast);
    maxSteps=maxSteps===undefined?1000:maxSteps;
    if(!Number.isInteger(maxSteps)||maxSteps<1||maxSteps>100000)fail('invalid execution budget');
    function expressionCost(node){
      return 1+((node.kind==='arithmetic'||node.kind==='compare'||node.kind==='logic')
        ?expressionCost(node.left)+expressionCost(node.right):0);
    }
    function sequenceCost(sequence){
      var cost=0;
      sequence.forEach(function(node){
        cost+=1;
        if(node.kind==='guarded_move')cost+=3*Math.round(node.max_distance_m*10)+1+sequenceCost(node.on_sensor);
        if(node.kind==='set_variable')cost+=expressionCost(node.value);
        if(node.kind==='if')cost+=expressionCost(node.condition)+Math.max(sequenceCost(node.then),sequenceCost(node.else||[]));
        if(node.kind==='while')cost+=(node.max_iterations+1)*expressionCost(node.condition)+node.max_iterations*(1+sequenceCost(node.body));
        if(node.kind==='repeat')cost+=node.count*sequenceCost(node.body);
        if(cost>maxSteps)fail('reachable execution exceeds runtime budget before takeoff');
      });
      return cost;
    }
    return sequenceCost(ast.program);
  }

  async function evaluate(expression,backend,budget,depth,options,path,env){
    env=env||environment();
    budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');
    var current=context(expression,path,'expression',env);
    await hook(options,'onNode',current);
    switch(expression.kind){
      case 'number':await hook(options,'beforeStep',current);return Number(expression.value);
      case 'variable_get':{var ref=variableRef(expression.variable);await hook(options,'beforeStep',current);if(!Object.prototype.hasOwnProperty.call(env.values,ref.id))fail('variable read before assignment: '+ref.name);if(env.names[ref.id]&&env.names[ref.id]!==ref.name)fail('variable id/name mismatch: '+ref.id);return env.values[ref.id];}
      case 'elapsed_time':{
        await hook(options,'beforeStep',current);
        var seconds=await requireMethod(backend,'readElapsedTime')();
        if(typeof seconds!=='number'||!Number.isFinite(seconds)||seconds<0)fail('elapsed time must be a finite nonnegative number');
        return seconds;
      }
      case 'range':{
        await hook(options,'beforeStep',current);
        var value=finite(await requireMethod(backend,'readRange')(String(expression.direction)),'range('+expression.direction+')');
        await hook(options,'onSensor',{node:expression,path:(path||[]).slice(),role:'expression',variables:snapshot(env),direction:String(expression.direction),value:value});
        return value;
      }
      case 'arithmetic':{
        var arithmeticLeft=numeric(await evaluate(expression.left,backend,budget,depth+1,options,(path||[]).concat('left'),env),'left arithmetic operand');
        var arithmeticRight=numeric(await evaluate(expression.right,backend,budget,depth+1,options,(path||[]).concat('right'),env),'right arithmetic operand');
        await hook(options,'beforeStep',context(expression,path,'expression',env));
        if(expression.op==='DIVIDE'&&arithmeticRight===0)studentFail('division by zero','Une division par zéro est impossible. Modifiez le diviseur.');
        var arithmeticResult;
        if(expression.op==='ADD')arithmeticResult=arithmeticLeft+arithmeticRight;
        else if(expression.op==='MINUS')arithmeticResult=arithmeticLeft-arithmeticRight;
        else if(expression.op==='MULTIPLY')arithmeticResult=arithmeticLeft*arithmeticRight;
        else arithmeticResult=arithmeticLeft/arithmeticRight;
        if(!Number.isFinite(arithmeticResult))studentFail('arithmetic result must be finite','Le calcul produit une valeur invalide. Vérifiez les nombres utilisés.');
        return arithmeticResult;
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

  function abortGuarded(options){
    if(options&&options.signal&&options.signal.aborted){var error=new Error('guarded movement cancelled');error.code='USER_STOPPED';throw error;}
  }
  function guardedNodes(sequence){
    var found=[];
    (sequence||[]).forEach(function(node){
      if(node.kind==='guarded_move')found.push(node);
      ['body','then','else','on_sensor'].forEach(function(key){if(node[key])found=found.concat(guardedNodes(node[key]));});
    });return found;
  }
  function preflightGuarded(ast,backend){
    var nodes=guardedNodes(ast.program);
    if(!nodes.length)return false;
    var cap=backend&&backend.capabilities;
    if(!cap||cap.guardedMove!==true||!Array.isArray(cap.actions)||cap.actions.indexOf('move')<0||
       !Array.isArray(cap.rangeDirections)||cap.rangeDirections.indexOf('front')<0||
       !Array.isArray(cap.moveDirections)||cap.moveDirections.indexOf('forward')<0)fail('guarded movement unavailable on this backend');
    ['move','readRange','getMotionEpoch'].forEach(function(name){requireMethod(backend,name);});
    var epoch=backend.getMotionEpoch();if(typeof epoch!=='string'||!epoch)fail('guarded motion epoch unavailable');
    return true;
  }
  async function executeGuarded(statement,backend,budget,depth,options,path,env){
    var epoch=backend.getMotionEpoch(),ref=variableRef(statement.progress),steps=Math.round(statement.max_distance_m*10);
    if(typeof epoch!=='string'||!epoch)fail('guarded motion epoch unavailable');
    function check(){abortGuarded(options);if(backend.getMotionEpoch()!==epoch)fail('guarded motion epoch changed');}
    function spend(){budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');}
    for(var completed=0;completed<=steps;completed++){
      check();spend();
      var sample=context(statement,path,'statement',env,{phase:'range',iteration:completed});
      await hook(options,'onNode',sample);await hook(options,'beforeStep',sample);check();
      var distance=await backend.readRange('front');check();
      // 2 m is the WWI sensor's saturated lower-bound return, NOT an exact range.
      if(typeof distance!=='number'||!Number.isFinite(distance)||distance<0||distance>2.001)fail('guarded range must be finite and within sensor bounds');
      await hook(options,'onSensor',Object.assign({},sample,{direction:'front',value:distance}));check();
      if(distance<=statement.threshold_m){
        await executeSequence(statement.on_sensor,backend,budget,depth+1,options,path.concat('on_sensor'),env);
        return;
      }
      if(completed===steps)return;
      var prior=numeric(env.values[ref.id],'commanded progression'),next=prior+0.1;
      if(!Number.isFinite(next)||next===prior)fail('commanded progression cannot advance');
      spend();var motion=context(statement,path,'statement',env,{phase:'move',iteration:completed});
      await hook(options,'onNode',motion);await hook(options,'beforeStep',motion);check();
      var ack=await backend.move('forward',0.1);
      // No retry and no accounting on unknown/malformed/stale completion.
      if(backend.getMotionEpoch()!==epoch)fail('guarded motion epoch changed');
      if(ack!==null)fail('guarded move requires an unambiguous OK acknowledgement');
      spend();env.values[ref.id]=next;env.names[ref.id]=ref.name;
      await hook(options,'onVariables',context(statement,path,'statement',env,{variable:ref,values:snapshot(env)}));
      check();
    }
  }

  async function executeSequence(sequence,backend,budget,depth,options,prefix,env){
    for(var i=0;i<sequence.length;i++){
      abortGuarded(options);
      budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');
      var statement=sequence[i],path=(prefix||[]).concat(i),current=context(statement,path,'statement',env);
      await hook(options,'onNode',current);
      switch(statement.kind){
        case 'guarded_move':await executeGuarded(statement,backend,budget,depth,options,path,env);break;
        case 'takeoff':await hook(options,'beforeStep',current);await requireMethod(backend,'takeoff')(Number(statement.height_m));break;
        case 'land':await hook(options,'beforeStep',current);await requireMethod(backend,'land')();break;
        case 'move':await hook(options,'beforeStep',current);await requireMethod(backend,'move')(String(statement.direction),Number(statement.distance_m));break;
        case 'vertical':await hook(options,'beforeStep',current);await requireMethod(backend,'vertical')(String(statement.direction),Number(statement.distance_m));break;
        case 'turn':await hook(options,'beforeStep',current);await requireMethod(backend,'turn')(Number(statement.angle_deg));break;
        case 'wait':await hook(options,'beforeStep',current);await requireMethod(backend,'wait')(Number(statement.seconds));break;
        case 'set_speed':await hook(options,'beforeStep',current);await requireMethod(backend,'setSpeed')(Number(statement.speed_m_s));break;
        case 'set_light':{var lightColor=String(statement.color);await hook(options,'beforeStep',current);await requireMethod(backend,'setLight')(lightColor);await hook(options,'onLight',{node:statement,path:path.slice(),role:'statement',variables:snapshot(env),color:lightColor});break;}
        case 'set_variable':{
          var ref=variableRef(statement.variable),stored=await evaluate(statement.value,backend,budget,depth+1,options,path.concat('value'),env);
          await hook(options,'beforeStep',context(statement,path,'statement',env));env.values[ref.id]=stored;env.names[ref.id]=ref.name;
          await hook(options,'onVariables',{node:statement,path:path.slice(),role:'statement',variables:snapshot(env),variable:ref,values:snapshot(env)});break;
        }
        case 'if':{var condition=Boolean(await evaluate(statement.condition,backend,budget,depth+1,options,path.concat('condition'),env));await hook(options,'beforeStep',context(statement,path,'statement',env));await executeSequence(condition?statement.then:(statement.else||[]),backend,budget,depth+1,options,path.concat(condition?'then':'else'),env);break;}
        case 'while':{
          var iteration=0;
          for(;;){
            var loopCondition=Boolean(await evaluate(statement.condition,backend,budget,depth+1,options,path.concat('condition'),env));
            if(statement.mode==='UNTIL'?loopCondition:!loopCondition)break;
            if(iteration>=statement.max_iterations)fail('conditional loop iteration limit exceeded');
            budget.remaining-=1;if(budget.remaining<0)fail('execution budget exceeded');
            await hook(options,'beforeStep',context(statement,path,'statement',env,{iteration:iteration}));
            await executeSequence(statement.body,backend,budget,depth+1,options,path.concat('body'),env);
            iteration+=1;
          }
          break;
        }
        case 'repeat':for(var repeat=0;repeat<statement.count;repeat++){await hook(options,'beforeStep',context(statement,path,'statement',env,{iteration:repeat}));await executeSequence(statement.body,backend,budget,depth+1,options,path.concat('body'),env);}break;
      }
    }
  }

  function containsConditionalLoop(sequence){return sequence.some(function(node){return node.kind==='while'||(node.kind==='repeat'&&containsConditionalLoop(node.body))||(node.kind==='guarded_move'&&containsConditionalLoop(node.on_sensor))||(node.kind==='if'&&(containsConditionalLoop(node.then)||containsConditionalLoop(node.else||[])));});}
  function containsElapsedTime(sequence){
    function expression(node){return node && (node.kind==='elapsed_time'||expression(node.left)||expression(node.right));}
    return sequence.some(function(node){return expression(node.value)||expression(node.condition)||(node.on_sensor&&containsElapsedTime(node.on_sensor))||(node.body&&containsElapsedTime(node.body))||(node.then&&containsElapsedTime(node.then))||(node.else&&containsElapsedTime(node.else));});
  }
  async function run(ast,backend,options){validateProgram(ast);var guarded=preflightGuarded(ast,backend);if(guarded)abortGuarded(options);if(containsElapsedTime(ast.program)&&!(backend&&backend.capabilities&&backend.capabilities.elapsedSimulationTime===true&&typeof backend.readElapsedTime==='function'))fail('elapsed simulation time unavailable on this backend');if(containsConditionalLoop(ast.program)&&!(backend&&backend.capabilities&&backend.capabilities.conditionalLoops===true))fail('conditional loops unavailable on this backend');var maxSteps=options&&Number.isInteger(options.maxSteps)?options.maxSteps:1000;if(maxSteps<1||maxSteps>100000)fail('invalid execution budget');if(guarded||containsConditionalLoop(ast.program))validateExecutionBudget(ast,maxSteps);var budget={remaining:maxSteps},env=environment();await executeSequence(ast.program,backend,budget,0,options||{},['program'],env);return{remainingBudget:budget.remaining,variables:snapshot(env)};}
  return{run:run,evaluate:evaluate,validateProgram:validateProgram,validateExecutionBudget:validateExecutionBudget};
});
