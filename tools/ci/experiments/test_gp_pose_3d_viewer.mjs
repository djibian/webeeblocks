// Reproducible presentation-state regression. No browser, Webots or authority mocks.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';

const html = readFileSync(join(dirname(fileURLToPath(import.meta.url)),
  'gp_pose_3d_viewer.html'), 'utf8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(match, 'inline renderer script exists');

function harness(poseFetch) {
  const constants = { VERTEX_SHADER:1, FRAGMENT_SHADER:2, COMPILE_STATUS:3,
    LINK_STATUS:4, ARRAY_BUFFER:5, STATIC_DRAW:6, TRIANGLES:7, FLOAT:8,
    DEPTH_TEST:9, COLOR_BUFFER_BIT:16, DEPTH_BUFFER_BIT:32 };
  const gl = new Proxy(constants, { get(target, property) {
    return property in target ? target[property] : () => ({});
  } });
  const canvas = {getContext: () => gl, clientWidth: 960,
    clientHeight: 563, width: 960, height: 563};
  const status = {textContent: ''};
  const doc = {getElementById: id => id === 'view' ? canvas : status};
  let poseRequests = 0;
  const fetch = async url => {
    if (url === '/scene') return {ok:true, json:async () => ({
      boxes:[], world_sha256:'fixture'})};
    assert.equal(url, '/pose');
    poseRequests++;
    return poseFetch();
  };
  const globals = {document:doc,window:{},fetch,
    setInterval:()=>{},requestAnimationFrame:()=>{},
    performance:{now:()=>0},devicePixelRatio:1};
  runInNewContext(match[1] + '\\nglobalThis.testHooks={poll,metrics};',
    globals, {timeout:5000});
  return {poll:globals.testHooks.poll, metrics:globals.testHooks.metrics,
    requests:()=>poseRequests};
}
function sample(inc,seq,valid=true) {
  return {incarnation:inc, sequence:seq,valid,time_ms:seq*8,
    position:[0,0,.4],orientation:[1,0,0,0,1,0,0,0,1]};
}
function responses(...poses) {
  const list=poses.slice();
  return harness(async()=>({ok:true,json:async()=>list.shift()}));
}

const a='a'.repeat(32), b='b'.repeat(32);
const same=responses(sample(a,1),sample(a,4));
await same.poll(); await same.poll();
assert.equal(same.metrics.poseSeq,4);
assert.equal(same.metrics.incarnations,0);
assert.equal(same.metrics.dropped,2);

const restarted=responses(sample(a,100),sample(b,1),sample(b,3),sample(b,3));
await restarted.poll(); await restarted.poll();
assert.equal(restarted.metrics.incarnation,b,
  'a new incarnation must supersede even a larger old sequence');
assert.equal(restarted.metrics.poseSeq,1);
assert.equal(restarted.metrics.incarnations,1);
assert.equal(restarted.metrics.dropped,99,
  'count gaps only within one incarnation; 99 missing before first sample');
await restarted.poll(); await restarted.poll();
assert.equal(restarted.metrics.poseSeq,3);
assert.equal(restarted.metrics.received,3);
assert.equal(restarted.metrics.dropped,100);

let release;
const stalled=harness(()=>new Promise(resolve=>{release=resolve;}));
const first=stalled.poll();
await Promise.resolve();
await stalled.poll(); // A slow HTTP request must not cause a second request.
assert.equal(stalled.requests(),1, 'at most one outstanding pose HTTP read');
release({ok:true,json:async()=>sample(a,1)});
await first;
assert.equal(stalled.metrics.poseSeq,1);
assert.equal(stalled.metrics.received,1);
console.log('pass: latest pose, new incarnation, no overlap, drops bounded');
