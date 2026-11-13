'use strict';
// Static profile + project-identity contract only; native GUI/mission not claimed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Activities = require('../../plugins/robot_windows/blockly/webeeblocks/activities');
const Profiles = require('../../plugins/robot_windows/blockly/webeeblocks/activity_profiles');
const Projects = require('../../plugins/robot_windows/blockly/webeeblocks/project_files');
const WwiBackend = require('../../plugins/robot_windows/blockly/webeeblocks/wwi_backend');

const variable = fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/setup.js', 'utf8');
const historical = fs.readFileSync('plugins/robot_windows/grand_prix_u/setup.js', 'utf8');
const html = fs.readFileSync('plugins/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html', 'utf8');

function load(source, catalog) {
  const context = {
    WebeeBlocksActivities: {BLOCK_CATALOG: catalog, DOCUMENT: Activities.DOCUMENT},
    WebeeBlocksRuntimeOutcome: {classify: () => null},
    WebeeBlocksActivityContract: {
      execute() {}, preflightWorkspace() {}, applyFieldBounds() {}
    },
    Blockly: {inject: (_element, options) => options},
    WebeeBlocksWwiBackend: function (_window, options) { this.options = options; }
  };
  context.window = context;
  vm.runInNewContext(source, context);
  const profile = Profiles.resolveById(context.WebeeBlocksActivities.DOCUMENT,
    context.WebeeBlocksInitialActivityId, catalog);
  return {profile, context};
}

function run(loops) {
  const catalog = Object.assign({}, Activities.BLOCK_CATALOG);
  if (loops) catalog.controls_whileUntil = {category: 'control'};
  else delete catalog.controls_whileUntil;
  const a = load(variable, catalog);
  const u = load(historical, catalog);
  const profile = a.profile;
  assert.equal(profile.id, 'progression-grand-prix-route-v2');
  assert.equal(profile.world, 'worlds/grand_prix_route_v2.wbt');
  assert.equal(profile.evaluation.oracle, 'grand-prix-route-v2');
  assert.equal(profile.evaluation.type, 'mission-state-v1');
  assert.equal(a.context.WebeeBlocksInitialActivityId, profile.id);
  assert.equal(profile.toolbox.includes('controls_whileUntil'), loops);
  assert.equal(profile.runtime.maxSteps, 20000);
  assert.equal(JSON.stringify(profile.toolbox), JSON.stringify(u.profile.toolbox),
    'use the existing generic block vocabulary unchanged');
  assert.equal(JSON.stringify(profile.runtime), JSON.stringify(u.profile.runtime),
    'retain existing AST/preflight bounds and runtime policy');
  assert.equal(JSON.stringify(profile.parameterBounds), JSON.stringify(u.profile.parameterBounds));
  assert.equal(JSON.stringify(profile.fieldOptions), JSON.stringify(u.profile.fieldOptions));
  const routeOptions = new a.context.WebeeBlocksWwiBackend({}, {}).options;
  assert.equal(routeOptions.simulationScenes, false);
  assert.equal(routeOptions.simulationAdmission, true);
  assert.equal(routeOptions.routeTakeoffTimeoutMs, 90000,
    'only the Grand Prix Route opt-in permits a bounded late native TAKEOFF response');
  assert.equal(new u.context.WebeeBlocksWwiBackend({}, {}).options.routeTakeoffTimeoutMs, undefined,
    'historical Grand Prix U must not inherit the route-only timeout');
  // The actual Windows GUI has served wwi_backend.js at the HTTP 200 URL for
  // activity_contract.js. A backend READY is not proof of an executable AST.
  const wrongAsset = load(variable, catalog);
  wrongAsset.context.WebeeBlocksActivityContract = undefined;
  assert.throws(() => new wrongAsset.context.WebeeBlocksWwiBackend({}, {}),
    error => error.code === 'BLOCKLY_ASSET_MISMATCH' &&
      /activity_contract\.js/.test(error.message),
    'wrong cached JS must refuse backend construction before READY');
  const partialAsset = load(variable, catalog);
  partialAsset.context.WebeeBlocksActivityContract = {execute() {}, applyFieldBounds() {}};
  assert.throws(() => new partialAsset.context.WebeeBlocksWwiBackend({}, {}),
    error => error.code === 'BLOCKLY_ASSET_MISMATCH',
    'incomplete Blockly contract is not a valid loaded module');
  assert.equal(a.context.WebeeBlocksRuntimeOutcome.classify({code: 'TIME_LIMIT'}).state, 'ARRÊTÉ');
  assert.equal(a.context.WebeeBlocksRuntimeOutcome.classify({code: 'TIME_LIMIT'}).detail,
    'Vol interrompu — résultat de mission non confirmé');
  for (const forbidden of ['seed', 'lengths', 'turns', 'gates', 'course', 'route', 'identifier'])
    assert.equal(Object.hasOwn(profile, forbidden), false, 'host-only parameter: ' + forbidden);
  assert.equal(profile.brief.visible, true);
  assert.match(profile.brief.mission, /droite/);
  assert.match(profile.brief.mission, /210 secondes/);

  // The actual .wbb codec must store the stable activity identity only.
  // This is intentionally not a mock of native dialogs or a cross-world GUI test.
  const text = Projects.createStarterText(profile.id);
  const document = Projects.parseProject(text);
  assert.deepEqual(Object.keys(document.activity).sort(), ['id', 'semantics']);
  assert.equal(document.activity.id, profile.id);
  assert.equal(JSON.stringify(document).includes('gp-route-v2-L'), false);
  const options = {
    Blockly: {
      Workspace: class {
        getAllBlocks() { return []; }
        dispose() {}
      },
      serialization: {workspaces: {load(_data, workspace) { workspace.loaded = true; }}}
    },
    profiles: Profiles,
    activitiesDocument: a.context.WebeeBlocksActivities.DOCUMENT,
    blockCatalog: catalog,
    semanticAst: {compileWorkspace() { throw new Error('Crazyflie program must have exactly one top-level sequence'); }},
    activityContract: {preflightWorkspace() {}}
  };
  const checked = Projects.validateProjectText(text, profile, options);
  assert.equal(checked.profile.world, profile.world);
  assert.equal(checked.ast, null, 'an unfinished pupil starter remains editable');
  assert.throws(() => Projects.validateProjectText(text, {...profile, world: 'worlds/grand_prix_u_seed4.wbt'}, options),
    /incompatible with the current Webots world/);
  const injected = JSON.parse(text);
  injected.activity.route = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2';
  assert.throws(() => Projects.parseProject(JSON.stringify(injected)), /unsupported fields/);
  assert.throws(() => Projects.validateProjectText(Projects.createStarterText(u.profile.id), profile, options),
    /exactly once/);
}


/*
 * #826: exercise the real .wbb codec + manager over two host-selected routes,
 * with an in-memory transport. This proves no OS dialog, native Webots scene,
 * pupil AST execution or mission result.
 */
async function proveSameFileAcrossHostRoutes() {
  const catalog = Object.assign({}, Activities.BLOCK_CATALOG);
  const {profile, context} = load(variable, catalog);
  const clone = value => JSON.parse(JSON.stringify(value));
  const empty = () => ({blocks: {languageVersion: 0, blocks: []}});
  class Workspace {
    constructor() { this.state = empty(); }
    clear() { this.state = empty(); }
    getAllBlocks() { return []; } // transport test, not Blockly preflight
    dispose() {}
  }
  const Blockly = {
    Workspace,
    serialization: {workspaces: {
      save(workspace) { return clone(workspace.state); },
      load(state, workspace) { workspace.state = clone(state); }
    }}
  };
  const dependencies = {
    Blockly, profiles: Profiles,
    activitiesDocument: context.WebeeBlocksActivities.DOCUMENT,
    blockCatalog: catalog,
    semanticAst: {
      compileWorkspace() {
        // An unfinished pupil sketch is editable and savable, not successful.
        throw new Error('Crazyflie program must have exactly one top-level sequence');
      }
    },
    activityContract: {
      preflightWorkspace() {},
      applyFieldBounds() {}
    }
  };
  const handle = {name: 'programme-grand-prix.wbb'};
  const writes = [];
  let fileText = null;
  const transport = {
    nativeFileSystemAccess: true,
    async open() { return {handle, name: handle.name, text: fileText, mode: 'test'}; },
    async saveAs(name, text) {
      fileText = text;
      writes.push({operation: 'saveAs', name, handle});
      return {handle, name: handle.name, mode: 'test'};
    },
    async save(target, name, text) {
      assert.equal(target, handle, 'Save must preserve the exact selected handle');
      fileText = text;
      writes.push({operation: 'save', name, handle: target});
      return {handle: target, name: handle.name, mode: 'test'};
    },
    async release() {}
  };
  const makeManager = workspace => Projects.createManager({
    ...dependencies, workspace,
    getProfile() { return profile; },
    setProfile(next) { assert.equal(next.id, profile.id); },
    transport
  });
  const pupilSketch = {blocks: {languageVersion: 0, blocks: [{
    type: 'webeeblocks_v2_move', id: 'pupil-unfinished-move',
    fields: {DIRECTION: 'forward'},
    inputs: {DISTANCE: {shadow: {type: 'math_number', fields: {NUM: 0.3}}}}
  }]}};
  let hostRoute = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2';
  const editingWorkspace = new Workspace();
  editingWorkspace.state = clone(pupilSketch);
  const editing = makeManager(editingWorkspace);
  assert.equal(editing.hasCurrentTarget(), false);
  await editing.saveAs('programme-grand-prix');
  assert.equal(editing.hasCurrentTarget(), true);
  await editing.save();
  assert.deepEqual(writes.map(write => write.operation), ['saveAs', 'save']);
  const originalFile = fileText;
  const parsed = Projects.parseProject(originalFile);
  assert.deepEqual(Object.keys(parsed.activity).sort(), ['id', 'semantics']);
  assert.equal(parsed.activity.id, profile.id);
  assert.deepEqual(parsed.workspace, pupilSketch);
  assert(!originalFile.includes(hostRoute), 'host route leaked into the .wbb');

  // Change only the native host route; Open must consume identical project bytes.
  hostRoute = 'gp-route-v2-L3000-2000-2500-TDG-s5-H3';
  const reopenedWorkspace = new Workspace();
  const reopened = makeManager(reopenedWorkspace);
  await reopened.open();
  assert.equal(reopened.hasCurrentTarget(), true);
  assert.deepEqual(reopenedWorkspace.state, pupilSketch);
  assert.equal(reopened.encodeCurrent(), originalFile);
  await reopened.save();
  assert.equal(fileText, originalFile, 'same-file Save changed an unchanged project');
  assert.deepEqual(writes.map(write => write.operation), ['saveAs', 'save', 'save']);
  assert(!fileText.includes(hostRoute), 'new host route leaked into .wbb on Save');

  // Reopening a historical U file must not silently replace the variable world.
  const historicalProfile = load(historical, catalog).profile;
  fileText = Projects.createStarterText(historicalProfile.id);
  await assert.rejects(() => reopened.open(), /exactly once/);
  assert.deepEqual(reopenedWorkspace.state, pupilSketch);
  assert.equal(reopened.hasCurrentTarget(), true);
  fileText = originalFile;
}


/* #826/#905: a real Runtime-v2 diagnostic must be readable AFTER the
 * interpreter's finish callback; this is a DOM/JS test, not a Webots GUI PASS. */
async function proveRouteTechnicalDiagnostics() {
  const events = new Map();
  const rows = {
    runtimeState: {textContent: 'EXÉCUTION'},
    debugState: {textContent: 'En pause'}
  };
  const context = {
    WebeeBlocksActivities: {BLOCK_CATALOG: Activities.BLOCK_CATALOG, DOCUMENT: Activities.DOCUMENT},
    WebeeBlocksRuntimeOutcome: {classify() { return {state: 'ERREUR'}; }},
    Blockly: {inject() {}},
    WebeeBlocksWwiBackend: function() {},
    addEventListener(name, fn) { events.set(name, fn); },
    document: {getElementById(id) { return rows[id] || null; }}
  };
  context.window = context;
  vm.runInNewContext(variable, context);
  const listener = events.get('webeeblocks-runtime-v2-diagnostic');
  assert.equal(typeof listener, 'function', 'Grand Prix diagnostic listener is missing');
  const flush = () => new Promise(resolve => setImmediate(resolve));

  // Event arrives before generic Runtime-v2 state, and onFinish may overwrite
  // the debug text synchronously. A deferred diagnostic must win only on ERREUR.
  listener({detail: {studentState: 'ERREUR', machineCode: null,
    technicalMessage: 'WWI timeout id=129 command=LAND'}});
  rows.debugState.textContent = 'Observation terminée';
  rows.runtimeState.textContent = 'ERREUR';
  await flush();
  assert.equal(rows.debugState.textContent, 'Diagnostic : WWI timeout id=129 command=LAND');

  rows.debugState.textContent = 'Observation inactive';
  rows.runtimeState.textContent = 'PRÊT';
  listener({detail: {studentState: 'ERREUR', machineCode: 'BACKEND_FAILURE',
    technicalMessage: 'old technical error'}});
  await flush();
  assert.equal(rows.debugState.textContent, 'Observation inactive',
    'a late diagnostic must not contaminate a fresh RESET');

  rows.runtimeState.textContent = 'ARRÊTÉ';
  listener({detail: {studentState: 'ARRÊTÉ', machineCode: 'USER_STOPPED',
    technicalMessage: 'stopped by user'}});
  await flush();
  assert.equal(rows.debugState.textContent, 'Observation inactive',
    'a voluntary stop must not display a technical failure');

  rows.runtimeState.textContent = 'ERREUR';
  listener({detail: {studentState: 'ERREUR', machineCode: 'E\nCODE',
    technicalMessage: '  line 1\n  line 2 '.repeat(50)}});
  await flush();
  assert(rows.debugState.textContent.startsWith('Diagnostic : E CODE — line 1 line 2 '));
  assert(rows.debugState.textContent.length <= 'Diagnostic : '.length + 40 + 3 + 240);
  assert(!rows.debugState.textContent.includes('\n'),
    'diagnostic must remain one bounded visible line');
}


/* Route-specific read-only clock: native observations only, not a local wall timer
 * or an oracle. The same four ordinary Runtime states must remain authoritative. */
async function proveRouteLiveClock() {
  const events = new Map(), timers = new Map();
  let nextInterval = 1, backend = null, reads = 0, nonceCounter = 0;
  const span = {id: null, textContent: '', style: {},
    setAttribute(key, value) { this[key] = value; }};
  const panel = {children: [], style: {}, appendChild(el) {this.children.push(el);}};
  const context = {
    WebeeBlocksActivities: {BLOCK_CATALOG: Activities.BLOCK_CATALOG, DOCUMENT: Activities.DOCUMENT},
    WebeeBlocksRuntimeOutcome: {classify() {return null;}},
    WebeeBlocksActivityContract: {execute() {}, preflightWorkspace() {}, applyFieldBounds() {}},
    Blockly: {inject() {}},
    WebeeBlocksWwiBackend: function () {},
    document: {getElementById(id) {return id === 'observationReadouts' ? panel : null;},
      createElement() {return span;}},
    addEventListener(name, listener) {events.set(name, listener);},
    setInterval(fn, ms) {assert.equal(ms, 1000); const id = nextInterval++;timers.set(id, fn);return id;},
    clearInterval(id) {timers.delete(id);},
    Promise,
    crypto: {getRandomValues(bytes) {bytes.fill(++nonceCounter % 256); return bytes;}}
  };
  context.window = context;
  Object.defineProperty(context, 'runtimeBackend', {get() {return backend;}, set(value) {backend = value;}});
  vm.runInNewContext(variable, context);
  const change = state => events.get('webeeblocks-runtime-v2')({detail: {state}});
  const flush = () => new Promise(resolve => setImmediate(resolve));
  events.get('webeeblocks-ui-ready')();
  assert.equal(span.textContent, '00min 00s / 03min 30s');
  assert.equal(span['aria-live'], 'off');
  assert.equal(panel.children[0], span, 'clock must live in the fixed observation readouts');
  assert(html.includes('id="observationReadouts"'), 'fixed observation readout container missing');
  change('EXÉCUTION');
  assert.equal(timers.size, 1);
  await flush();
  assert.equal(span.textContent, '00min 00s / 03min 30s',
    'the zero placeholder must not advance before a native reading');
  backend = {ready: true, readElapsedTime() {reads++; return Promise.resolve(9.05);}};
  [...timers.values()][0]();await flush();
  assert.equal(reads, 1);
  assert.equal(span.textContent, '00min 09s / 03min 30s');
  backend.readElapsedTime = () => {reads++; return Promise.resolve(12.99);};
  [...timers.values()][0]();await flush();
  assert.equal(span.textContent, '00min 12s / 03min 30s');
  let reply;
  backend.readElapsedTime = () => {reads++; return new Promise(resolve => {reply = resolve;});};
  [...timers.values()][0]();await flush();
  [...timers.values()][0]();await flush();
  assert.equal(reads, 3, 'no overlapping ELAPSED observations');
  change('MISSION RÉUSSIE');
  reply(99.9);await flush();
  assert.equal(span.textContent, '00min 12s / 03min 30s',
    'a late observation cannot update a terminal state');
  assert.equal(timers.size, 0);
  change('PRÊT');
  assert.equal(span.textContent, '00min 00s / 03min 30s');
  backend.readElapsedTime = () => {reads++;return Promise.resolve(20);};
  change('EXÉCUTION');await flush();
  assert.equal(span.textContent, '00min 20s / 03min 30s');
  change('RÉINITIALISATION');
  assert.equal(span.textContent, '00min 00s / 03min 30s');
  assert.equal(timers.size, 0);
  change('EXÉCUTION');await flush();
  backend.readElapsedTime = () => Promise.reject(Object.assign(new Error('unavailable'), {code:'TIME_UNAVAILABLE'}));
  [...timers.values()][0]();await flush();
  assert.equal(span.textContent, '00min 20s / 03min 30s');
  change('ARRÊTÉ');
  assert.equal(timers.size, 0);
  assert.equal(panel.children.length, 1, 'clock must not duplicate after reset');
  // A route-only, browser-nonce-bound native event must update each simulated
  // second independently of the 1000 ms wall fallback. No other attempt or
  // older STOP/RESET nonce can update the latest mission display.
  const sent = [];
  backend = {ready: true, robotWindow: {send(message) {sent.push(message);}},
    readElapsedTime() {return Promise.reject(new Error('not-admitted'));}};
  change('PRÊT');
  change('EXÉCUTION');await flush();
  const subscription = sent[sent.length - 1];
  assert(/^GP_ROUTE_CLOCK_V1 SUBSCRIBE nonce=[0-9a-f]{32}$/.test(subscription),
    'clock subscription missing unpredictable session nonce');
  const nonce = subscription.slice(-32);
  const notify = raw => events.get('webeeblocks-route-native-clock')({detail: {raw}});
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=2');
  assert.equal(span.textContent, '00min 00s / 03min 30s',
    'unbound native clock event accepted');
  notify('GP_ROUTE_CLOCK_V1 ACK nonce=' + nonce + ' attempt=7');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=2');
  assert.equal(span.textContent, '00min 02s / 03min 30s',
    'native simulated second not displayed promptly');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=8 seconds=3');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=ffffffffffffffffffffffffffffffff attempt=7 seconds=3');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=1');
  assert.equal(span.textContent, '00min 02s / 03min 30s',
    'stale/cross-attempt or regressing clock event accepted');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=60');
  assert.equal(span.textContent, '01min 00s / 03min 30s',
    'simulated minute rollover did not reach pinned clock');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=210');
  assert.equal(span.textContent, '03min 30s / 03min 30s',
    'exact native 210 s boundary did not reach pinned clock');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=211');
  assert.equal(span.textContent, '03min 30s / 03min 30s',
    'out-of-bounds time from native clock accepted');
  change('PRÊT');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=61');
  assert.equal(span.textContent, '00min 00s / 03min 30s',
    'old native clock after RESET changed current display');
  change('EXÉCUTION');await flush();
  assert.notEqual(sent[sent.length - 1], subscription,
    'new attempt reused an earlier session nonce');
  notify('GP_ROUTE_CLOCK_V1 ACK nonce=' + nonce + ' attempt=7');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + nonce + ' attempt=7 seconds=62');
  assert.equal(span.textContent, '00min 00s / 03min 30s',
    'old native ACK/TICK contaminated the new attempt');
  change('ARRÊTÉ');
  // Adversarial race: a fallback ELAPSED request starts before the native ACK.
  // Its late (but valid) time must not overwrite the authoritative TICK once
  // the native stream has taken over the display for the same run.
  let releaseFallback = null;
  backend = {ready:true, robotWindow:{send(message) {sent.push(message);}},
    readElapsedTime() {return new Promise(resolve => {releaseFallback = resolve;});}};
  change('PRÊT');
  change('EXÉCUTION');await flush();
  assert.equal(typeof releaseFallback, 'function', 'missing in-flight ELAPSED request');
  const lastSubscribe = sent[sent.length - 1];
  assert(/^GP_ROUTE_CLOCK_V1 SUBSCRIBE nonce=[0-9a-f]{32}$/.test(lastSubscribe));
  const lastNonce = lastSubscribe.slice(-32);
  notify('GP_ROUTE_CLOCK_V1 ACK nonce=' + lastNonce + ' attempt=9');
  notify('GP_ROUTE_CLOCK_V1 TICK nonce=' + lastNonce + ' attempt=9 seconds=10');
  assert.equal(span.textContent, '00min 10s / 03min 30s',
    'bound native simulated-second TICK was not displayed');
  releaseFallback(120.75);await flush();
  assert.equal(span.textContent, '00min 10s / 03min 30s',
    'in-flight wall-polled fallback overwrote an already bound native tick');
  change('ARRÊTÉ');
  console.log('PASS native route clock: simulated-second pushes, 59→60, nonce/attempt binding, STOP/RESET, late fallback exclusion, no wall extrapolation');
}


async function proveRouteOnlyNativePauseBrowser() {
  // Browser-only adversarial test of the exact opt-in hooks. No flight source,
  // physics clock or native Webots success is inferred from these fakes.
  const sent = [], original = {create(_workspace, callbacks) {return callbacks;}};
  const catalog = Object.assign({}, Activities.BLOCK_CATALOG);
  const context = {
    WebeeBlocksActivities:{BLOCK_CATALOG:catalog,DOCUMENT:Activities.DOCUMENT},
    WebeeBlocksRuntimeOutcome:{classify:()=>null},
    WebeeBlocksActivityContract:{execute(){},preflightWorkspace(){},applyFieldBounds(){}},
    Blockly:{inject(_element,options){return options;}},
    WebeeBlocksWwiBackend:function(_rw,_options) {
      this.ready=true;
      this.robotWindow={send(message){sent.push(message);}};
      this.stopSimulation=async function(){sent.push('NATIVE_STOP');};
      this.handleMessage=function(){return false;};
    },
    WebeeBlocksExecutionObserver:original,
    setTimeout,clearTimeout,setInterval,clearInterval
  };
  context.window=context;
  vm.runInNewContext(variable,context);
  let currentNonce='a'.repeat(32),currentAttempt=4;
  context.WebeeBlocksRouteClockBinding=()=>({nonce:currentNonce,attempt:currentAttempt});
  const backend=new context.WebeeBlocksWwiBackend({},{});
  context.runtimeBackend=backend;
  const observer=context.WebeeBlocksExecutionObserver.create({},{onBegin(){},onFinish(){}});
  observer.onBegin({enabled:true});
  const pause=observer.beforePause();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.pop(),
    'GP_ROUTE_PAUSE_V1 PAUSE nonce='+currentNonce+' attempt=4 seq=1');
  let resolved=false;pause.then(()=>{resolved=true;});
  backend.handleMessage('GP_ROUTE_PAUSE_V1 PAUSED nonce='+currentNonce+
    ' attempt=4 seq=2');
  await Promise.resolve();
  assert.equal(resolved,false,'wrong sequence released the paused browser');
  backend.handleMessage('GP_ROUTE_PAUSE_V1 PAUSED nonce='+currentNonce+
    ' attempt=4 seq=1');
  await pause;
  const resume=observer.beforeResume();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.pop(),
    'GP_ROUTE_PAUSE_V1 RESUME nonce='+currentNonce+' attempt=4 seq=1');
  backend.handleMessage('GP_ROUTE_PAUSE_V1 RESUMED nonce='+currentNonce+
    ' attempt=5 seq=1');
  let resumed=false;resume.then(()=>{resumed=true;});
  await Promise.resolve();
  assert.equal(resumed,false,'another attempt released the browser');
  backend.handleMessage('GP_ROUTE_PAUSE_V1 RESUMED nonce='+currentNonce+
    ' attempt=4 seq=1');
  await resume;
  observer.onFinish();
  currentNonce='b'.repeat(32);currentAttempt=5;
  observer.onBegin({enabled:true});
  const next=observer.beforePause();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.pop(),
    'GP_ROUTE_PAUSE_V1 PAUSE nonce='+currentNonce+' attempt=5 seq=1');
  backend.handleMessage('GP_ROUTE_PAUSE_V1 PAUSED nonce='+'a'.repeat(32)+
    ' attempt=4 seq=1');
  let stale=false;next.then(()=>{stale=true;},()=>{});
  await Promise.resolve();
  assert.equal(stale,false,'stale ACK crossed the RESET/browser epoch');
  observer.onFinish();
  await assert.rejects(next,/PAUSE_NATIVE_CANCELLED/);
  observer.onBegin({enabled:false});
  await assert.rejects(observer.beforePause(),/PAUSE_NATIVE_NOT_READY/);
  observer.onFinish();
  console.log('PASS route-only browser native PAUSE: ACK fences, wrong seq, old attempt, STOP cancellation and no opt-in');
}

async function proveBoundedRouteTakeoffReply() {
  // Native R2025a executed TAKEOFF for 52.319 s wall-clock while the default
  // 35 s pending promise expired. Test only the explicit TAKEOFF wall budget:
  // native 210 s simulation safety, oracle, STOP and RESET remain independent.
  const sent=[];
  const backend=new WwiBackend({send: message=>sent.push(message)}, {
    timeoutMs:35000, routeTakeoffTimeoutMs:90000,
    simulationAdmission:true, simulationStop:true, simulationReset:true
  });
  backend.ready=true;
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  const first=backend.takeoff(0.4);
  await flush();
  assert.match(sent[0], / REQUEST 1 ADMISSION$/);
  assert.equal(backend.pending[1].timer._idleTimeout,35000,
    'route admission must not consume extended TAKEOFF budget');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 VALUE 1');
  await flush();
  assert.match(sent[1], / REQUEST 2 TAKEOFF 0\.40000000000000002$/);
  assert.equal(backend.pending[2].timer._idleTimeout,90000,
    'only the native effect ACK waits for the measured slow Webots takeoff');

  const cancelled=assert.rejects(first, error=>error && error.code==='RESET_CANCELLED');
  const reset=backend.resetSimulation();
  await cancelled;
  assert.match(sent[2], / REQUEST 3 RESET$/);
  assert.equal(backend.pending[3].timer._idleTimeout,35000,
    'RESET safety postconditions must retain the original timeout');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK');
  assert(backend.pending[3], 'stale TAKEOFF ACK unexpectedly finalized RESET');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK');
  await reset;

  const second=backend.takeoff(0.4);
  await flush();
  assert.match(sent[3], / REQUEST 4 ADMISSION$/);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 VALUE 1');
  await flush();
  assert.match(sent[4], / REQUEST 5 TAKEOFF /);
  assert.equal(backend.pending[5].timer._idleTimeout,90000);
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 5 OK');
  await second;
  assert.equal(sent.filter(x=>/ TAKEOFF /.test(x)).length,2,
    'takeoff must be sent exactly once for each separately authorized attempt');

  const stop=backend.stopSimulation();
  assert.match(sent[5], / REQUEST 6 STOP$/);
  assert.equal(backend.pending[6].timer._idleTimeout,35000,
    'STOP must not inherit the route TAKEOFF response budget');
  backend.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 6 OK');
  await stop;

  for (const opts of [
    {timeoutMs:35000,routeTakeoffTimeoutMs:90000},
    {timeoutMs:35000,simulationAdmission:false,routeTakeoffTimeoutMs:90000},
    {timeoutMs:35000,simulationAdmission:true,routeTakeoffTimeoutMs:90001},
    {timeoutMs:35000,simulationAdmission:true,routeTakeoffTimeoutMs:Infinity}
  ]) {
    const messages=[];
    const generic=new WwiBackend({send:message=>messages.push(message)},opts);
    const flight=generic.takeoff(.4);
    assert.equal(generic.pending[1].timer._idleTimeout,35000,
      'generic/physical/noncanonical backend unexpectedly received extended timeout');
    assert.match(messages[0], / REQUEST 1 TAKEOFF /);
    generic.handleMessage('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK');
    await flight;
  }
  console.log('PASS route-only 90s TAKEOFF ACK: exact admission, stale/reset rejection, STOP 35s, no physical/generic opt-in, no replay');
}

run(false);
run(true);
for (const id of ['projectActivity', 'projectOpen', 'projectSave', 'projectSaveAs',
  'stepMode', 'stepNext', 'stepContinue', 'resetSimulation']) {
  assert(html.includes('id="' + id + '"'), 'UI element missing: ' + id);
}
assert(html.includes('src="setup.js"'));
assert(html.includes('../blockly_v2/main.js'));
assert(!html.includes('grand_prix_u'));
Promise.all([proveSameFileAcrossHostRoutes(), proveRouteTechnicalDiagnostics(), proveRouteLiveClock(), proveRouteOnlyNativePauseBrowser(), proveBoundedRouteTakeoffReply()]).then(() => {
  console.log('PASS isolated Grand Prix variable profile: stable .wbb world, generic blocks, unfinished same-file Save/Open across host routes');
}).catch(error => { console.error(error); process.exitCode = 1; });
