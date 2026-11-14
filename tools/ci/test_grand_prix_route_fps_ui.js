'use strict';
/* Deterministic isolated browser DOM/WWI contract tests; not a GUI acceptance. */
const assert = require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const listeners={};
function makeElement() {
  return {
    value:'20', disabled:true, hidden:true, textContent:'', dataset:{}, attributes:{}, listeners:{},
    addEventListener(name,callback) {(this.listeners[name]??=[]).push(callback);},
    setAttribute(name,value){this.attributes[name]=value;},
    contains(target){return target===this;},
    focus(){},
    fire(name,props={}){for(const fn of this.listeners[name]||[])fn(props);}
  };
}
const elements={};
for(const id of ['gpFpsControl','gpFpsToggle','gpFpsPanel','gpFpsSlider','gpFpsValue','gpFpsStatus'])
  elements[id]=makeElement();
const document={
  readyState:'complete',
  getElementById(id){return elements[id]??null;},
  addEventListener() {}
};
const sent=[];
let id=0;
const window={
  crypto:{getRandomValues(arr){for(let i=0;i<arr.length;i++)arr[i]=(i+id)%256;id++;}},
  runtimeBackend:{ready:true,robotWindow:{send(msg){sent.push(msg);}}},
  runtimeRunning:false,runtimeTerminal:false,runtimeResetPending:false,runtimeStopPending:false,
  runtimeOutcomePending:false,runtimeScenePending:false,runtimeProjectPending:false,
  addEventListener(name,fn){(listeners[name]??=[]).push(fn);},
  setTimeout(){return 1;},clearTimeout(){}
};
const context={window,document,Uint8Array,Number,Array,String};
vm.runInNewContext(
  fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/fps_settings.js','utf8'),context);
function event(name,detail){for(const fn of listeners[name]||[])fn({detail});}
function response(kind,request,value){
  const nonce=request.match(/nonce=([0-9a-f]{32})$/)?.[1];
  assert.ok(nonce,'request has a nonce');
  event('webeeblocks-gp-fps-response',{raw:'GP_ROUTE_FPS_V1 '+kind+
    ' nonce='+nonce+' '+(kind==='REFUSED'?'reason='+value:'fps='+value)});
}
const slider=elements.gpFpsSlider, status=elements.gpFpsStatus;
assert.equal(slider.disabled,true,'locked during initialization');
event('webeeblocks-runtime-v2',{state:'PRÊT'});
assert.match(sent[0],/^GP_ROUTE_FPS_V1 GET nonce=[0-9a-f]{32}$/);
response('CURRENT',sent[0],20);
assert.equal(slider.disabled,false,'unlocked after verified native READY & GET');
slider.value='15';slider.fire('input');slider.fire('change');
assert.match(sent[1],/^GP_ROUTE_FPS_V1 SET fps=15 nonce=[0-9a-f]{32}$/);
assert.equal(slider.disabled,true,'locked until native APPLIED response');
response('APPLIED',sent[1],15);
assert.equal(slider.disabled,false);
assert.equal(elements.gpFpsValue.textContent,'15 FPS');
assert.match(status.textContent,/appliqué/i);
window.runtimeRunning=true;
event('webeeblocks-runtime-v2',{state:'EXÉCUTION'});
assert.equal(slider.disabled,true,'disabled throughout flight');
slider.value='25';slider.fire('change');
assert.equal(sent.length,2,'no message during a flight even on scripted change event');
assert.equal(slider.value,'15','revert unapproved preview');
window.runtimeRunning=false;
window.runtimeTerminal=true;
event('webeeblocks-runtime-v2',{state:'TERMINÉ'});
assert.equal(slider.disabled,true,'must reset before another change');
window.runtimeTerminal=false;
event('webeeblocks-runtime-v2',{state:'PRÊT'});
assert.match(sent[2],/^GP_ROUTE_FPS_V1 GET nonce=[0-9a-f]{32}$/);
response('CURRENT',sent[2],15);
assert.equal(slider.disabled,false);
slider.value='23';slider.fire('change');
response('REFUSED',sent[3],'BUSY');
assert.equal(slider.value,'15','native BUSY preserves last confirmed setting');
assert.match(status.textContent,/refusé/i);
slider.value='23';slider.fire('change');
response('APPLIED',sent[4],23);
assert.equal(slider.value,'23');
assert.equal(slider.disabled,false);
elements.gpFpsToggle.fire('click');
assert.equal(elements.gpFpsPanel.hidden,false,'popover opens');
assert.equal(elements.gpFpsToggle.attributes['aria-expanded'],'true');
elements.gpFpsToggle.fire('click');
assert.equal(elements.gpFpsPanel.hidden,true,'popover closes');
console.log('GP_ROUTE_FPS_WEB_UI_STATE_AND_NONCE_PASS');
