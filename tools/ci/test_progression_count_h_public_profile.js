'use strict';
// Product-profile contract for A6, not a claim of public native admission.
// The hidden contract contains no route answer and cannot become a pupil
// activity just because a private CI pilot can fly the three Webots scenes.
const assert=require('node:assert/strict');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Files=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const Contract=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const Interpreter=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const fs=require('node:fs'),path=require('node:path');

const id='progression-count-h-v1';
const occurrences=Activities.DOCUMENT.activities.filter(p=>p.id===id);
assert.equal(occurrences.length,1,'A6 pupil profile must have exactly one identity');
const profile=Activities.getProfile(id);
Profiles.validateProfile(profile,Activities.BLOCK_CATALOG);
for (const scene of ['count-h-1-v1','count-h-2-v1','count-h-3-v1']) {
  const candidate=JSON.parse(JSON.stringify(profile));
  candidate.runtime.scene=scene;
  Profiles.validateProfile(candidate,Activities.BLOCK_CATALOG);
}
for (const bad of ['count-h-0-v1','count-h-4-v1','count-h-1-v1-extra','a8-route']) {
  const rejected=JSON.parse(JSON.stringify(profile));
  rejected.runtime.scene=bad;
  assert.throws(()=>Profiles.validateProfile(rejected,Activities.BLOCK_CATALOG),
    /runtime.scene/,'untrusted native scene ID must be rejected: '+bad);
}
assert.equal(profile.starterVisible,false,'A6 must remain hidden pending native product admission');
assert.equal(profile.runtime.scene,'count-h-1-v1');
assert.equal(profile.world,'worlds/crazyflie_classroom_count_h_start.wbt',
  'A6 must start at the real school native -1.40m blue origin, not Grand Prix');
const schoolStart=fs.readFileSync(path.resolve(__dirname,'../../',profile.world),'utf8');
for(const marker of ['basicTimeStep 32','controller "crazyflie_classroom_v2"',
                     'translation -1.40 0 0.055'])
  assert(schoolStart.includes(marker),'A6 school world missing '+marker);
assert(!schoolStart.includes('controller "crazyflie_runtime_v2"'),
  'A6 must not launch the shared real-flight runtime');

assert.equal(profile.evaluation.type,'mission-state-v1');
assert.equal(profile.evaluation.oracle,id);
assert.equal(profile.brief.visible,true);
assert.match(profile.brief.mission,/trois parcours/);
assert(!/compte\s*=|variable\s*=|0\.82|0\.75|0\.36/.test(profile.brief.mission),
  'learner brief must never reveal the private reference algorithm');
for(const type of ['controls_whileUntil','variables_set','variables_get',
                   'webeeblocks_v2_range','controls_if'])
  assert(profile.toolbox.includes(type),'A6 missing pupil concept '+type);
assert(profile.runtime.allowedStatementKinds.includes('while'));
assert(profile.runtime.allowedStatementKinds.includes('set_variable'));
assert.deepEqual(profile.runtime.rangeDirections,['front','up']);
assert.deepEqual(profile.runtime.moveDirections,['forward','left','right']);
assert.deepEqual(profile.fieldOptions.webeeblocks_v2_range.DIRECTION,['front','up']);
assert.deepEqual(profile.runtime.astBounds['while.max_iterations'],{min:1,max:80});
assert.deepEqual(profile.parameterBounds.controls_whileUntil.MAX_ITERATIONS,
  {min:1,max:80,step:1},'A6 editable while bound must agree with preflight');
const pupilWhile={version:1,semantics:'webeeblocks-ast-v1',program:[
  {kind:'takeoff',height_m:0.40},
  {kind:'while',mode:'WHILE',max_iterations:80,
    condition:{kind:'compare',op:'GT',
      left:{kind:'range',direction:'front',unit:'m'},
      right:{kind:'number',value:0.82}},
    body:[{kind:'move',direction:'forward',distance_m:0.08}]},
  {kind:'land'}
]};
assert(Contract.preflightAst(profile,pupilWhile));
assert(Interpreter.validateExecutionBudget(pupilWhile,profile.runtime.maxSteps)>0);
const excessive=JSON.parse(JSON.stringify(pupilWhile));
excessive.program[1].max_iterations=81;
assert.throws(()=>Contract.preflightAst(profile,excessive),
  /while.max_iterations outside profile bounds/,
  'A6 imported or edited while(81) must fail before flight');

assert.equal(profile.runtime.maxSteps,20000);
assert.equal(profile.runtime.astBounds['set_speed.speed_m_s'].max,0.20);
assert.equal(profile.runtime.astBounds['takeoff.height_m'].max,0.40);
assert.equal(profile.runtime.astBounds['move.lateral.distance_m'].max,0.60);
assert(!profile.toolbox.includes('webeeblocks_v2_light'),'unavailable LED deck must stay absent');
assert(!profile.toolbox.includes('webeeblocks_v2_vertical'),'A6 must not add an altitude concept');
const starter=Files.parseProject(Files.createStarterText(id));
assert.equal(starter.activity.id,id);
assert.deepEqual(starter.workspace.blocks.blocks,[],'pupil starter must have no hidden solution');
assert.equal(Activities.DOCUMENT.activities.filter(x=>x.id.startsWith('progression-')&&x.starterVisible!==false).length,8,
  'an unqualified A6 profile must not appear in the pupil Start catalogue');
console.log('PASS A6 hidden pupil profile: limited concepts, three-world contract, blank starter, not yet public');
