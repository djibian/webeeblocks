'use strict';
// Product-profile contract for A6, not a claim of public native admission.
// The hidden contract contains no route answer and cannot become a pupil
// activity just because a private CI pilot can fly the three Webots scenes.
const assert=require('node:assert/strict');
const Activities=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Files=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');

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
