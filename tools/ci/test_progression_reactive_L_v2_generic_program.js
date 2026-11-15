'use strict';
/* TEST-ONLY A5 v2 whole-algorithm witness, never an activity starter.
 * A real Blockly 13 .wbb, unchanged A/B/C, exercises bounded re-observation
 * and a first state variable. This fixture uses MOCK ranges/dynamics only.
 * It DOES NOT establish a successful Webots or pupil flight.
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
function build(){
  const w=new Blockly.Workspace();
  const state=w.getVariableMap().createVariable('observation mémorisée','','a5-v2-memory');
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
  const store=block('variables_set');store.getField('VAR').setValue(state.getId());
  put(store,'VALUE',range('left'));
  const choose=block('controls_if');choose.loadExtraState({elseIfCount:1,hasElse:true});
  put(choose,'IF0',cmp('LT',get(),num(.6)));
  const a=[turn('right'),move(.78)];link(...a);
  choose.getInput('DO0').connection.connect(a[0].previousConnection);
  put(choose,'IF1',cmp('GT',get(),num(1.6)));
  const b=[turn('left'),move(1.42)];link(...b);
  choose.getInput('DO1').connection.connect(b[0].previousConnection);
  const c=[turn('left'),move(1.25),turn('right'),move(.60)];link(...c);
  choose.getInput('ELSE').connection.connect(c[0].previousConnection);
  const land=block('webeeblocks_v2_land');
  link(takeoff,speed,first,left,second,store,choose,land);
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
      if(direction==='front'){
        if(heading===0)return round(.98-x);
        if(heading===90&&x>=.7)return round(1.21-y);
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
    assert.equal(ast.program.length,8);
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
        assert.equal(b.records.filter(x=>x[0]==='land').length,1);
        readings.push({variant,left:{A:.28,B:1.78,C:1.44}[variant],
          steps:b.reads.length,final:b.pose()});
      }finally{reopened.dispose();}
    }
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
    }
    console.log('PASS A5 real Blockly .wbb serialisation, two reactive while loops, one stored range, common AST across A/B/C, MOCK backend only; sha256='+sha);
    console.log(JSON.stringify({wbb_sha256:sha,pupil_flight:'NOT_TESTED',
      didactics:'functional loop/state syntax, not proof they are necessary',readings}));
  }finally{source.dispose();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
