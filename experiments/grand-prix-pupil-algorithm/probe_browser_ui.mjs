// Isolated optional Chromium classroom UI observation for experimental GP234_CLASSROOM.
// No Webots, no physical API, no claim that fake transport proves robot motion.
const {chromium}=await import(process.env.WEBEEBLOCKS_PLAYWRIGHT_MODULE || 'playwright');
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const candidatePath='experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb';
const candidate=fs.readFileSync(path.join(root,candidatePath),'utf8');
const parsed=JSON.parse(candidate);
const output=path.resolve(process.env.WEBEEBLOCKS_UI_OUTPUT||path.join(root,'ci-artifacts/gp234-classroom-browser-ui'));
fs.mkdirSync(output,{recursive:true});
const server=http.createServer((req,res)=>{
  try {
    const url=new URL(req.url,'http://127.0.0.1');
    const file=path.resolve(root,'.'+decodeURIComponent(url.pathname));
    if(!file.startsWith(root+path.sep))throw new Error('outside repository');
    const type=file.endsWith('.js')?'application/javascript':file.endsWith('.html')?'text/html':file.endsWith('.css')?'text/css':'application/octet-stream';
    res.setHeader('Content-Type',type);res.end(fs.readFileSync(file));
  } catch(e){res.statusCode=404;res.end();}
});
await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
const origin='http://127.0.0.1:'+server.address().port;
const errors=[], warnings=[],events=[];
let browser;
try{
 browser=await chromium.launch({executablePath:process.env.CHROME_BIN||undefined,headless:true,
   args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1600,height:1000}});
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('console',m=>{if(m.type()==='error')warnings.push(m.text());});
 await page.addInitScript(({candidate})=>{
   window.testProjectText=candidate;
   window.testWrites=[];
   window.testCommands=[];
   window.testPaused=[];
   const handle={
     name:'grand-prix-pupil-candidate.wbb',
     async getFile(){return {name:this.name,text:async()=>window.testProjectText};},
     async createWritable(){return {async write(text){window.testProjectText=text;window.testWrites.push(text);},async close(){}};}
   };
   window.showOpenFilePicker=async()=>[handle];
   window.showSaveFilePicker=async()=>handle;
   window.addEventListener('webeeblocks-debug-paused',e=>window.testPaused.push(e.detail.blockId));
 },{candidate});
 await page.route('**/blockly_v2/webots/RobotWindow.js',route=>route.fulfill({contentType:'application/javascript',body:`
 export default class RobotWindow {
   send(message) {
     window.testCommands.push(message);
     const parts=String(message).split(' ');
     const reply=parts[1]==='HELLO' ? 'WEBEEBLOCKS_RUNTIME_V2 READY HELLO' :
       ('WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+parts[2]+' '+(parts[3]==='OUTCOME'?'STATE not-achieved':
       parts[3]==='RANGE'?'VALUE 2.0':'OK'));
     setTimeout(()=>this.receive(reply),0);
   }
 }`}));
 await page.goto(origin+'/plugins/robot_windows/grand_prix_u/grand_prix_u.html');
 await page.waitForFunction(()=>window.WebeeBlocksProjectManager && document.body.dataset.runtimeState==='PRÊT',{timeout:30000});
 await page.getByRole('button',{name:'Ouvrir',exact:true}).click();
 await page.waitForFunction(()=>window.workspace?.getAllBlocks(false).length===234,{timeout:30000});
 async function inspect(label){
   return await page.evaluate(label=>{
     const all=workspace.getAllBlocks(false),ids=all.map(b=>b.id).sort(),bounds=workspace.getBlocksBoundingBox();
     const m=workspace.getMetrics(),root=workspace.getTopBlocks(false),rect=document.querySelector('.blocklySvg')?.getBoundingClientRect();
     const names=workspace.getVariableMap().getAllVariables().map(v=>v.name).sort();
     const blockRoots=root.map(b=>({type:b.type,id:b.id,name:b.getFieldValue('NAME')||null}));
     const treeDepth=b=>{let p=b.getParent(),i=0;while(p){i++;p=p.getParent();}return i;};
     const maxParentDepth=Math.max(...all.map(treeDepth));
     return {label,blocks:all.length,ids,variables:names,
       top: blockRoots,deepestParentChain:maxParentDepth,
       workspaceScale:workspace.scale,
       workspaceBBoxPx:{width:bounds.right-bounds.left,height:bounds.bottom-bounds.top},
       viewportRectPx:rect?{width:rect.width,height:rect.height}:null,
       scrollMetrics:m&&{viewWidth:m.viewWidth,viewHeight:m.viewHeight,
                          contentWidth:m.contentWidth,contentHeight:m.contentHeight,
                          scrollWidth:m.scrollWidth,scrollHeight:m.scrollHeight,
                          absoluteLeft:m.absoluteLeft,absoluteTop:m.absoluteTop},
       runtimeState:document.body.dataset.runtimeState};
   },label);
 }
 const initial=await inspect('before-fit');
 assert.equal(initial.blocks,234);assert.equal(initial.variables.length,10);
 assert.equal(initial.top.length,5,'one main stack + four ordinary student procedures');
 assert.equal(initial.top.filter(b=>b.type==='procedures_defnoreturn').length,4);
 for (const name of ['parcourir un côté','observer et décider','franchir et confirmer le H','approcher le H fermé et poser'])
   assert(initial.top.some(b=>b.name===name),'named pupil procedure not visible: '+name);
 assert(initial.top.some(b=>b.type==='webeeblocks_v2_takeoff'));
 // Browser-only layout qualification: prevent pupil blocks from occluding one another.
 const packing=await page.evaluate(()=>{
   const roots=workspace.getTopBlocks(false);
   const bounds=root=>{
     const rs=root.getDescendants(false).map(b=>b.getBoundingRectangle());
     return {left:Math.min(...rs.map(r=>r.left)),right:Math.max(...rs.map(r=>r.right)),
       top:Math.min(...rs.map(r=>r.top)),bottom:Math.max(...rs.map(r=>r.bottom))};
   };
   const observed=roots.map(b=>({name:b.getFieldValue('NAME')||'programme',
     type:b.type,bounds:bounds(b),position:b.getRelativeToSurfaceXY()}));
   const overlaps=[];
   for(let i=0;i<observed.length;i++)for(let j=i+1;j<observed.length;j++){
     const a=observed[i].bounds,b=observed[j].bounds;
     if(a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom)
       overlaps.push(observed[i].name+' / '+observed[j].name);
   }
   if(overlaps.length)throw Error('ORIGINAL WBB layout collision '+JSON.stringify(overlaps));
   return {originalRootPositions:observed,overlaps};
 });
 console.log('ORIGINAL_WBB_NO_OVERLAP '+JSON.stringify(packing));
 await page.evaluate(()=>{Blockly.svgResize(workspace);workspace.zoomToFit();});
 const fitted=await inspect('after-non-overlap-fit');
 await page.screenshot({path:path.join(output,'gp234-classroom-1600x1000-fit.png'),fullPage:true});
 // Real browser gesture, not a scripted field.setValue shortcut:
 // center the ordinary numeric Blockly field; click, type, commit the editor.
 await page.evaluate(()=>workspace.centerOnBlock('gp-pupil-v2-b-109'));
 // Blockly scroll/transform is asynchronous; measure the field only after render.
 await page.waitForTimeout(350);
 const target=await page.evaluate(()=>{
   const block=workspace.getBlockById('gp-pupil-v2-b-109');
   if(!block||block.type!=='math_number')throw Error('pupil open-H threshold block missing');
   const field=block.getField('NUM');
   const box=field.getSvgRoot().getBoundingClientRect();
   const x=box.left+box.width/2,y=box.top+box.height/2;
   const hit=document.elementFromPoint(x,y);
   return {before:field.getValue(),x,y,bounds:{left:box.left,top:box.top,width:box.width,height:box.height},
     hitTag:hit?.tagName||null,hitClass:hit?.getAttribute('class')||null};
 });
 console.log('PUPIL_THRESHOLD_MOUSE_TARGET '+JSON.stringify(target));
 assert(target.x>110 && target.x<1550 && target.y>227 && target.y<990,
   'number field not in visible Blockly workspace after centering');
 await page.mouse.click(target.x,target.y);
 const fieldEditor=page.locator('input.blocklyHtmlInput').first();
 await fieldEditor.waitFor({state:'visible',timeout:5000});
 await fieldEditor.fill('0.31');
 await fieldEditor.press('Enter');
 const edited={before:target.before,after:await page.evaluate(
   ()=>workspace.getBlockById('gp-pupil-v2-b-109')?.getFieldValue('NUM'))};
 assert.equal(Number(edited.before),0.3);
 assert.equal(Number(edited.after),0.31);
 await page.getByRole('button',{name:'Enregistrer sous',exact:true}).click();
 await page.waitForFunction(()=>window.testWrites.length===1,{timeout:20000});
 await page.evaluate(()=>workspace.clear());
 await page.getByRole('button',{name:'Ouvrir',exact:true}).click();
 await page.waitForFunction(()=>workspace.getAllBlocks(false).length===234,{timeout:20000});
 const reopened=await inspect('reopened');
 const modified=await page.evaluate(()=>workspace.getBlockById('gp-pupil-v2-b-109')?.getFieldValue('NUM'));
 assert.equal(Number(modified),0.31,'saved pupil threshold edit must survive reopening');
 assert.deepEqual(reopened.ids,initial.ids,'browser Save/Open changed original block IDs');
 assert.deepEqual(reopened.variables,initial.variables,'browser Save/Open changed variables');
 assert.deepEqual(reopened.top,initial.top,'browser Save/Open changed procedure/main identity');
 assert.equal(errors.length,0,'browser runtime errors before stepping: '+errors.join('; '));
 await page.locator('#stepMode').check();
 await page.getByRole('button',{name:'Lancer le vol',exact:true}).click();
 await page.waitForFunction(()=>!document.getElementById('stepNext').disabled,{timeout:15000});
 const firstPaused=await page.evaluate(()=>window.testPaused.slice());
 const firstId=firstPaused.at(-1);
 assert(initial.ids.includes(firstId),'step-mode pause not mapped to a real candidate block');
 // Advance only two genuine browser control steps, not fake a mission result.
 for(let i=0;i<2;i++){
   const count=await page.evaluate(()=>window.testPaused.length);
   await page.locator('#stepNext').click();
   await page.waitForFunction(n=>window.testPaused.length>n||!window.runtimeRunning,count,{timeout:10000});
 }
 const stepped=await page.evaluate(()=>({pausedBlocks:window.testPaused.slice(),commands:window.testCommands.slice(),writes:window.testWrites.length}));
 assert(stepped.pausedBlocks.length>=2,'browser debugger did not progress');
 assert(stepped.pausedBlocks.every(id=>initial.ids.includes(id)),'browser debugger highlights an unknown ID');
 fs.writeFileSync(path.join(output,'metrics.json'),JSON.stringify({
   exactProjectActivity:parsed.activity.id,head:'7204975ad0d05b0fb2bcfe56e2690e225dfd9266',
   sourceBlockCount:234,chromium:browser.version(),viewport:[1600,1000],
   initial,fitted,packing,reopened:{...reopened,ids:'234 IDs unchanged'},editedThreshold:edited,debug:{
     steps:stepped.pausedBlocks.length,matchedRealBlocks:true,firstPausedBlockId:firstId,
     commands:stepped.commands.length},browserErrors:errors,consoleErrors:warnings,
   notes:['Browser is real headless Chromium and UI is production Robot Window.',
     'Transport and Webots RobotWindow are stubbed; no native physical move or mission result.',
     'Threshold edit uses Playwright mouse click and keyboard entry in real Blockly field; not proof of independent pupil performance.',
     'File picker is injected; not a verified native OS file dialog.',
     'Static screenshots and dimensions are not human classroom acceptance.']
 },null,2)+'\n');
 console.log('PASS_GP234_WBB_ORIGINAL_CHROMIUM_UI '+JSON.stringify({
   blocks:initial.blocks,variables:initial.variables.length,roots:initial.top,
   chain:initial.deepestParentChain,
   before:initial.workspaceBBoxPx,viewport:initial.viewportRectPx,
   fittedScale:fitted.workspaceScale,fitBBox:fitted.workspaceBBoxPx,
   writes:stepped.writes,paused:stepped.pausedBlocks.length,
   browserErrors:errors.length,consoleErrors:warnings.length}));
} catch(e){
 fs.writeFileSync(path.join(output,'error.txt'),String(e.stack||e)+'\n');
 console.error('FAIL_GP234_CLASSROOM_CHROMIUM_UI',e);
 process.exitCode=1;
} finally {
 if(browser)await browser.close();
 server.close();
}
