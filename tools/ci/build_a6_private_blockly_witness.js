'use strict';
// PRIVATE A6 CI REFERENCE ONLY. Never place this algorithm in an activity
// starter, teacher instructions, the product Activity 6 mission or toolbox.
// This checks real Blockly 13.2.1 Save/Open and the semantic interpreter
// against a simulated backend. A physical .wbb Webots run is STILL UNPROVEN.
const assert=require('assert'),fs=require('fs'),path=require('path');
const ROOT=path.resolve(__dirname,'../..');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require('../../plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js');
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
Semantic.installConditionalLoopBounds(Blockly);
delete global.Blockly;
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const ProjectFiles=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');

const n=x=>({kind:'number',value:x});
const ref=name=>({id:'a6-private-'+name,name});
const v=name=>({kind:'variable_get',variable:ref(name)});
const set=(name,value)=>({kind:'set_variable',variable:ref(name),
  value:typeof value==='number'?n(value):value});
const range=direction=>({kind:'range',direction,unit:'m'});
const cmp=(op,left,right)=>({kind:'compare',op,left,
  right:typeof right==='number'?n(right):right});
const ar=(op,left,right)=>({kind:'arithmetic',op,left,
  right:typeof right==='number'?n(right):right});
const both=(left,right)=>({kind:'logic',op:'AND',left,right});
const iff=(condition,then,otherwise)=>({kind:'if',condition,then,
  ...(otherwise&&otherwise.length?{else:otherwise}:{})});
const forward=distance_m=>({kind:'move',direction:'forward',distance_m});

function expectedAst(){
  // Compact private *candidate*, not an approved pupil solution. Exactly two
  // state variables: confirmed H crossings and currently under a H.
  // Sensor reads are immediate and fresh: no copied front/up/step variables.
  // Bounded 80-iteration loop is the native execution limit, not an extra
  // variable or an AST-based criterion for mission success.
  return {version:1,semantics:'webeeblocks-ast-v1',program:[
    set('count',0),set('under',0),
    {kind:'takeoff',height_m:.4},
    {kind:'set_speed',speed_m_s:.2},
    {kind:'while',mode:'WHILE',max_iterations:80,
      condition:cmp('GT',range('front'),.82),
      body:[
        forward(.08),
        iff(both(cmp('LT',range('up'),.75),cmp('LT',range('up'),.75)),[
          set('under',1)
        ],[
          iff(both(cmp('GT',range('up'),1.30),cmp('EQ',v('under'),1)),[
            set('count',ar('ADD',v('count'),1)),
            set('under',0)
          ])
        ])
      ]},
    forward(ar('MINUS',range('front'),.36)),
    iff(cmp('EQ',v('count'),2),[{kind:'move',direction:'left',distance_m:.55}]),
    iff(cmp('EQ',v('count'),3),[{kind:'move',direction:'right',distance_m:.55}]),
    {kind:'land'}
  ]};
}

function privateProfile(){
  const p=Activities.getProfile('reactive-obstacle-v2');
  p.id='progression-count-h-private-ci-only';
  p.brief={visible:false,title:'PRIVATE A6 CI ONLY',
    goal:'Validate serialized Blockly without giving students a solution'};
  p.toolbox=Array.from(new Set(p.toolbox.concat(['controls_whileUntil'])));
  p.fieldOptions=Object.assign({},p.fieldOptions,{
    webeeblocks_v2_range:{DIRECTION:['up','front']},
    webeeblocks_v2_move:{DIRECTION:['forward','left','right']}
  });
  p.runtime.allowedStatementKinds=Array.from(
    new Set(p.runtime.allowedStatementKinds.concat(['while'])));
  p.runtime.rangeDirections=['up','front'];
  p.runtime.moveDirections=['forward','left','right'];
  p.runtime.maxSteps=20000;
  p.runtime.astBounds=Object.assign({},p.runtime.astBounds,{
    'move.distance_m':{min:.01,max:.70},
    'move.forward.distance_m':{min:.01,max:.70},
    'move.lateral.distance_m':{min:.01,max:.60},
    'while.max_iterations':{min:1,max:80}
  });
  return Profiles.resolveById({version:1,activities:[p]},p.id,
    Activities.BLOCK_CATALOG);
}

function build(){
  const expected=expectedAst(),profile=privateProfile();
  const workspace=new Blockly.Workspace();
  function block(type,fields){
    const b=workspace.newBlock(type);
    for(const [k,value] of Object.entries(fields||{}))
      b.setFieldValue(String(value),k);
    return b;
  }
  function input(b,name,child){
    const socket=b.getInput(name);
    if(!socket)throw Error('private Blockly connection unavailable: '+name);
    socket.connection.connect(child.outputConnection||child.previousConnection);
  }
  function variable(x){
    const m=workspace.getVariableMap();
    return m.getVariableById(x.id)||m.createVariable(x.name,'',x.id);
  }
  function expr(e){
    if(e.kind==='number')return block('math_number',{NUM:e.value});
    if(e.kind==='range')return block('webeeblocks_v2_range',{DIRECTION:e.direction});
    if(e.kind==='variable_get')return block('variables_get',{VAR:variable(e.variable).getId()});
    const types={arithmetic:'math_arithmetic',compare:'logic_compare',
      logic:'logic_operation'};
    const b=block(types[e.kind],{OP:e.op});
    input(b,'A',expr(e.left));input(b,'B',expr(e.right));
    return b;
  }
  function sequence(items){
    let first,last;
    for(const e of items){
      let b;
      if(e.kind==='takeoff'){
        b=block('webeeblocks_v2_takeoff');input(b,'HEIGHT',expr(n(e.height_m)));
      }else if(e.kind==='land')b=block('webeeblocks_v2_land');
      else if(e.kind==='set_speed')b=block('webeeblocks_v2_speed',{SPEED:e.speed_m_s});
      else if(e.kind==='move'){
        b=block('webeeblocks_v2_move',{DIRECTION:e.direction});
        input(b,'DISTANCE',expr(typeof e.distance_m==='number'?n(e.distance_m):e.distance_m));
      }else if(e.kind==='set_variable'){
        b=block('variables_set',{VAR:variable(e.variable).getId()});
        input(b,'VALUE',expr(e.value));
      }else if(e.kind==='if'){
        b=block('controls_if');
        if(e.else&&e.else.length)b.loadExtraState({hasElse:true});
        input(b,'IF0',expr(e.condition));
        if(e.then.length)input(b,'DO0',sequence(e.then));
        if(e.else&&e.else.length)input(b,'ELSE',sequence(e.else));
      }else if(e.kind==='while'){
        b=block('controls_whileUntil',{
          MODE:e.mode,MAX_ITERATIONS:e.max_iterations});
        input(b,'BOOL',expr(e.condition));
        input(b,'DO',sequence(e.body));
      }else throw Error('unhandled private AST block '+e.kind);
      if(last)last.nextConnection.connect(b.previousConnection);
      else first=b;
      last=b;
    }
    return first;
  }
  try{
    sequence(expected.program);
    Contract.preflightWorkspace(profile,workspace);
    const ast=Semantic.compileWorkspace(workspace);
    Contract.preflightAst(profile,ast);
    assert.deepStrictEqual(ast,expected);
    Interpreter.validateExecutionBudget(ast,profile.runtime.maxSteps);
    const project={format:'webeeblocks-project',version:1,
      activity:{id:profile.id,semantics:ast.semantics},
      workspace:Blockly.serialization.workspaces.save(workspace)};
    const document={version:1,activities:[profile]};
    const options={Blockly,profiles:Profiles,activitiesDocument:document,
      blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Semantic,
      activityContract:Contract};
    /* Validate, replay and emit the very same canonical .wbb BYTES.
     * The old fixture validated minified bytes but wrote a different
     * pretty-printed file to the native handoff artifact. */
    const text=ProjectFiles.encodeProject(profile,workspace,options);
    /* Blockly.serialization.workspaces.save uses null-prototype maps for
     * fields/inputs. JSON.parse intentionally reconstructs ordinary objects:
     * compare canonical JSON content, not in-memory JS prototypes. */
    assert.equal(JSON.stringify(JSON.parse(text)),JSON.stringify(project),
      'canonical .wbb must encode the exact checked workspace');
    const validated=ProjectFiles.validateProjectText(text,profile,options);
    assert.deepStrictEqual(validated.ast,ast);
    const reopened=new Blockly.Workspace();
    try{
      Blockly.serialization.workspaces.load(project.workspace,reopened);
      Contract.preflightWorkspace(profile,reopened);
      const after=Semantic.compileWorkspace(reopened);
      Contract.preflightAst(profile,after);
      assert.deepStrictEqual(after,ast);
    }finally{reopened.dispose();}
    return {ast,profile,project,text,
      blockCount:workspace.getAllBlocks(false).length,
      variableCount:workspace.getVariableMap().getAllVariables().length};
  }finally{workspace.dispose();}
}

function virtualSensorBackend(numberOfH){
  const gatePositions=[-.85,0,.85].slice(0,numberOfH);
  const self={x:-1.4,y:0,z:0,landed:false,
    actions:[],
    capabilities:{actions:['takeoff','move','set_speed','land'],
      conditionalLoops:true,
      rangeDirections:['up','front'],
      moveDirections:['forward','left','right'],verticalDirections:[]},
    async takeoff(z){this.z=z;this.actions.push('takeoff');},
    async setSpeed(speed){assert.equal(speed,.2);this.actions.push('speed');},
    async move(direction,distance){
      assert(Number.isFinite(distance)&&distance>0&&distance<=.70);
      if(direction==='forward')this.x+=distance;
      else if(direction==='left')this.y+=distance;
      else if(direction==='right')this.y-=distance;
      else throw Error('unsafe private mock direction');
      this.actions.push('move');
    },
    async readRange(direction){
      this.actions.push('read:'+direction);
      if(direction==='front')return Math.max(.01,Math.min(2,1.84-this.x));
      if(direction==='up')
        return gatePositions.some(x=>Math.abs(this.x-x)<=.061)? .20:2.0;
      throw Error('unavailable mock sensor');
    },
    async land(){this.z=0;this.landed=true;this.actions.push('land');}
  };
  return self;
}
async function main(){
  const witness=build(),serialized=witness.text;
  assert(!serialized.includes('count-h-1-v1'));
  assert(!serialized.includes('count-h-2-v1'));
  assert(!serialized.includes('count-h-3-v1'));
  assert.equal(serialized.includes('progression-count-h-private-ci-only'),true);
  const pads=[0,.55,-.55];
  const noLoopCapability=virtualSensorBackend(1);
  noLoopCapability.capabilities.conditionalLoops=false;
  await assert.rejects(
    Interpreter.run(witness.ast,noLoopCapability,{
      maxSteps:20000,motionBounds:witness.profile.runtime.astBounds}),
    /conditional loops unavailable on this backend/);
  assert.equal(noLoopCapability.actions.length,0,
    'missing capability must refuse BEFORE takeoff');
  for(let n=1;n<=3;n++){
    const backend=virtualSensorBackend(n);
    const result=await Interpreter.run(witness.ast,backend,{maxSteps:20000,
      motionBounds:witness.profile.runtime.astBounds});
    assert.equal(result.variables.count,n,'generic Blockly count wrong in mock '+n);
    assert.equal(result.variables.under,0,'last H pulse not closed');
    assert.equal(backend.landed,true);
    assert(Math.abs(backend.x-1.48)<.06,'terminal approach wrong');
    assert(Math.abs(backend.y-pads[n-1])<.06,'pad selection wrong');
    assert(backend.actions.filter(x=>x==='read:up').length>10);
    assert.equal(witness.text,serialized,'same exact .wbb must be reused');
  }
  if(process.argv[2]){
    const dest=path.resolve(process.argv[2]);
    fs.mkdirSync(path.dirname(dest),{recursive:true});
    fs.writeFileSync(dest,serialized,{encoding:'utf8',flag:'wx'});
    assert.equal(fs.readFileSync(dest,'utf8'),serialized,
      'private WBB artifact differs from the MOCK-qualified exact bytes');
  }
  console.log('WEBEEBLOCKS_A6_COMPACT_BLOCKLY_CANDIDATE '+ 
    'blocks='+witness.blockCount+' variables='+witness.variableCount+
    ' physical_webots=UNPROVEN pupil_wbb=UNPROVEN');
  console.log('WEBEEBLOCKS_A6_PRIVATE_BLOCKLY_ROUNDTRIP_OK '+
    'blockly=13.2.1 same_wbb=1 mock_worlds=1,2,3 '+
    'physical_webots=UNPROVEN product_profile=UNPROVEN pupil_starter=EMPTY');
}
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1;});
module.exports={expectedAst,privateProfile,build};
