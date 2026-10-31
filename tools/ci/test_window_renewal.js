'use strict';
const assert = require('assert');
const make = require('../../plugins/robot_windows/blockly_v2/window_renewal.js');
const token = 'a'.repeat(64);

function environment(options = {}) {
  let data = JSON.stringify({version:2,token,profileId:'reactive-obstacle-v2',workspace:'{}'});
  let reloads = 0, fetched = 0, clocks = 0, ms = 0;
  const location = {
    protocol:'http:', hostname:'localhost',
    pathname:'/robot_windows/blockly_v2/blockly_v2.html',
    href:'http://localhost:1234/robot_windows/blockly_v2/blockly_v2.html?name=Crazyflie',
    reload() { ++reloads; }
  };
  if (options.path) location.pathname = options.path;
  if (options.hostname) location.hostname = options.hostname;
  if (options.href) location.href = options.href;
  const timers = new Map();
  const env = {
    location, performance:{now:()=>ms}, localStorage:{getItem(key) {
      assert.strictEqual(key,'webeeblocks-world-recovery-v1'); return data;
    }},
    AbortController, fetch: async (url, init) => {
      ++fetched;
      assert.strictEqual(url, location.href, 'no arbitrary navigation target');
      assert.strictEqual(init.credentials,'same-origin');
      assert.strictEqual(init.redirect,'error', 'HTTP redirection must stay forbidden');
      assert.strictEqual(init.cache,'no-store', 'HTTP revalidation must bypass the cache');
      if(options.httpUnavailable) throw Error('HTTP unavailable');
      return {ok:true,headers:{get:()=>options.mime||'text/html; charset=utf-8'}};
    },
    setTimeout: (fn,delay)=>{ const id=++clocks;timers.set(id,{fn,delay});return id; },
    clearTimeout:id=>timers.delete(id),
    document:{getElementById:()=>({textContent:''})}
  };
  return {env, control:make(env), get reloads(){return reloads;},
    get fetched(){return fetched;}, set checkpoint(value){data=value;},
    nextTimer(){const x=timers.entries().next().value;if(x){timers.delete(x[0]);ms+=x[1].delay;x[1].fn();}},
    timers
  };
}
async function flush(){await new Promise(r=>setImmediate(r));}
async function testWindowRenewal() {
  let e=environment();
  assert.strictEqual(e.control.arm('b'.repeat(64)),false,'invalid token');
  assert.strictEqual(e.control.onTransportClose(),false,'unarmed close must not renew');
  assert.strictEqual(e.control.arm(token),true);
  assert.strictEqual(e.control.arm(token),false,'no repeated arm/replay');
  assert.strictEqual(e.control.begin(),true);
  assert.strictEqual(e.control.onTransportClose(),true);
  await flush();
  assert.strictEqual(e.reloads,1,'same existing tab must renew exactly once');
  assert.strictEqual(e.fetched,1);
  assert.strictEqual(e.control.onTransportClose(),true);
  await flush();
  assert.strictEqual(e.reloads,1,'duplicate WWI close cannot relaunch');
  assert.strictEqual(e.control.arm(token),false,'navigation is one-shot');

  // The exact URL observed by the Windows 11/Chrome human test (#768).
  const sessionName = 'blockly_v2_3bd18613c66933c7_session_284_604b5ee93d99';
  const winPath = '/robot_windows/' + sessionName + '/' + sessionName + '.html';
  const windowsUrl = 'http://127.0.0.1:50301' + winPath + '?name=Crazyflie%20WebeeBlocks';
  e=environment({hostname:'127.0.0.1',path:winPath,href:windowsUrl});
  assert.strictEqual(e.control.arm(token),true,'observed Windows session URL must be admitted');
  assert.strictEqual(e.control.onTransportClose(),true);
  await flush();
  assert.strictEqual(e.reloads,1,'observed Windows URL must renew the existing tab once');
  assert.strictEqual(e.fetched,1,'observed Windows URL must only probe its own document');

  // Preserve old localhost, content-addressed and loopback forms.
  e=environment({hostname:'127.0.0.1'});
  assert.strictEqual(e.control.arm(token),true,'non-session loopback URL must stay valid');
  e=environment({hostname:'localhost',path:winPath});
  assert.strictEqual(e.control.arm(token),true,'local legacy host can serve session identity');

  // All name/path/authority variants are negative assertions, not allowlists.
  const invalid = [
    {hostname:'evil.example',path:winPath},
    {hostname:'localhost.evil.example',path:winPath},
    {hostname:'127.0.0.2',path:winPath},
    {hostname:'[::1]',path:winPath}, // Not observed / not admitted implicitly.
    {hostname:'0.0.0.0',path:winPath},
    {hostname:'127.0.0.1',path:winPath.slice(0, -5) + '_other.html'},
    {hostname:'127.0.0.1',path:winPath.replace('session_284_', 'session_284_ffff')},
    {hostname:'127.0.0.1',path:winPath.replace('session_284_', 'session_foo_')},
    {hostname:'127.0.0.1',path:winPath.replace('session_284_', 'session_12345678901_')},
    {hostname:'127.0.0.1',path:winPath.replace('604b5ee93d99','604b5ee93d9g')},
    {hostname:'127.0.0.1',path:winPath.replace('session_284_', 'session_284__')},
    {hostname:'127.0.0.1',path:winPath.replace('3bd18613c66933c7_', 'deadbeefdeadbeef_')},
    {hostname:'127.0.0.1',path:'/robot_windows/../../robot_windows/'+sessionName+'/'+sessionName+'.html'},
    {hostname:'127.0.0.1',path:'/robot_windows/%2e%2e/'+sessionName+'/'+sessionName+'.html'},
    {hostname:'127.0.0.1',path:'/robot_windows/evil/evil.html'}
  ];
  for (const variant of invalid) {
    e=environment(variant);
    assert.strictEqual(e.control.arm(token),false,'invalid Robot Window URL admitted '+JSON.stringify(variant));
    assert.strictEqual(e.reloads,0,'invalid URL navigated');
  }
  e=environment({hostname:'evil.example'});
  assert.strictEqual(e.control.arm(token),false,'cross-origin navigation refused');
  // Windows classroom release uses content-addressed directory+HTML names;
  // a mismatched digest is NOT an allowed Webots Robot Window identity.
  e=environment({path:'/robot_windows/blockly_v2_0123456789abcdef/blockly_v2_0123456789abcdef.html'});
  assert.strictEqual(e.control.arm(token),true,'fingerprinted Windows Blockly page admitted');
  e.control.disarm();
  e=environment({path:'/robot_windows/blockly_v2_0123456789abcdef/blockly_v2_deadbeef01234567.html'});
  assert.strictEqual(e.control.arm(token),false,'mismatched Windows release identity denied');
  e=environment({path:'/robot_windows/other_robot/other_robot.html'});
  assert.strictEqual(e.control.arm(token),false,'non Blockly Robot Window denied');
  e=environment({path:'/evil/origin/forged.html'});
  assert.strictEqual(e.control.arm(token),false,'unapproved HTML path refused');
  e=environment();
  e.checkpoint=JSON.stringify({version:2,token:'b'.repeat(64)});
  assert.strictEqual(e.control.arm(token),false,'stale or other-session token denied');
  e=environment();
  assert.strictEqual(e.control.arm(token),true);
  e.checkpoint=null;
  assert.strictEqual(e.control.onTransportClose(),false,'checkpoint loss fails closed');
  assert.strictEqual(e.reloads,0);
  // Session URL unavailable after a world reload must fail closed as before.
  e=environment({hostname:'127.0.0.1',path:winPath,href:windowsUrl,httpUnavailable:true});
  assert.strictEqual(e.control.arm(token),true);
  assert.strictEqual(e.control.onTransportClose(),true);
  for (let n=0;n<70;n++) { await flush(); e.nextTimer(); }
  await flush();
  assert.strictEqual(e.reloads,0,'vanished Windows session URL cannot authorize navigation');
  assert(e.fetched >= 40 && e.fetched <= 61,'same absolute HTTP deadline retained');
  e=environment({mime:'text/plain'});
  assert.strictEqual(e.control.arm(token),true);
  e.control.onTransportClose();
  await flush();
  assert.strictEqual(e.reloads,0,'non HTML response cannot authorize renewal');
  e.control.disarm();
  assert.strictEqual(e.control.onTransportClose(),false,'disarmed stale close denied');
  // Transport never recovers: one bounded series and NO further attempt on
  // repeated close/replay, no navigation and no forgotten pupil data.
  e=environment({httpUnavailable:true});
  assert.strictEqual(e.control.arm(token),true);
  assert.strictEqual(e.control.onTransportClose(),true);
  for (let n=0;n<70;n++) { await flush(); e.nextTimer(); }
  await flush();
  assert.strictEqual(e.reloads,0,'HTTP outage may not be interpreted as success');
  const attempts=e.fetched;
  assert(attempts >= 40 && attempts <= 61,'HTTP attempts must fit the absolute 30s deadline');
  assert.strictEqual(e.control.onTransportClose(),true,'old tab stays safely gated');
  await flush();
  assert.strictEqual(e.fetched,attempts,'duplicate close must not retry indefinitely');
  assert.strictEqual(e.control.arm(token),false,'failed generation is single use');
  e=environment();
  assert.strictEqual(e.control.arm(token),true);
  assert.strictEqual(e.control.begin(),true);
  e.nextTimer();
  await flush();
  assert.strictEqual(e.reloads,1,'bounded fallback renews when WWI close missing');
  console.log('PASS: same-origin single-tab renewal, token, replay, corrupt/lost checkpoint, HTTP content and fallback');
}
module.exports = testWindowRenewal;
if (require.main === module) testWindowRenewal().catch(err=>{console.error(err);process.exitCode=1;});
