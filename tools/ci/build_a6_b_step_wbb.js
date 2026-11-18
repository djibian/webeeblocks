'use strict';
// A6 B: PRIVATE, never a learner starter. Build one real Blockly-13 project
// for 8-cm or 4-cm spatial sampling with the EXACT same counting algorithm.
// The deterministic point-ray mock is a falsifier, NOT Webots evidence.
const assert=require('assert');
const fs=require('fs');
const path=require('path');
const Base=require('./build_a6_private_blockly_witness.js');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Semantic=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const ProjectFiles=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');

const GATES={
  matched:{1:[.36],2:[-.85,.36],3:[-.85,-.31,.36]},
  sampling:{1:[.48],2:[-.80,.48],3:[-.80,-.16,.48]}
};
function candidate(stepCm) {
  if(stepCm!==4&&stepCm!==8)throw Error('invalid private step; only 4 or 8 cm');
  const ast=Base.expectedAst();
  const loops=ast.program.filter(s=>s.kind==='while');
  assert.equal(loops.length,1);
  const forward=loops[0].body.filter(s=>s.kind==='move'&&s.direction==='forward');
  assert.equal(forward.length,1);
  assert.equal(forward[0].distance_m,.08);
  forward[0].distance_m=stepCm/100;
  // No change to the compiler, state machine, speed, budget, allowed blocks,
  // flight profile, target pads, or native C behavioral/origin checks.
  const witness=Base.build(ast,['count','under']);
  assert.equal(witness.variableCount,2);
  const real=Activities.getProfile('progression-count-h-v1');
  assert.equal(real.starterVisible,false);
  const product=JSON.stringify({
    ...witness.project,
    activity:{id:real.id,semantics:ast.semantics}
  },null,2)+'\n';
  const options={Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,
    blockCatalog:Activities.BLOCK_CATALOG,semanticAst:Semantic,activityContract:Contract};
  const validated=ProjectFiles.validateProjectText(product,real,options);
  assert.deepStrictEqual(validated.ast,ast);
  Contract.preflightAst(real,ast);
  assert(!['count-h-1-v1','count-h-2-v1','count-h-3-v1']
    .some(id=>product.includes(id)),'private WBB must not encode a session scene');
  return {ast,product,witness};
}
function idealBackend(gates) {
  return {
    x:-1.4,y:0,z:0,landed:false,readings:[],
    capabilities:{actions:['takeoff','set_speed','move','land'],
      conditionalLoops:true,rangeDirections:['up','front'],
      moveDirections:['forward','left','right'],verticalDirections:[]},
    async takeoff(height){this.z=height;},
    async setSpeed(speed){assert.equal(speed,.2);},
    async move(dir,d){
      assert(Number.isFinite(d)&&d>0&&d<=.70);
      if(dir==='forward')this.x+=d;
      else if(dir==='left')this.y+=d;
      else if(dir==='right')this.y-=d;
      else throw Error('out-of-scope movement');
    },
    async readRange(dir){
      if(dir==='front')return Math.max(.01,Math.min(2.,1.84-this.x));
      if(dir!=='up')throw Error('unexpected sensor');
      const blocked=gates.some(x=>Math.abs(this.x-x)<=.035);
      this.readings.push({x:this.x,up:blocked?.20:2.});
      return blocked?.20:2.;
    },
    async land(){this.z=0;this.landed=true;}
  };
}
async function checkMock(ast,profile,stepCm) {
  for(const [family,variants] of Object.entries(GATES)) {
    for(let n=1;n<=3;n++) {
      const sim=idealBackend(variants[n]);
      const outcome=await Interpreter.run(ast,sim,{
        maxSteps:20000,motionBounds:profile.runtime.astBounds});
      assert(sim.landed,'ideal source-only sensor mock did not terminate');
      assert(Math.abs(sim.x-1.48)<.06,'ideal terminal approach incorrect');
      // In ideal punctual optics, 4 cm sees all six; 8 cm misses every
      // second-family H, even when the same PRIVATE algorithm is otherwise valid.
      if(stepCm===4) {
        assert.equal(outcome.variables.count,n,'4-cm ideal count mismatch');
        assert.equal(outcome.variables.under,0,'last H not exited');
        assert(Math.abs(sim.y-({1:0,2:.55,3:-.55}[n]))<.06);
      }else if(family==='sampling') {
        assert.equal(outcome.variables.count,0,'8-cm ideal alias falsifier disappeared');
      }
      console.log('A6_B_IDEAL_PUNCTUAL_MOCK family='+family+
        ' n='+n+' step_cm='+stepCm+' count='+outcome.variables.count+
        ' native_webots=UNPROVEN');
    }
  }
}
async function main(){
  const stepCm=Number(process.argv[2]),destination=process.argv[3];
  if(!destination||![4,8].includes(stepCm))throw Error('Usage: node build_a6_b_step_wbb.js 4|8 OUTPUT');
  const built=candidate(stepCm);
  await checkMock(built.ast,built.witness.profile,stepCm);
  const out=path.resolve(destination);
  fs.mkdirSync(path.dirname(out),{recursive:true});
  fs.writeFileSync(out,built.product,{flag:'wx',encoding:'utf8'});
  assert.equal(fs.readFileSync(out,'utf8'),built.product);
  console.log('A6_B_PRIVATE_STEP_WBB_VALID step_cm='+stepCm+
    ' blocks='+built.witness.blockCount+' variables=2 same_program_across_worlds=true'+
    ' native_webots=UNPROVEN');
}
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1;});
module.exports={candidate,idealBackend,checkMock};
