'use strict';
// CI-only Blockly 13 witness with a REAL while-loop and ONE named variable.
// The test below uses a deterministic MODEL. It proves neither native Webots
// flight nor an authorized pupil Activity 5 or OS Save/Open dialogs.
const assert=require('assert'),fs=require('fs'),path=require('path'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../..');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
global.Blockly=Blockly;
require('../../plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js');
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
Semantic.installConditionalLoopBounds(Blockly);delete global.Blockly;
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const ProjectFiles=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const n=value=>({kind:'number',value});
const ref=name=>({id:'a5-private-'+name,name});
const v=name=>({kind:'variable_get',variable:ref(name)});
const set=(name,value)=>({kind:'set_variable',variable:ref(name),value});
const range=direction=>({kind:'range',direction,unit:'m'});
const cmp=(op,left,right)=>({kind:'compare',op,left,
  right:typeof right==='number'?n(right):right});
const iff=(condition,then,otherwise)=>({kind:'if',condition,then,
  ...(otherwise?.length?{else:otherwise}:{})});
const forward=distance_m=>({kind:'move',direction:'forward',distance_m});
const turn=angle_deg=>({kind:'turn',angle_deg});
function expectedAst(strategy='reactive'){
  if(!['reactive','fixed','snapshot'].includes(strategy))throw Error('invalid private A5 strategy');
  // Unlike the previous private JS pilot, frontal sensing is repeated.
  // Sensor thresholds are hypotheses; native R2025a .wbb remains UNPROVEN.
  return {version:1,semantics:'webeeblocks-ast-v1',program:[
    {kind:'takeoff',height_m:.5},
    {kind:'set_speed',speed_m_s:.2},
    set('destination',range('left')),
    // Fixed-blind adversary intentionally NEVER reads front. The original
    // four scenes have a common 2.4m approach: 12 × (2 × 0.10m).
    // A single front snapshot at the same x≈1.80 m in every world may
    // distinguish short vs long; only motor/C oracle can test success.
    ...(strategy==='snapshot'
      ? [{kind:'repeat',count:18,body:[forward(.1)]},
         iff(cmp('GT',range('front'),1.25),[forward(.9)],[forward(.5)])]
      : [strategy==='fixed'
        ? {kind:'repeat',count:12,body:[forward(.1),forward(.1)]}
        : {kind:'while',mode:'WHILE',max_iterations:32,
            condition:cmp('GT',range('front'),.75),body:[forward(.1)]}]),
    iff(cmp('GT',range('left'),1),[
      turn(90),forward(.6),turn(-90),forward(.85),forward(.8),forward(.1),
      iff(cmp('GT',v('destination'),.8),[turn(-90),forward(1.24)])
    ],[
      turn(-90),forward(.6),turn(90),forward(.85),forward(.8),forward(.1),
      iff(cmp('LTE',v('destination'),.8),[turn(90),forward(1.24)])
    ]),
    // The 0.1m forward correction is inside BOTH G branches, BEFORE
    // the optional 90° lateral shift; the Floor oracle is unchanged.
    {kind:'land'}
  ]};
}
function privateProfile(strategy='reactive'){
  if(!['reactive','fixed','snapshot'].includes(strategy))throw Error('invalid private A5 profile');
  const p=Activities.getProfile('reactive-obstacle-v2');
  p.id=strategy==='fixed'?'progression-reactive-hg-fixed-blind-ci-only':
    strategy==='snapshot'?'progression-reactive-hg-single-snapshot-ci-only':
    'progression-reactive-hg-private-ci-only';
  p.starterVisible=false;p.brief={visible:false,title:'PRIVATE CI ONLY',
    goal:'Test actual Blockly loops and memory without publishing a pupil solution'};
  p.toolbox=Array.from(new Set([...p.toolbox,
    strategy==='reactive'?'controls_whileUntil':'controls_repeat_ext']));
  p.fieldOptions={...p.fieldOptions,
    webeeblocks_v2_range:{DIRECTION:['left','front']},
    webeeblocks_v2_move:{DIRECTION:['forward']},
    webeeblocks_v2_turn:{DIRECTION:['left','right']}};
  p.parameterBounds={...p.parameterBounds,
    webeeblocks_v2_speed:{SPEED:{min:.2,max:.2,step:.01}}};
  p.runtime.allowedStatementKinds=Array.from(
    new Set([...p.runtime.allowedStatementKinds,strategy==='reactive'?'while':'repeat']));
  p.runtime.rangeDirections=['left','front'];
  p.runtime.moveDirections=['forward'];p.runtime.maxSteps=20000;
  p.runtime.astBounds={...p.runtime.astBounds,
    'move.distance_m':{min:.1,max:1.24},
    'move.forward.distance_m':{min:.1,max:1.24},
    'takeoff.height_m':{min:.5,max:.5},
    'set_speed.speed_m_s':{min:.2,max:.2},
    'turn.angle_deg_abs':{min:90,max:90},
    'while.max_iterations':{min:1,max:32}};
  return Profiles.resolveById({version:1,activities:[p]},p.id,
    Activities.BLOCK_CATALOG);
}
function build(strategy='reactive'){
  const expected=expectedAst(strategy),profile=privateProfile(strategy);
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
      }else if(e.kind==='turn'){
        b=block('webeeblocks_v2_turn',{
          DIRECTION:e.angle_deg>0?'left':'right',ANGLE:Math.abs(e.angle_deg)});
      }else if(e.kind==='set_variable'){
        b=block('variables_set',{VAR:variable(e.variable).getId()});
        input(b,'VALUE',expr(e.value));
      }else if(e.kind==='if'){
        b=block('controls_if');
        if(e.else&&e.else.length)b.loadExtraState({hasElse:true});
        input(b,'IF0',expr(e.condition));
        if(e.then.length)input(b,'DO0',sequence(e.then));
        if(e.else&&e.else.length)input(b,'ELSE',sequence(e.else));
      }else if(e.kind==='repeat'){
        b=block('controls_repeat_ext');
        input(b,'TIMES',expr(n(e.count)));
        input(b,'DO',sequence(e.body));
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
    // Blockly 13 creates a default orphan "item" while constructing the
    // first variable block. Never leak that unused variable into the saved
    // classroom project: only the two declared states are legitimate.
    const variables=workspace.getVariableMap();
    for(const candidate of variables.getAllVariables()){
      if(candidate.name!=='item')continue;
      const id=candidate.getId();
      const referenced=workspace.getAllBlocks(false).some(b=>{
        const field=b.getField('VAR');
        return field&&field.getValue()===id;
      });
      assert.equal(referenced,false,'default item variable unexpectedly used');
      // Blockly 13 VariableMap.deleteVariable(model) is the supported,
      // non-interactive deletion API. Neither deleteVariableById method
      // exists on Blockly 13's Workspace or VariableMap.
      variables.deleteVariable(candidate);
    }
    assert.deepStrictEqual(
      variables.getAllVariables().map(x=>x.name).sort(),
      ['destination'],'A5 private proof must contain one memory variable');
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


function virtualBackend(HFar,GLeft,opts={}){
  const self={x:0,y:0,z:0,angle:0,landed:false,actions:[],
    frontReads:0,initialLeft:0,lateLeft:0,
    capabilities:{actions:['takeoff','move','turn','set_speed','land'],
      conditionalLoops:true,rangeDirections:['front','left'],
      moveDirections:['forward'],verticalDirections:[]},
    async takeoff(h){this.z=h;this.actions.push('takeoff');},
    async setSpeed(s){assert.equal(s,.2);this.actions.push('speed');},
    async move(dir,d){
      assert.equal(dir,'forward');assert(d>=.1&&d<=1.24);
      this.x+=d*Math.cos(this.angle*Math.PI/180);
      this.y+=d*Math.sin(this.angle*Math.PI/180);
      this.actions.push('move');
    },
    async turn(a){assert(Math.abs(a)===90);this.angle+=a;this.actions.push('turn');},
    async readRange(direction){
      if(direction==='front'){this.frontReads++;return Math.max(.01,Math.min(2,3.065-this.x));}
      assert.equal(direction,'left');
      if(this.x<2){this.initialLeft++;return opts.blindH?.54:(HFar?1.14:.54);}
      this.lateLeft++;return opts.blindG?1.41:(GLeft?1.41:.54);
    },
    async land(){this.z=0;this.landed=true;this.actions.push('land');}
  };return self;
}
async function main(){
  const retired=Activities.getProfile('progression-reactive-v1');
  assert.equal(retired.starterVisible,false);
  assert(!retired.toolbox.includes('variables_set'));
  assert(!retired.toolbox.includes('controls_whileUntil'));
  const w=build('reactive'),fixed=build('fixed'),snapshot=build('snapshot');
  assert.equal(snapshot.variableCount,1);
  assert.equal(snapshot.ast.program[3].kind,'repeat');
  assert.equal(snapshot.ast.program[3].count,18);
  assert.equal(snapshot.ast.program[3].body.length,1);
  assert.equal(snapshot.ast.program[4].kind,'if');
  assert.equal((JSON.stringify(snapshot.ast).match(/"direction":"front"/g)||[]).length,1,
    'snapshot adversary must read front precisely once, never inside loop');
  assert(!JSON.stringify(snapshot.ast.program[3]).includes('"direction":"front"'));
  assert.notEqual(snapshot.text,w.text);
  assert.notEqual(snapshot.text,fixed.text);
  assert.equal(JSON.parse(snapshot.text).activity.id,
    'progression-reactive-hg-single-snapshot-ci-only');
  assert.equal(w.variableCount,1);
  assert.equal(fixed.variableCount,1);
  assert.equal(fixed.ast.program[3].kind,'repeat');
  assert.equal(fixed.ast.program[3].count,12);
  assert.equal(fixed.ast.program[3].body.length,2);
  assert(!JSON.stringify(fixed.ast).includes('"direction":"front"'),
    'blind fixed repeat must never read the front range');
  assert.notEqual(fixed.text,w.text);
  assert.equal(JSON.parse(fixed.text).activity.id,
    'progression-reactive-hg-fixed-blind-ci-only');
  assert.equal(w.ast.program[3].kind,'while');
  assert(w.blockCount>18);
  assert(!/hfar-gleft|hfar-gright|reactive-L-factor-/.test(w.text));
  const bytes=w.text,hash=crypto.createHash('sha256').update(bytes).digest('hex');
  const results=[],fixedResults=[];
  const fixedSha=crypto.createHash('sha256').update(fixed.text).digest('hex');
  for(const H of [false,true])for(const G of [true,false]){
    const b=virtualBackend(H,G);
    const executed=await Interpreter.run(w.ast,b,{
      maxSteps:w.profile.runtime.maxSteps,
      motionBounds:w.profile.runtime.astBounds});
    assert(b.landed&&Math.abs(b.x-4.15)<.05&&
           Math.abs(b.y-(H?-.62:.62))<.05,
           'deterministic private model should reach correct pad');
    assert.equal(b.initialLeft,1);assert.equal(b.lateLeft,1);
    assert(b.frontReads>=21&&b.frontReads<=32,
           'front must be freshly sensed on every approach iteration');
    assert.equal(executed.variables.destination,H?1.14:.54);
    results.push({HFar:H,GLeft:G,frontReads:b.frontReads,
      initialValue:executed.variables.destination,x:b.x,y:b.y});
    const blind=virtualBackend(H,G);
    // A fixed repeat is permitted on a backend WITHOUT conditional loops.
    blind.capabilities.conditionalLoops=false;
    const blindRun=await Interpreter.run(fixed.ast,blind,{
      maxSteps:fixed.profile.runtime.maxSteps,
      motionBounds:fixed.profile.runtime.astBounds});
    assert(blind.landed && blind.frontReads===0,
      'the blind competitor must finish without a front-range reading');
    assert(Math.abs(blind.x-b.x)<1e-9&&Math.abs(blind.y-b.y)<1e-9,
      'the four original worlds cannot discriminate a fixed from a reactive approach');
    assert.equal(blindRun.variables.destination,executed.variables.destination);
    fixedResults.push({HFar:H,GLeft:G,frontReads:blind.frontReads,
      finalX:blind.x,finalY:blind.y});
  }
  const blindH=virtualBackend(true,true,{blindH:true});
  await Interpreter.run(w.ast,blindH,{maxSteps:20000,
    motionBounds:w.profile.runtime.astBounds});
  assert(Math.abs(blindH.y-.62)<.05&&Math.abs(blindH.y+.62)>1.0);
  const noLoop=virtualBackend(false,true);
  noLoop.capabilities.conditionalLoops=false;
  await assert.rejects(Interpreter.run(w.ast,noLoop,{
    maxSteps:20000,motionBounds:w.profile.runtime.astBounds}),
    /conditional loops unavailable on this backend/);
  assert.equal(noLoop.actions.length,0);
  const output=ROOT+'/ci-artifacts/progression-reactive-L-factor-blockly';
  fs.mkdirSync(output,{recursive:true});
  fs.writeFileSync(path.join(output,'a5-private-loop-state-ci-only.wbb'),bytes,'utf8');
  fs.writeFileSync(path.join(output,'a5-private-fixed-front-ci-only.wbb'),
    fixed.text,'utf8');
  fs.writeFileSync(path.join(output,'a5-private-single-snapshot-ci-only.wbb'),
    snapshot.text,'utf8');
  fs.writeFileSync(path.join(output,'summary.json'),JSON.stringify({
    schema:'webeeblocks-a5-private-blockly-loop-memory-v1',
    model_pass:true,sha256:hash,block_count:w.blockCount,
    variable_count:w.variableCount,variants:results,
    native_2x2_from_this_wbb:false,real_webots_oracle:false,
    pupil_activity_published:false,os_save_open:false,
    blind_G_collision_rejection_from_this_wbb:false,
    fixed_front_adversary_virtual_four_pass:true,
    fixed_front_sha256:fixedSha,
    single_snapshot_sha256:crypto.createHash('sha256').update(snapshot.text).digest('hex'),
    snapshot_front_reads_structurally_one:true,
    snapshot_native_four_worlds: 'UNPROVEN',
    fixed_front_four_native_proven:false,
    fixed_front_virtual_variants:fixedResults
  },null,2)+'\n','utf8');
  console.log('WEBEEBLOCKS_A5_PRIVATE_SNAPSHOT_PROJECT_BUILT one_front_read=true '+
    'source_roundtrip=true native_four_worlds=UNPROVEN sha256='+
    crypto.createHash('sha256').update(snapshot.text).digest('hex'));
  console.log('WEBEEBLOCKS_A5_PRIVATE_FIXED_FRONT_MODEL_PASS '+
    'four_mock_variants=true no_front_range=true 12_x_2_moves=true '+
    'native_fixed_worlds=UNPROVEN sha256='+fixedSha);
  console.log('WEBEEBLOCKS_A5_PRIVATE_BLOCKLY_LOOP_MEMORY_MODEL_PASS '+
    'wbb_roundtrip=true loop_front_fresh=true one_variable=true '+
    'four_mock_variants=true native_wbb_flight=UNPROVEN sha256='+hash);
}
main().catch(e=>{console.error(e);process.exitCode=1;});
