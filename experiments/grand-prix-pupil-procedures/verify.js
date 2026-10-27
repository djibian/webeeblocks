#!/usr/bin/env node
'use strict';
// Independent structural equality first; optional real Blockly/AST/preflight
// validation on the repository's pinned Blockly installation.
const fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const dir=__dirname;
const source=JSON.parse(fs.readFileSync(path.join(dir,'source-655.wbb'),'utf8'));
const pupil=JSON.parse(fs.readFileSync(path.join(dir,'Grand-Prix-procedures-sans-murs.wbb'),'utf8'));
function traverse(project){
  const roots=project.workspace.blocks.blocks,ids=new Set(),variables=new Set(),counts={blocks:0,calls:0};
  function visit(b){
    for(;b;b=b.next?.block){
      assert(b.id&&typeof b.type==='string'&&!ids.has(b.id),'invalid or duplicate Blockly block');
      ids.add(b.id);counts.blocks++;
      if(b.fields?.VAR?.id)variables.add(b.fields.VAR.id);
      if(b.type==='procedures_callnoreturn')counts.calls++;
      for(const v of Object.values(b.inputs||{}))if(v.block||v.shadow)visit(v.block||v.shadow);
    }
  }
  roots.forEach(visit);
  return {...counts,roots:roots.length,variables:project.workspace.variables.length,usedVariables:variables.size};
}
function expanded(first,defs){
  const result=[];
  for(let b=first;b;b=b.next?.block){
    if(b.type==='procedures_callnoreturn'){
      assert(defs[b.extraState?.name],'procedure must be defined');
      result.push(...expanded(defs[b.extraState.name].inputs.STACK.block,defs));
    }else{
      const x={type:b.type};
      if(b.fields)x.fields=b.fields;
      if(b.extraState)x.extraState=b.extraState;
      if(b.inputs){x.inputs={};for(const [key,val] of Object.entries(b.inputs))x.inputs[key]=expanded(val.block||val.shadow,defs);}
      result.push(x);
    }
  }
  return result;
}
const defs=Object.fromEntries(pupil.workspace.blocks.blocks.slice(1).map(x=>[x.fields.NAME,x]));
assert.deepStrictEqual(Object.keys(defs).sort(),['explorer un côté','initialiser la mémoire','observer et décider'].sort());
assert.deepStrictEqual(expanded(source.workspace.blocks.blocks[0],{}),expanded(pupil.workspace.blocks.blocks[0],defs));
const a=traverse(source),b=traverse(pupil);
assert.deepStrictEqual(a,{blocks:389,calls:0,roots:1,variables:12,usedVariables:11});
assert.deepStrictEqual(b,{blocks:395,calls:3,roots:4,variables:11,usedVariables:11});
console.log('PASS static source 389 -> structured 395; expanded Blockly tree exactly equal; main chain 15 -> 5');
if(process.argv.includes('--structural-only'))process.exit(0);
const ROOT=path.resolve(dir,'../..');
const Blockly=require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly'));
require(path.join(ROOT,'plugins/robot_windows/blockly_v2/node_modules/blockly/blocks'));
global.Blockly=Blockly;
require(path.join(ROOT,'plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js'));
const Semantic=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/semantic_ast'));
Semantic.installConditionalLoopBounds(Blockly);delete global.Blockly;
const Contract=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_contract'));
const Activities=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activities'));
const Profiles=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/activity_profiles'));
const ProjectFiles=require(path.join(ROOT,'plugins/robot_windows/blockly/webeeblocks/project_files'));
const vm=require('node:vm');
const context={Blockly,WebeeBlocksActivities:Activities,WebeeBlocksActivityProfiles:Profiles,
  WebeeBlocksRuntimeOutcome:{classify:()=>({})},WebeeBlocksWwiBackend:function(){}};
context.window=context;
vm.runInNewContext(fs.readFileSync(path.join(ROOT,'plugins/robot_windows/grand_prix_u/setup.js'),'utf8'),context);
const profile=Profiles.resolveById(Activities.DOCUMENT,'progression-grand-prix-u-v1',Activities.BLOCK_CATALOG);
function compile(project){
 const w=new Blockly.Workspace();
 try{
  Blockly.serialization.workspaces.load(project.workspace,w);
  Contract.preflightWorkspace(profile,w);
  const ast=Semantic.compileWorkspace(w);
  Contract.preflightAst(profile,ast);
  const test=ProjectFiles.validateProjectText(JSON.stringify(project),profile,{Blockly,profiles:Profiles,
   activitiesDocument:Activities.DOCUMENT,blockCatalog:Activities.BLOCK_CATALOG,
   semanticAst:Semantic,activityContract:Contract});
  assert.deepStrictEqual(test.ast,ast);
  const reopened=new Blockly.Workspace();
  try{Blockly.serialization.workspaces.load(project.workspace,reopened);assert.deepStrictEqual(Semantic.compileWorkspace(reopened),ast);}
  finally{reopened.dispose();}
  return ast;
 }finally{w.dispose();}
}
const astSource=compile(source),astPupil=compile(pupil);
function normalize(items){
  return items.flatMap(s=>{
    if(s.kind==='call')return normalize(s.body);
    const t={...s};
    for(const key of ['body','then','else'])if(Array.isArray(t[key]))t[key]=normalize(t[key]);
    return [t];
  });
}
assert.strictEqual(astSource.version,astPupil.version);
assert.strictEqual(astSource.semantics,astPupil.semantics);
assert.deepStrictEqual(normalize(astSource.program),normalize(astPupil.program));
console.log('PASS true Blockly load/save, .wbb validation, exact Grand Prix preflight, compiled AST equal after call expansion');
