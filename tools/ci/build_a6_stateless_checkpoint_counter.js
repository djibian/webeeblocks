'use strict';
/* PRIVATE A6 REFUTATION CANDIDATE. Never put this Blockly program in the
 * student catalogue, activity instructions or any published .wbb.
 * This proves a *synthetic* checkpoint/branch witness and Save/Open only.
 * Native Webots PID/motor outcomes remain UNPROVEN.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {build}=require('./build_a6_private_blockly_witness');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const ProjectFiles=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
require('../../plugins/robot_windows/blockly_v2/node_modules/blockly/blocks');
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');

const number=value=>({kind:'number',value});
const forward=distance_m=>({kind:'move',direction:'forward',distance_m});
const lateral=(direction,distance_m)=>({kind:'move',direction,distance_m});
const under=()=>({kind:'compare',op:'LT',
  left:{kind:'range',direction:'up',unit:'m'},right:number(.75)});
const decide=(yes,no)=>({kind:'if',condition:under(),then:yes,else:no});

function statelessAst(){
  return {version:1,semantics:'webeeblocks-ast-v1',program:[
    {kind:'takeoff',height_m:.4},{kind:'set_speed',speed_m_s:.2},
    forward(.7),forward(.7),
    // Both moves start from the SAME origin; no world ID, counter, GPS or
    // variant-specific serialization. The branch itself carries the state.
    decide([
      forward(.45),
      // The fixed .40-m leg could stop just before the real x=.85 H3
      // observation, despite the earlier Supervisor probe at exact x=.85.
      // Calibrate from the genuinely sensed final panel (x=1.86, with
      // about 0.03 m front sensor offset), then use the unchanged up ray.
      // This remains a private, bounded no-counter experiment.
      forward({kind:'arithmetic',op:'MINUS',
        left:{kind:'range',direction:'front',unit:'m'},right:number(.98)}),
      decide([forward(.63),lateral('right',.55)],
             [forward(.63),lateral('left',.55)])
    ],[
      forward(.5),forward(.5),forward(.48)
    ]),
    // Real R2025a MOVE acknowledgements tolerate a small final position
    // error. Independent native pad oracle requires true pad containment:
    // use a NEW genuine front reading to close the terminal offset.
    // No variable, world identity or professor solution is exposed.
    {kind:'if',condition:{kind:'compare',op:'GT',
      left:{kind:'range',direction:'front',unit:'m'},right:number(.42)},
      then:[{kind:'move',direction:'forward',distance_m:{
        kind:'arithmetic',op:'MINUS',
        left:{kind:'range',direction:'front',unit:'m'},right:number(.36)}}]},
    {kind:'land'}
  ]};
}

function mockBackend(n,{missingUp=false,alwaysClear=false}={}){
  assert([1,2,3].includes(n));
  const gates=[-.85,0,.85].slice(0,n),moves=[],readings=[];
  const backend={x:-1.4,y:0,z:0,landed:false,
    capabilities:{actions:['takeoff','move','set_speed','land'],
      conditionalLoops:true,rangeDirections:['up','front'],
      moveDirections:['forward','left','right'],verticalDirections:[]},
    async takeoff(height){assert.equal(height,.4);this.z=height;},
    async setSpeed(speed){assert.equal(speed,.2);},
    async move(direction,distance){
      assert(this.z>.2&&Number.isFinite(distance)&&distance>0&&distance<=.7);
      if(direction==='forward')this.x+=distance;
      else if(direction==='left')this.y+=distance;
      else if(direction==='right')this.y-=distance;
      else assert.fail('disallowed simulated move');
      moves.push([direction,distance]);
    },
    async readRange(direction){
      if(direction==='front')return Math.max(.01,Math.min(2.,1.83-this.x));
      assert.equal(direction,'up');
      if(missingUp)return Number.NaN;
      const observed=!alwaysClear&&gates.some(g=>Math.abs(this.x-g)<.025);
      const value=observed?.20:2.0;
      readings.push({x:this.x,value});
      return value;
    },
    async land(){
      assert.equal(this.z,.4);
      this.z=0;this.landed=true;
    }};
  return {backend,moves,readings};
}

async function main(){
  const wanted=statelessAst();
  const witness=build(wanted,[]);
  assert.equal(witness.variableCount,0);
  assert.deepStrictEqual(witness.ast,wanted);
  assert(!/count-h-[123]-v1/.test(witness.text),
    'program may not encode the chosen physical world');
  const profile=Activities.getProfile('progression-count-h-v1');
  assert.equal(profile.starterVisible,false,'A6 must remain hidden');
  const actualWbb=JSON.stringify({
    ...witness.project,
    activity:{id:profile.id,semantics:witness.ast.semantics}
  },null,2)+'\n';
  const options={Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,
    blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Semantic,
    activityContract:Contract};
  const checked=ProjectFiles.validateProjectText(actualWbb,profile,options);
  assert.deepStrictEqual(checked.ast,wanted);
  Contract.preflightAst(profile,wanted);
  const hash=require('node:crypto').createHash('sha256')
    .update(actualWbb).digest('hex');
  for(const n of [1,2,3]){
    const {backend,moves,readings}=mockBackend(n);
    await Interpreter.run(wanted,backend,{maxSteps:20000,
      motionBounds:profile.runtime.astBounds});
    const y=n===1?0:n===2?.55:-.55;
    assert(backend.landed,'did not land');
    assert(Math.abs(backend.x-1.48)<1e-7,'terminal X mismatch');
    assert(Math.abs(backend.y-y)<1e-7,'wrong pad on mock variant '+n);
    assert.equal(readings.length,n===1?1:2);
    assert.deepStrictEqual(readings.map(x=>Number(x.x.toFixed(2))),
      n===1?[0]:[0,.85]);
    assert(moves.every(x=>x[1]<=.7));
  }
  for(const n of [2,3]){
    const {backend}=mockBackend(n,{alwaysClear:true});
    await Interpreter.run(wanted,backend,{maxSteps:20000,
      motionBounds:profile.runtime.astBounds});
    assert(backend.landed);
    assert.equal(backend.y,0,
      'negative synthetic ray should misclassify, not prove native equivalence');
  }
  const {backend:bad}=mockBackend(2,{missingUp:true});
  await assert.rejects(
    Interpreter.run(wanted,bad,{maxSteps:20000,
      motionBounds:profile.runtime.astBounds}),
    /sensor|finite|NaN|range|invalid|non-finite/i);
  assert.equal(bad.landed,false,'no native completion on invalid sensor');
  if(process.argv[3]) {
    // Same AST, separately serialized for the *private* Robot Window;
    // this is NOT an A6 pupil profile, starter or released asset.
    const privateWbb=witness.text;
    assert.equal(JSON.parse(privateWbb).activity.id,witness.profile.id);
    assert.notEqual(witness.profile.id,profile.id);
    assert.equal(witness.variableCount,0);
    assert(!/count-h-[123]-v1/.test(privateWbb));
    const privateDest=path.resolve(process.argv[3]);
    if(privateDest===path.resolve(process.argv[2]||"."))throw Error("private and student-profile outputs must differ");
    fs.mkdirSync(path.dirname(privateDest),{recursive:true});
    fs.writeFileSync(privateDest,privateWbb,{flag:'wx',encoding:'utf8'});
    assert.equal(fs.readFileSync(privateDest,'utf8'),privateWbb);
    console.log('A6_STATELESS_PRIVATE_CI_WBB_VALID variables=0 '+
      'profile=private-only same_ast=true native_B=UNPROVEN');
  }
  if(process.argv[2]){
    const dest=path.resolve(process.argv[2]);
    fs.mkdirSync(path.dirname(dest),{recursive:true});
    fs.writeFileSync(dest,actualWbb,{flag:'wx',encoding:'utf8'});
    assert.equal(fs.readFileSync(dest,'utf8'),actualWbb);
  }
  console.log('A6_STATELESS_CHECKPOINT_BLOCKLY_MOCK_PASS '+
    'variants=1,2,3 variables=0 observations=1,2,2 '+
    'same_wbb_sha256='+hash+' terminal_front_correction=bounded '+
    'real_webots_motor=UNPROVEN school_pass=UNPROVEN');
}
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1;});
module.exports={statelessAst};
