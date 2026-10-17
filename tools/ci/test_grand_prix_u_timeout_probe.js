'use strict';
// Execute the production probe orchestration across both legal native phases.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'grand_prix_u_node_probe.js'),'utf8');
(async()=>{
 for(const installed of [false,true]){
 for(const landed of [false,true]){
  const events=[],commands=[],modules=[];let socket,reset=false;
  const root=installed?path.resolve('installed project with spaces'):path.resolve(__dirname,'../..');
  class Socket{constructor(){socket=this;}send(){}close(){}}
  class Backend{
   async waitUntilReady(){}
   handleMessage(){}
   async _request(parts){
    commands.push(parts[0]);
    events.push({event:'request',detail:'WEBEEBLOCKS_RUNTIME_V2 REQUEST '+commands.length+' '+parts.join(' ')});
    if(parts[0]==='OUTCOME'){
     if(!reset)return 'not-achieved';
     throw Object.assign(new Error('fresh attempt'),{code:'OUTCOME_UNAVAILABLE'});
    }
    if(parts[0]==='RESET'&&landed){reset=true;return null;}
    throw Object.assign(new Error('expired'),{code:'TIME_LIMIT'});
   }
   async resetSimulation(){return this._request(['RESET']);}
  }
  const context={__dirname,WebSocket:Socket,console:{log:line=>events.push(JSON.parse(line.slice('GP_U_NODE '.length)))},
   process:{argv:['node','probe','12345','timeout',undefined,...(installed?[root]:[])],exit(){throw new Error('unexpected exit');}},
   setTimeout:()=>({unref(){}}),require:name=>{
    if(name==='fs')return fs;
    if(name==='path')return path;
    if(name===path.join(root,'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js')){modules.push('backend');return Backend;}
    if(name===path.join(root,'plugins/robot_windows/blockly/webeeblocks/interpreter.js')){modules.push('interpreter');return {run:async()=>{throw Object.assign(new Error('deadline'),{code:'TIME_LIMIT'});}};}
    if(name.includes('witness_workspace'))return {build:()=>({ast:{}})};
    throw new Error('unexpected require '+name);
   }};
  vm.runInNewContext(source,context);await socket.onopen();
  assert.deepStrictEqual(modules,['backend','interpreter']);
  assert.deepStrictEqual(commands,landed?['COMPLETE','FAILURE','MOVE','STOP','OUTCOME','RESET','OUTCOME']:
   ['COMPLETE','FAILURE','MOVE','STOP','OUTCOME','RESET']);
  const result=events.find(e=>e.event==='late-outcome-read');assert.strictEqual(result.detail.status,'not-achieved');
  assert(events.find(e=>e.event===(landed?'recovery-reset-accepted':'recovery-reset-rejected')));
  assert(!events.some(e=>e.event==='late-command-accepted'||e.event==='late-stop-accepted'||e.event==='recovery-stale-outcome'));
  if(landed)assert(events.find(e=>e.event==='recovery-outcome-error').detail.code==='OUTCOME_UNAVAILABLE');
 }
 }
 console.log('PASS timeout probe: expired evidence precedes RESET, both native recovery phases, fresh outcome and no automatic retry');
})().catch(e=>{console.error(e);process.exitCode=1;});
