'use strict';
const assert=require('node:assert/strict');
const {build,guardedBuild}=require('./build');
const o=guardedBuild(),n=build(),orig=o.workspace.blocks.blocks,now=n.workspace.blocks.blocks;
assert.equal(orig.length,4);assert.equal(now.length,5);
for(let i=1;i<4;i++)assert.deepStrictEqual(now[i].inputs,orig[i].inputs);
function repeat(root){let p=root;while(p&&p.type!=='controls_repeat_ext')p=p.next?.block;assert(p);return p}
assert.deepStrictEqual(now[4].inputs.STACK.block,repeat(orig[0]).inputs.DO.block);
assert.equal(now[4].fields.NAME,'parcourir un côté');
assert.equal(repeat(now[0]).inputs.DO.block.type,'procedures_callnoreturn');
assert.equal(repeat(now[0]).inputs.DO.block.extraState.name,'parcourir un côté');
const a=JSON.parse(JSON.stringify(orig[0]));
repeat(a).inputs.DO.block=JSON.parse(JSON.stringify(repeat(now[0]).inputs.DO.block));
a.x=now[0].x;a.y=now[0].y;
assert.deepStrictEqual(a,now[0]);
console.log('PASS four ordinary editable procedures, entire side algorithm unchanged');
console.log('PASS full ambiguity, per-side memory, rear confirmation and pose decisions preserved');
