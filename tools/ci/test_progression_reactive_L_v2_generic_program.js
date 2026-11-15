'use strict';
/* TEST-ONLY A5 v2 whole-algorithm witness, never an activity starter.
 * A real Blockly 13 .wbb, unchanged A/B/C, exercises bounded re-observation
 * and delayed use of historical sensor state AFTER a common 90-degree turn.
 * The new front ray after the pivot may recover the old left ray.
 * Test a genuinely variable-free competing Blockly project as well.
 * This fixture uses MOCK ranges/dynamics only; physical necessity of this
 * memory and real Webots/pupil flight MUST be independently falsified.
 */
const assert=require('node:assert/strict');
const path=require('node:path');
const crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..');
const Blockly=require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly'));
require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
const Activities=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Contract=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const Compiler=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));
const Interpreter=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/interpreter.js'));
const Files=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/project_files.js'));
global.Blockly=Blockly;
require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js'));
delete global.Blockly;
Compiler.installConditionalLoopBounds(Blockly);
const base=Profiles.resolveById(Activities.DOCUMENT,'progression-reactive-L-v2',Activities.BLOCK_CATALOG);
const options={Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,
  blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Compiler,activityContract:Contract};
function build(remember=true){
  const w=new Blockly.Workspace();
  const state=remember?w.getVariableMap().createVariable('observation mémorisée','','a5-v2-memory'):null;
  const block=t=>w.newBlock(t);
  const num=x=>{const n=block('math_number');n.setFieldValue(String(x),'NUM');return n;};
  const put=(b,input,e)=>{b.getInput(input).connection.connect(e.outputConnection);return b;};
  const link=(...bs)=>{for(let i=1;i<bs.length;i++)
    bs[i-1].nextConnection.connect(bs[i].previousConnection);};
  const move=x=>{const b=block('webeeblocks_v2_move');b.setFieldValue('forward','DIRECTION');
    put(b,'DISTANCE',num(x));return b;};
  const turn=d=>{const b=block('webeeblocks_v2_turn');
    b.setFieldValue(d,'DIRECTION');b.setFieldValue('90','ANGLE');return b;};
  const range=d=>{const b=block('webeeblocks_v2_range');
    b.setFieldValue(d,'DIRECTION');return b;};
  const get=()=>{const b=block('variables_get');b.getField('VAR').setValue(state.getId());return b;};
  const cmp=(op,a,b)=>{const c=block('logic_compare');c.setFieldValue(op,'OP');
    put(c,'A',a);put(c,'B',b);return c;};
  const untilWall=()=>{const c=block('controls_whileUntil');
    c.setFieldValue('WHILE','MODE');
    if(!c.getField('MAX_ITERATIONS'))throw Error('bounded while field absent');
    c.setFieldValue('12','MAX_ITERATIONS');
    put(c,'BOOL',cmp('GT',range('front'),num(.24)));
    c.getInput('DO').connection.connect(move(.10).previousConnection);
    return c;};
  const takeoff=block('webeeblocks_v2_takeoff');put(takeoff,'HEIGHT',num(.5));
  const speed=block('webeeblocks_v2_speed');speed.setFieldValue('0.10','SPEED');
  const first=untilWall(),left=turn('left'),second=untilWall();
  const store=remember?block('variables_set'):null;
  if(store){store.getField('VAR').setValue(state.getId());put(store,'VALUE',range('left'));}
  // First preserve the left-looking westward observation while facing north.
  // A common turn then changes the left sensor's physical viewing direction.
  // The competing branch uses the current front sensor after rotation.
  const pivot=turn('left');
  const choose=block('controls_if');choose.loadExtraState({elseIfCount:1,hasElse:true});
  put(choose,'IF0',cmp('LT',remember?get():range('front'),num(.6)));
  const a=[turn('right'),turn('right'),move(.78)];link(...a);
  choose.getInput('DO0').connection.connect(a[0].previousConnection);
  put(choose,'IF1',cmp('GT',remember?get():range('front'),num(1.6)));
  const b=[move(1.42)];link(...b);
  choose.getInput('DO1').connection.connect(b[0].previousConnection);
  const c=[move(1.25),turn('right'),move(.60)];link(...c);
  choose.getInput('ELSE').connection.connect(c[0].previousConnection);
  const land=block('webeeblocks_v2_land');
  if(remember)link(takeoff,speed,first,left,second,store,pivot,choose,land);
  else link(takeoff,speed,first,left,second,pivot,choose,land);
  return w;
}
function backend(variant){
  let x=0,y=0,heading=0,airborne=false;
  const records=[],reads=[];
  function round(v){return Math.round(v*100)/100;}
  return{
    records,reads,
    capabilities:{actions:['takeoff','set_speed','move','turn','land'],
      rangeDirections:['front','left'],moveDirections:['forward'],
      verticalDirections:[],conditionalLoops:true,elapsedSimulationTime:false},
    async takeoff(h){records.push(['takeoff',h]);airborne=true;},
    async setSpeed(speed){records.push(['speed',speed]);},
    async move(dir,m){
      assert(airborne);
      assert.equal(dir,'forward');
      assert(m>.09&&m<1.51);
      const theta=heading*Math.PI/180;
      x=round(x+Math.cos(theta)*m);y=round(y+Math.sin(theta)*m);
      records.push(['move',m,round(x),round(y)]);
    },
    async turn(degrees){heading=(heading+degrees+360)%360;
      records.push(['turn',degrees,heading]);},
    async readRange(direction){
      reads.push([direction,round(x),round(y),heading]);
      records.push(['range',direction,round(x),round(y),heading]);
      if(direction==='front'){
        if(heading===0)return round(.98-x);
        if(heading===90&&x>=.7)return round(1.21-y);
        if(heading===180&&Math.abs(x-.8)<.02&&Math.abs(y-1)<.02)
          return {A:.28,B:1.78,C:1.44}[variant];
        throw Error('fixture sampled front in unmodelled stage');
      }
      if(direction==='left'){
        if(heading!==90||Math.abs(x-.8)>.02||Math.abs(y-1)>.02)
          throw Error('left classification before second physical stage');
        return {A:.28,B:1.78,C:1.44}[variant];
      }
      throw Error('forbidden sensor: '+direction);
    },
    async land(){records.push(['land',round(x),round(y),heading]);airborne=false;},
    pose:()=>({x:round(x),y:round(y),heading,airborne}),
  };
}
async function main(){
  const source=build();
  try{
    Contract.preflightWorkspace(base,source);
    const ast=Compiler.compileWorkspace(source);
    Contract.preflightAst(base,ast);
    assert.equal(ast.program.length,9);
    assert.equal(ast.program.filter(x=>x.kind==='while').length,2);
    assert.equal(ast.program.filter(x=>x.kind==='set_variable').length,1);
    assert.equal(ast.program.filter(x=>x.kind==='if').length,1);
    const text=Files.encodeProject(base,source,options);
    const sha=crypto.createHash('sha256').update(text).digest('hex');
    let readings=[];
    for(const [variant,scene,expect] of [
      ['A','reactive-L-a-v2',{x:1.58,y:1,heading:0}],
      ['B','reactive-L-b-v2',{x:-.62,y:1,heading:180}],
      ['C','reactive-L-c-v2',{x:-.45,y:1.6,heading:90}],
    ]){
      const profile=JSON.parse(JSON.stringify(base));profile.runtime.scene=scene;
      const same=Files.encodeProject(profile,source,options);
      assert.equal(same,text,'scene leaked into saved student workspace');
      const validated=Files.validateProjectText(text,profile,options);
      assert.equal(validated.project.activity.id,base.id);
      const reopened=new Blockly.Workspace();
      try{
        Blockly.serialization.workspaces.load(validated.project.workspace,reopened);
        Contract.applyFieldBounds(profile,reopened);
        const real=Compiler.compileWorkspace(reopened);
        assert.deepEqual(real,ast,'native profile switch changed Blockly AST');
        const b=backend(variant);
        await Interpreter.run(real,b,{motionBounds:profile.runtime.astBounds});
        assert.deepEqual(b.pose(),{...expect,airborne:false});
        assert.equal(b.reads.filter(x=>x[0]==='front').length,20);
        assert.equal(b.reads.filter(x=>x[0]==='left').length,1);
        // The range read is in the old physical frame (north-facing drone
        // looks west with its left sensor). The decision is deliberately
        // deferred until the drone has rotated into the new frame.
        const oldLeft=b.records.findIndex(x=>x[0]==='range'&&x[1]==='left');
        const pivotTurn=b.records.findIndex((x,i)=>i>oldLeft&&
          x[0]==='turn'&&x[2]===180);
        assert(oldLeft>=0&&pivotTurn>oldLeft,
          'saved observation must precede common orientation change');
        assert.equal(b.records[oldLeft][4],90);
        assert.equal(b.reads.filter(x=>x[0]==='left'&&x[3]===180).length,0,
          'classification may not re-read a now reoriented sensor');
        assert.equal(b.records.filter(x=>x[0]==='land').length,1);
        readings.push({variant,left:{A:.28,B:1.78,C:1.44}[variant],
          steps:b.reads.length,final:b.pose()});
      }finally{reopened.dispose();}
    }
    // Adversarial no-memory version: same trajectories/loops, but the
    // post-pivot front sensor replaces the older stored left value.
    const alternative=build(false);
    let alternativeText,alternativeSha;
    try {
      Contract.preflightWorkspace(base,alternative);
      const alternativeAst=Compiler.compileWorkspace(alternative);
      Contract.preflightAst(base,alternativeAst);
      assert.equal(alternativeAst.program.length,8);
      assert.equal(alternativeAst.program.filter(x=>x.kind==='while').length,2);
      assert.equal(alternativeAst.program.filter(x=>x.kind==='set_variable').length,0);
      assert.equal(alternativeAst.program.filter(x=>x.kind==='if').length,1);
      alternativeText=Files.encodeProject(base,alternative,options);
      alternativeSha=crypto.createHash('sha256').update(alternativeText).digest('hex');
      assert.notEqual(alternativeSha,sha);
      for(const [variant,scene,expect] of [
        ['A','reactive-L-a-v2',{x:1.58,y:1,heading:0}],
        ['B','reactive-L-b-v2',{x:-.62,y:1,heading:180}],
        ['C','reactive-L-c-v2',{x:-.45,y:1.6,heading:90}]
      ]){
        const profile=JSON.parse(JSON.stringify(base));profile.runtime.scene=scene;
        assert.equal(Files.encodeProject(profile,alternative,options),alternativeText);
        const checked=Files.validateProjectText(alternativeText,profile,options);
        const reopened=new Blockly.Workspace();
        try {
          Blockly.serialization.workspaces.load(checked.project.workspace,reopened);
          Contract.applyFieldBounds(profile,reopened);
          const ast=Compiler.compileWorkspace(reopened);
          assert.deepEqual(ast,alternativeAst);
          const flight=backend(variant);
          await Interpreter.run(ast,flight,{motionBounds:profile.runtime.astBounds});
          assert.deepEqual(flight.pose(),{...expect,airborne:false});
          assert(flight.reads.some(x=>x[0]==='front'&&x[3]===180),
            'variable-free decision must measure front after pivot');
          assert.equal(flight.reads.filter(x=>x[0]==='left').length,0);
          assert.equal(flight.records.filter(x=>x[0]==='land').length,1);
        } finally {reopened.dispose();}
      }
    } finally {alternative.dispose();}
    // This opt-in CI fixture is the SAME bytes for any subsequently flown
    // variant. Never install it into activities/progression/ or show to pupils.
    if(process.env.WEBEEBLOCKS_A5_WBB_OUTPUT){
      const fs=require('node:fs');
      const allowed='ci-artifacts/progression-reactive-L-v2-pupil/generic-witness.wbb';
      if(process.env.WEBEEBLOCKS_A5_WBB_OUTPUT!==allowed)
        throw Error('refuse unexpected pupil-fixture output path');
      const file=path.join(ROOT,allowed);
      fs.mkdirSync(path.dirname(file),{recursive:true});
      fs.writeFileSync(file,text,{encoding:'utf8',flag:'wx'});
      if(fs.readFileSync(file,'utf8')!==text)throw Error('fixture write corruption');
      const rival=path.join(ROOT,'ci-artifacts/progression-reactive-L-v2-pupil/no-memory-witness.wbb');
      fs.writeFileSync(rival,alternativeText,{encoding:'utf8',flag:'wx'});
      if(fs.readFileSync(rival,'utf8')!==alternativeText)throw Error('rival fixture corruption');
    }
    console.log('PASS A5 same Blockly .wbb A/B/C with delayed historical range after 90-degree pivot; two reactive loops, MOCK backend only; sha256='+sha);
    console.log('A5_NO_MEMORY_CHALLENGER_MOCK_PASS front after pivot, zero variables, same A/B/C; sha256='+alternativeSha);
    console.log(JSON.stringify({no_memory_wbb_sha256:alternativeSha,native_flight:'NOT_TESTED'}));
    console.log(JSON.stringify({wbb_sha256:sha,pupil_flight:'NOT_TESTED',
      didactics:'historical value read AFTER changing sensor frame; physical necessity NOT YET TESTED',readings}));
  }finally{source.dispose();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
