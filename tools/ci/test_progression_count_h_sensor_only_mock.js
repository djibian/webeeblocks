'use strict';
/* A6 Draft-only synthetic adversarial test of the REAL sensor-only module.
 * Synthetic sensor readings are not a Webots motor flight, not a Blockly
 * .wbb run, not a pupil starter, and never authorize hardware flight.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
const code=fs.readFileSync(path.join(ROOT,
  'plugins/robot_windows/count_h_flight_probe/count_h_sensor_only_probe.js'),'utf8');
assert(code.includes('export async function runSensorOnly(backend,report)'));
const gateX=[-.85,0,.85];
async function trial(run,n,opts={}){
  let x=-1.4,y=0,airborne=false,landed=false,forward=0;
  const actions=[],events=[];
  const backend={
    async setSpeed(v){assert.equal(v,.20);},
    async takeoff(v){assert.equal(v,.40);airborne=true;},
    async move(dir,d){
      assert(airborne&&Number.isFinite(d)&&d>0&&d<=.70);
      if(dir==='forward'){x+=d;forward++;}
      else if(dir==='left')y+=d;
      else if(dir==='right')y-=d;
      else assert.fail('unexpected direction '+dir);
      actions.push(dir);
    },
    async readRange(dir){
      if(dir==='front'){
        if(opts.invalidFront)return NaN;
        if(opts.neverTerminal)return 2;
        return Math.min(2,Math.max(0,1.86-x));
      }
      assert.equal(dir,'up');
      if(opts.invalidUp)return NaN;
      if(opts.alwaysUnder)return .20;
      const under=gateX.slice(0,n).some(g=>Math.abs(x-g)<.105);
      return under?.20:2;
    },
    async land(){
      assert(airborne);
      assert(Math.abs(x-1.48)<=.06,'landing must be physical-pad-bound');
      assert(Math.abs(y-(n===2?.55:n===3?-.55:0))<=.001);
      landed=true;airborne=false;
    }
  };
  let error=null;
  try{await run(backend,async(event,detail)=>events.push({event,detail}));}
  catch(e){error=e;}
  return{error,landed,forward,actions,events};
}
(async()=>{
  /* Import EXACT module bytes from the checkout, not a rewritten algorithm. */
  const {runSensorOnly}=await import('data:text/javascript;base64,'+
    Buffer.from(code,'utf8').toString('base64'));
  for(const n of [1,2,3]){
    const v=await trial(runSensorOnly,n);
    assert.equal(v.error,null,'mock n='+n+' '+v.error);
    assert(v.landed);
    assert(v.forward>=20&&v.forward<=80);
    const count=v.events.filter(e=>e.event==='A6_SENSOR_COUNT');
    assert.equal(count.length,1);
    assert.equal(count[0].detail.count,n);
    assert.equal(count[0].detail.sceneBlind,true);
    assert.equal(v.actions.filter(s=>s==='left').length,n===2?1:0);
    assert.equal(v.actions.filter(s=>s==='right').length,n===3?1:0);
    const last=v.events.at(-1);
    assert.equal(last.event,'A6_TEST_COMPLETE');
    assert.equal(last.detail.pupilWbbUnproven,true);
  }
  for(const item of [
    {n:0,options:{},why:/no bounded scene-blind H count/},
    {n:1,options:{invalidFront:true},why:/native front sensor unavailable/},
    {n:1,options:{invalidUp:true},why:/native upper sensor unavailable/},
    {n:1,options:{alwaysUnder:true},why:/no bounded scene-blind H count/},
    {n:1,options:{neverTerminal:true},why:/no bounded scene-blind H count/},
  ]){
    const v=await trial(runSensorOnly,item.n,item.options);
    assert(v.error&&item.why.test(String(v.error)),
      'test-only variant-blind pilot must refuse: '+JSON.stringify(item));
    assert(!v.landed,'refuted sensor trace landed');
    assert(!v.events.some(e=>e.event==='A6_SENSOR_COUNT'),
      'refuted sensor trace published false sensor success');
  }
  console.log('A6_SENSOR_ONLY_MOCK_ADVERSARIAL_PASS positive=1,2,3 negative=5 webots=NOT_TESTED pupil_wbb=UNPROVEN');
})().catch(error=>{console.error(error);process.exitCode=1;});
