// Optional browser QA: no Webots process or mission oracle is substituted here.
const {chromium}=await import(process.env.WEBEEBLOCKS_PLAYWRIGHT_MODULE || 'playwright');
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const server=http.createServer((req,res)=>{const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);try{res.setHeader('Content-Type',p.endsWith('.js')?'application/javascript':p.endsWith('.html')?'text/html':p.endsWith('.css')?'text/css':'application/octet-stream');res.end(fs.readFileSync(p));}catch(e){res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin='http://127.0.0.1:'+server.address().port;
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:process.env.CHROME_BIN || undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--single-process','--no-zygote','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}).catch(error=>{server.close();throw error;});
const page=await browser.newPage({viewport:{width:1600,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
const fixture=fs.readFileSync(root+'/tools/blockly/procedure_steps_demo.wbb','utf8');
await page.addInitScript(({fixture})=>{
 window.testWrites=[];window.testProjectText=fixture;window.testMessages=[];window.testBlocks=[];
 const handle={name:'procedure_steps_demo.wbb',async getFile(){return {name:this.name,text:async()=>window.testProjectText};},async createWritable(){let staged=window.testProjectText;return {async write(text){staged=text;},async close(){window.testProjectText=staged;window.testWrites.push(staged);},async abort(){staged=null;}};}};
 window.showOpenFilePicker=async()=>[handle];window.showSaveFilePicker=async()=>handle;
 window.addEventListener('webeeblocks-debug-paused',e=>window.testBlocks.push(e.detail.blockId));
}, {fixture});
await page.route('**/blockly_v2/webots/RobotWindow.js',route=>route.fulfill({contentType:'application/javascript',body:`export default class RobotWindow {
 send(message){window.testMessages.push(message);const a=message.split(' ');setTimeout(()=>this.receive(a[1]==='HELLO'?'WEBEEBLOCKS_RUNTIME_V2 READY HELLO':'WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+a[2]+' '+(a[3]==='OUTCOME'?'STATE not-achieved':'OK')),0);}
}`}));
try{
 await page.goto(origin+'/plugins/robot_windows/grand_prix_u/grand_prix_u.html');
 await page.waitForFunction(()=>window.WebeeBlocksProjectManager && document.body.dataset.runtimeState==='PRÊT');
 await page.getByRole('button',{name:'Ouvrir',exact:true}).click();
 await page.waitForFunction(()=>workspace.getAllBlocks(false).length===11);
 await page.getByRole('treeitem',{name:'Procédures',exact:true}).click();
 const flyout=await page.evaluate(()=>workspace.getToolbox().getFlyout().getWorkspace().getTopBlocks(false).map(b=>({type:b.type,name:b.getProcedureCall?.(),icons:b.getIcons().map(i=>i.getType().toString())})));
 assert.deepEqual(flyout.map(x=>x.type),['procedures_defnoreturn','procedures_callnoreturn']);
 assert.equal(flyout[1].name,'avancer_un_pas');assert(!flyout[0].icons.includes('mutator'));
 await page.evaluate(()=>{workspace.getToolbox().clearSelection();Blockly.svgResize(workspace);workspace.zoomToFit();});
 if(process.env.WEBEEBLOCKS_UI_SCREENSHOT) await page.screenshot({path:process.env.WEBEEBLOCKS_UI_SCREENSHOT,fullPage:true});
 // Exercise real Save As and Open handlers with an injected file-picker boundary.
 await page.getByRole('button',{name:'Enregistrer sous',exact:true}).click();await page.waitForFunction(()=>testWrites.length===1);
 await page.evaluate(()=>workspace.clear());await page.getByRole('button',{name:'Ouvrir',exact:true}).click();
 await page.waitForFunction(()=>workspace.getAllBlocks(false).length===11);
 await page.locator('#stepMode').check();await page.getByRole('button',{name:'Lancer le vol',exact:true}).click();
 await page.waitForFunction(()=>!document.getElementById('stepNext').disabled);
 for(let i=0;i<60;i++){
  if(await page.evaluate(()=>!runtimeRunning))break;
  await page.locator('#stepNext').click();
  await page.waitForFunction(()=>!runtimeRunning||!document.getElementById('stepNext').disabled);
 }
 await page.waitForFunction(()=>!runtimeRunning);
 const outcome=await page.evaluate(()=>({blocks:testBlocks,messages:testMessages,variables:document.getElementById('debugVariables').textContent,state:document.body.dataset.runtimeState,types:workspace.getAllBlocks(false).map(b=>b.type),writes:testWrites.length}));
 const ids=await page.evaluate(()=>Object.fromEntries(['procedures_callnoreturn','webeeblocks_v2_move','math_change'].map(t=>[t,workspace.getAllBlocks(false).find(b=>b.type===t).id])));
 for(const [t,id]of Object.entries(ids))assert(outcome.blocks.includes(id),'not stepped: '+t);
 assert(outcome.variables.includes('3'));assert.equal(outcome.state,'MISSION NON RÉUSSIE');assert.equal(errors.length,0,errors.join('\n'));
 console.log(JSON.stringify({browser:browser.version(),flyout,steps:outcome.blocks.length,blocks:outcome.types.length,writes:outcome.writes,variables:outcome.variables,state:outcome.state,pageErrors:errors,nativeWebots:false,transport:'injected acknowledged commands; negative mission result'},null,2));
}finally{await browser.close();server.close();}
