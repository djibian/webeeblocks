'use strict';
// One serialized .wbb must not contain a scene variant. Real pupil flight,
// classroom OPEN/SAVE UI and teacher variant selection remain UNTESTED.
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
const Blockly=require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly'));
require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
const Activities=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const Profiles=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Contract=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const Semantic=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));
const Projects=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/project_files.js'));
global.Blockly=Blockly;
require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js'));
delete global.Blockly;
const opts={Blockly,profiles:Profiles,activitiesDocument:Activities.DOCUMENT,
  blockCatalog:Activities.BLOCK_CATALOG,activityContract:Contract,semanticAst:Semantic};
const profile=Profiles.resolveById(
  Activities.DOCUMENT,'progression-reactive-L-v2',Activities.BLOCK_CATALOG);
assert.equal(profile.starterVisible,false,'unqualified A5 became visible');
assert.equal(profile.evaluation.oracle,'progression-reactive-L-v2');
const w=new Blockly.Workspace();
function attach(block,name,num){
  let n=block.getInputTargetBlock(name);
  if(!n){
    n=w.newBlock('math_number');
    block.getInput(name).connection.connect(n.outputConnection);
  }
  n.setFieldValue(String(num),'NUM');
}
try{
  const takeoff=w.newBlock('webeeblocks_v2_takeoff');
  const move=w.newBlock('webeeblocks_v2_move');
  const land=w.newBlock('webeeblocks_v2_land');
  attach(takeoff,'HEIGHT',.5);
  move.setFieldValue('forward','DIRECTION');
  attach(move,'DISTANCE',.2);
  takeoff.nextConnection.connect(move.previousConnection);
  move.nextConnection.connect(land.previousConnection);
  const texts=[];
  for(const scene of ['reactive-L-a-v2','reactive-L-b-v2','reactive-L-c-v2']){
    const testProfile=JSON.parse(JSON.stringify(profile));
    testProfile.runtime.scene=scene;
    assert.equal(Profiles.validateProfile(testProfile,Activities.BLOCK_CATALOG),true);
    const text=Projects.encodeProject(testProfile,w,opts);
    const project=Projects.parseProject(text);
    assert.equal(project.activity.id,profile.id);
    assert.equal(Object.hasOwn(project.activity,'scene'),false);
    assert.equal(JSON.stringify(project).includes('reactive-L-'),false);
    const verified=Projects.validateProjectText(text,testProfile,opts);
    assert.equal(verified.project.activity.id,profile.id);
    assert.equal(verified.profile.world,profile.world);
    texts.push(text);
  }
  assert.equal(texts[0],texts[1]);
  assert.equal(texts[1],texts[2]);
  const sha=crypto.createHash('sha256').update(texts[0]).digest('hex');
  assert.equal(sha.length,64);
  console.log('PASS A5 V2 same real serialized .wbb across A/B/C: sha256='+sha+
    ' flight=NOT_TESTED browser_save_open=NOT_TESTED');
}finally{w.dispose();}
