// Optional real Blockly/Zelos UI check. Transport/file pickers are injected;
// this is not Webots, a native OS-dialog test, or a physical qualification.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.WEBEEBLOCKS_PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const server=http.createServer((req,res)=>{
 const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
 if(!p.startsWith(root+path.sep)){res.statusCode=403;res.end();return;}
 try{res.setHeader('Content-Type',p.endsWith('.js')?'application/javascript':p.endsWith('.html')?'text/html':p.endsWith('.css')?'text/css':'application/octet-stream');res.end(fs.readFileSync(p));}catch{res.statusCode=404;res.end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.CHROME_BIN,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--single-process','--no-zygote','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}).catch(e=>{server.close();throw e;});
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(fixture=>{
 window.testText=fixture;window.testWrites=[];window.testSteps=[];window.testMessages=[];window.testRanges=[.83,.73,.63,.53,.43,.43,.33];
 const handle={name:'compact_u_demo.wbb',async getFile(){return{name:this.name,text:async()=>testText};},async createWritable(){return{write:async text=>{testText=text;testWrites.push(text);},close:async()=>{}};}};
 window.showOpenFilePicker=async()=>[handle];window.showSaveFilePicker=async()=>handle;
 window.addEventListener('webeeblocks-debug-paused',e=>testSteps.push({id:e.detail.blockId,phase:e.detail.phase}));
},fs.readFileSync(root+'/tools/blockly/compact_u_demo.wbb','utf8'));
await page.route('**/blockly_v2/webots/RobotWindow.js',route=>route.fulfill({contentType:'application/javascript',body:`export default class RobotWindow {
 send(message){window.testMessages.push(message);const a=message.split(' ');setTimeout(()=>this.receive(a[1]==='HELLO'?'WEBEEBLOCKS_RUNTIME_V2 READY HELLO':'WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+a[2]+' '+(a[3]==='RANGE'?'VALUE '+testRanges.shift():a[3]==='OUTCOME'?'STATE not-achieved':'OK')),0);}
}`}));
try{
 await page.goto('http://127.0.0.1:'+server.address().port+'/plugins/robot_windows/grand_prix_u/grand_prix_u.html');
 await page.waitForFunction(()=>window.WebeeBlocksProjectManager&&document.body.dataset.runtimeState==='PRÊT');
 await page.getByRole('button',{name:'Ouvrir',exact:true}).click();await page.waitForFunction(()=>workspace.getAllBlocks(false).length===63);
 await page.evaluate(()=>{Blockly.svgResize(workspace);workspace.zoomToFit();});
 if(process.env.WEBEEBLOCKS_UI_SCREENSHOT)await page.screenshot({path:process.env.WEBEEBLOCKS_UI_SCREENSHOT,fullPage:true});
 const before=await page.evaluate(()=>({ast:WebeeBlocksSemanticAst.compileWorkspace(workspace),map:WebeeBlocksExecutionObserver.buildSourceMap(workspace)}));
 await page.getByRole('button',{name:'Enregistrer sous',exact:true}).click();await page.waitForFunction(()=>testWrites.length===1);
 await page.evaluate(()=>workspace.clear());await page.getByRole('button',{name:'Ouvrir',exact:true}).click();await page.waitForFunction(()=>workspace.getAllBlocks(false).length===63);
 assert.deepEqual(await page.evaluate(()=>({ast:WebeeBlocksSemanticAst.compileWorkspace(workspace),map:WebeeBlocksExecutionObserver.buildSourceMap(workspace)})),before);
 const info=await page.evaluate(()=>({blocks:workspace.getAllBlocks(false).length,scale:workspace.scale,bounds:workspace.getBlocksBoundingBox(),variables:workspace.getVariableMap().getAllVariables().map(v=>v.name),writes:testWrites.length}));
 assert.equal(info.blocks,63);assert.equal(info.variables.length,2);assert.equal(info.writes,1);assert.equal(errors.length,0,errors.join('\n'));
 console.log(JSON.stringify({browser:browser.version(),...info,errors,execution:false,nativeWebots:false,transport:'injected'},null,2));
}finally{await browser.close();server.close();}
