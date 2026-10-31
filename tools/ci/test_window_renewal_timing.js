'use strict';
// Deterministic virtual-time adversarial tests of two *different* deadlines.
// No real sleep, external browser, profile or physical simulation dependency.
const assert = require('node:assert/strict');
const make = require('../../plugins/robot_windows/blockly_v2/window_renewal.js');
const TOKEN = 'a'.repeat(64);

async function flush() {
  for (let i = 0; i < 5; i++) await Promise.resolve();
}
function clockEnvironment() {
  let now = 0, seq = 0, reloads = 0, requests = 0;
  let checkpoint = JSON.stringify({version:2,token:TOKEN});
  const timers = new Map(), late = [];
  const location = {
    protocol:'http:',hostname:'localhost',
    pathname:'/robot_windows/blockly_v2/blockly_v2.html',
    href:'http://localhost:1234/robot_windows/blockly_v2/blockly_v2.html?name=Crazyflie',
    reload(){ reloads++; }
  };
  const root = {
    location, performance:{now:()=>now}, AbortController,
    localStorage:{getItem:()=>checkpoint},
    document:{getElementById:()=>({textContent:''})},
    setTimeout(fn,ms) {
      const id=++seq;
      timers.set(id,{at:now+ms,fn});
      return id;
    },
    clearTimeout(id){timers.delete(id);},
    fetch:()=>{throw Error('fetch handler missing');},
    navigator:{}
  };
  async function advance(ms) {
    const until=now+ms;
    for(let n=0;n<20000;n++) {
      await flush();
      let selected=null, id=null;
      for(const [k,v] of timers) if(v.at<=until && (!selected||v.at<selected.at)){
        selected=v;id=k;
      }
      if(!selected) break;
      now=selected.at;timers.delete(id);selected.fn();
    }
    now=until;
    await flush();
  }
  return {root, advance, late,
    warp(ms){now+=ms;}, // blocked event loop: due timers have NOT run
    get now(){return now;},get reloads(){return reloads;},
    get requests(){return requests;},
    set checkpoint(v){checkpoint=v;},
    fetch(handler){root.fetch=(url,opts)=>{
      requests++;
      assert.equal(url,location.href);
      assert.equal(opts.credentials,'same-origin');
      assert.equal(opts.redirect,'error');
      return handler(opts);
    };},
    response(ok=true){return {ok,headers:{get:()=> 'text/html; charset=utf-8'}};}
  };
}
class SharedLocks {
  constructor(ignoreAbort=false){
    this.busy=false;this.queue=[];this.concurrent=0;this.peak=0;
    this.ignoreAbort=ignoreAbort;
  }
  request(name,options,cb) {
    assert.equal(name,'webeeblocks-recovery-v1');
    assert.equal(options.mode,'exclusive');
    assert(options.signal);
    return new Promise((resolve,reject)=>{
      const item={cb,resolve,reject,options,active:true};
      if(!this.ignoreAbort)options.signal.addEventListener('abort',()=>{
        if(!item.active)return;
        item.active=false;this.queue=this.queue.filter(x=>x!==item);
        reject(Object.assign(new Error('Aborted'),{name:'AbortError'}));
      },{once:true});
      this.queue.push(item);this.pump();
    });
  }
  pump() {
    if(this.busy)return;
    const item=this.queue.shift();
    if(!item)return;
    if(!item.active){this.pump();return;}
    this.busy=true;this.concurrent++;this.peak=Math.max(this.peak,this.concurrent);
    Promise.resolve().then(item.cb).then(item.resolve,item.reject).finally(()=>{
      item.active=false;this.busy=false;this.concurrent--;this.pump();
    });
  }
}

async function test() {
  // HTTP permanently blocked AND deliberately ignoring AbortSignal. The
  // explicit Promise.race prevents a hung fetch from hanging the recovery.
  {
    const e=clockEnvironment(), responses=[];
    e.fetch(()=>new Promise(resolve=>responses.push(resolve)));
    const renewal=make(e.root);
    assert(renewal.arm(TOKEN));
    assert(renewal.onTransportClose());
    await e.advance(30100);
    assert.equal(e.reloads,0);
    assert(e.requests>=10 && e.requests<=26,'finite request count');
    responses.forEach(resolve=>resolve(e.response()));
    await flush();
    assert.equal(e.reloads,0,'late HTTP response cannot reopen after deadline');
    assert(renewal.onTransportClose(),'WWI close still intercepted without reopening');
    await e.advance(5000);
    assert.equal(e.reloads,0,'single-use after expiration');
  }
  // Late-but-in-deadline HTTP availability must work; the deadline does not
  // accidentally impose a 12 s cap because of the previous fixed 24 polls.
  {
    const e=clockEnvironment();
    e.fetch(()=>Promise.resolve(e.response(e.now>=29500)));
    const renewal=make(e.root);
    assert(renewal.arm(TOKEN));renewal.onTransportClose();
    await e.advance(30001);
    assert.equal(e.reloads,1,'29.5 s availability must navigate');
    renewal.onTransportClose();
    await e.advance(30000);
    assert.equal(e.reloads,1,'no second navigation');
  }
  // A response after the 30 s deadline cannot trigger navigation even if it
  // reports HTTP 200 and the browser ignores AbortSignal.
  {
    const e=clockEnvironment(), delayed=[];
    e.fetch(()=>new Promise(resolve=>delayed.push(resolve)));
    const renewal=make(e.root);
    renewal.arm(TOKEN);renewal.onTransportClose();
    await e.advance(30000);
    delayed.forEach(resolve=>resolve(e.response()));
    await flush();
    assert.equal(e.reloads,0);
  }
  // Disarm must make even a late HTTP 200 non-authoritative.
  {
    const e=clockEnvironment(), delayed=[];
    e.fetch(()=>new Promise(resolve=>delayed.push(resolve)));
    const renewal=make(e.root);
    renewal.arm(TOKEN);renewal.onTransportClose();
    renewal.disarm();
    delayed.forEach(resolve=>resolve(e.response()));
    await e.advance(31000);
    assert.equal(e.reloads,0);
  }
  // Web Locks: unavailable capability fails CLOSED and does not run callback.
  {
    const e=clockEnvironment();let invoked=0;
    const renewal=make(e.root);
    await assert.rejects(renewal.withRecoveryLock(()=>{invoked++;}),/indisponible/);
    assert.equal(invoked,0);
  }
  // Held lock for >10 s. Even a deliberately NON-COMPLIANT Lock Manager that
  // ignores abort signals and grants the old request later must not run it.
  {
    const e=clockEnvironment(), locks=new SharedLocks(true);e.root.navigator.locks=locks;
    let unblock;
    const held=locks.request('webeeblocks-recovery-v1',{mode:'exclusive',signal:new AbortController().signal},
      ()=>new Promise(resolve=>unblock=resolve));
    await flush();
    let invoked=0;
    const result=make(e.root).withRecoveryLock(()=>{invoked++;}).then(()=>null,e=>e);
    await e.advance(10100);
    const error=await result;
    assert.match(error.message,/expirée/);
    assert.equal(invoked,0);
    unblock();await held;await flush();
    assert.equal(invoked,0,'late lock grant after expiration is rejected before native calls');
    assert(locks.peak<=1);
  }
  // Event-loop suspension can delay the timer task while Web Locks itself
  // grants a queued request. A monotonic check INSIDE the callback must deny
  // this grant even when the abort callback has never run.
  {
    const e=clockEnvironment(),locks=new SharedLocks(true);e.root.navigator.locks=locks;
    let release;
    const first=locks.request('webeeblocks-recovery-v1',
      {mode:'exclusive',signal:new AbortController().signal},
      ()=>new Promise(resolve=>release=resolve));
    await flush();
    let nativeCalls=0;
    const late=make(e.root).withRecoveryLock(()=>{nativeCalls++;})
      .then(()=>null,err=>err);
    e.warp(11000); // simulate a frozen browser tab, no timer delivery
    release();
    await first;await flush();
    const verdict=await late;
    assert.match(verdict.message,/après expiration/);
    assert.equal(nativeCalls,0,'grant after 10s cannot start native work');
  }
  // A holder may legitimately take >10 s doing physical RESET/SCENE checks:
  // the acquisition timer is disarmed as soon as the lock is granted.
  {
    const e=clockEnvironment(),locks=new SharedLocks();e.root.navigator.locks=locks;
    let unblock;
    const holder=make(e.root).withRecoveryLock(
      ()=>new Promise(resolve=>unblock=resolve));
    await flush();
    await e.advance(15000);
    let done=false;unblock('verified');
    const output=await holder;done=true;
    assert.equal(output,'verified');assert(done);
    assert.equal(locks.peak,1);
  }
  // Two documents with SAME browser storage share one lock; only the first
  // gets to consume the independent native witness/checkpoint. A disappeared
  // holder releases the lock; the next request can acquire before its deadline.
  {
    const a=clockEnvironment(),b=clockEnvironment(),locks=new SharedLocks();
    a.root.navigator.locks=locks;b.root.navigator.locks=locks;
    let release, checkpoint=true, nativeCalls=0;
    const one=make(a.root).withRecoveryLock(async()=>{
      assert(checkpoint);nativeCalls++;
      await new Promise(resolve=>release=resolve);
      checkpoint=false;
    });
    await flush();
    let secondResult=null;
    const two=make(b.root).withRecoveryLock(async()=>{
      if(!checkpoint)throw Error('checkpoint consumed; flight remains blocked');
      nativeCalls++; checkpoint=false;
    }).then(()=>null,err=>err);
    await b.advance(4000);
    assert.equal(nativeCalls,1);
    release();
    await one;
    await flush();
    secondResult=await two;
    assert.match(secondResult.message,/checkpoint consumed/);
    assert.equal(nativeCalls,1,'no concurrent second native authority');
    assert.equal(locks.peak,1);
  }
  console.log('PASS: absolute HTTP deadline, hung/late HTTP, cancellation, timed Web Lock, lock loss, shared-profile exclusion');
}
module.exports = test;
if (require.main === module) test().catch(e=>{console.error(e);process.exitCode=1;});
