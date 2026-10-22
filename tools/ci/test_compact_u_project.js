'use strict';
const assert=require('assert'),fs=require('fs');
const Demo=require('../blockly/compact_u_demo');
const Blockly=require('../../plugins/robot_windows/blockly_v2/node_modules/blockly');
const S=require('../../plugins/robot_windows/blockly/webeeblocks/semantic_ast');
const C=require('../../plugins/robot_windows/blockly/webeeblocks/activity_contract');
const P=require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const O=require('../../plugins/robot_windows/blockly/webeeblocks/execution_observer');
const I=require('../../plugins/robot_windows/blockly/webeeblocks/interpreter');
const A=require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles=require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const r=Demo.build(),reopened=new Blockly.Workspace();
const options={Blockly,profiles:Profiles,activitiesDocument:r.document,blockCatalog:A.BLOCK_CATALOG,semanticAst:S,activityContract:C};
const loaded=P.validateProjectText(fs.readFileSync('tools/blockly/compact_u_demo.wbb','utf8'),r.profile,options);
assert.deepStrictEqual(loaded.ast,r.ast);
Blockly.serialization.workspaces.load(loaded.project.workspace,reopened);
assert.deepStrictEqual(S.compileWorkspace(reopened),r.ast);
C.preflightWorkspace(r.profile,reopened);C.preflightAst(r.profile,r.ast);
assert.deepStrictEqual(r.metrics,{blocks:63,variables:2,procedures:0,statementNesting:3});
// Every condition, action and increment must retain a real block identity,
// including statements inside UNTIL -> guarded_move -> on_sensor.
const map=O.buildSourceMap(reopened);
function walk(nodes,prefix=['program']){nodes.forEach((q,i)=>{
 const path=prefix.concat(i);assert(map[path.join('/')],path.join('/'));
 if(q.kind==='set_variable'&&q.value.kind==='arithmetic'){for(const suffix of ['value','value/left','value/right'])assert(map[path.join('/')+'/'+suffix],suffix);}
 for(const key of ['body','on_sensor','then','else'])if(q[key])walk(q[key],path.concat(key));
});}walk(r.ast.program);
const budget=I.validateExecutionBudget(r.ast,20000);
const forbidden=['seed','gateCount','configuration','score','elapsed_time'];
for(const key of forbidden)assert(!JSON.stringify(r.ast).includes('"'+key+'"'));
assert.strictEqual(r.ast.program.filter(q=>q.kind==='repeat').length,1);
assert.strictEqual(r.ast.program.find(q=>q.kind==='repeat').count,3);
console.log('PASS compact U: real 63-block .wbb round-trip, two used variables, UNTIL/guarded source IDs, profile and conservative budget='+budget+'; no native success claim');
r.workspace.dispose();reopened.dispose();
