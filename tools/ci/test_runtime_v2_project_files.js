'use strict';

const assert = require('assert');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const Blockly = require(path.join(ROOT, 'plugins/robot_windows/blockly_v2/node_modules/blockly'));
const Profiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js'));
const Activities = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activities.js'));
const SemanticAst = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/semantic_ast.js'));
const ActivityContract = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/activity_contract.js'));
const ProjectFiles = require(path.join(ROOT, 'plugins/robot_windows/blockly/webeeblocks/project_files.js'));

Blockly.defineBlocksWithJsonArray([
  {type:'webeeblocks_v2_takeoff', message0:'takeoff %1', args0:[{type:'field_number',name:'HEIGHT',value:1,min:0.2,max:1.5,precision:0.1}], previousStatement:null,nextStatement:null},
  {type:'webeeblocks_v2_move', message0:'move %1 %2', args0:[{type:'field_dropdown',name:'DIRECTION',options:[['forward','forward'],['left','left']]},{type:'field_number',name:'DISTANCE',value:0.3,min:0.1,max:2,precision:0.1}], previousStatement:null,nextStatement:null},
  {type:'webeeblocks_v2_land', message0:'land', previousStatement:null}
]);

function buildWorkspace(distance) {
  const workspace = new Blockly.Workspace();
  const takeoff = workspace.newBlock('webeeblocks_v2_takeoff');
  const move = workspace.newBlock('webeeblocks_v2_move');
  const land = workspace.newBlock('webeeblocks_v2_land');
  takeoff.setFieldValue('1', 'HEIGHT');
  move.setFieldValue('forward', 'DIRECTION');
  move.setFieldValue(String(distance), 'DISTANCE');
  takeoff.nextConnection.connect(move.previousConnection);
  move.nextConnection.connect(land.previousConnection);
  return workspace;
}

function ast(workspace, profile) {
  ActivityContract.preflightWorkspace(profile, workspace);
  const value = SemanticAst.compileWorkspace(workspace);
  ActivityContract.preflightAst(profile, value);
  return value;
}

function memoryTransport() {
  const state = {writes:[], openText:null, currentText:null};
  const handle = {name:'eleve.wbb', token:'same-target'};
  return {
    state,
    nativeFileSystemAccess:true,
    async open() {
      if (state.openText === null) throw new Error('no open fixture');
      return {handle, name:handle.name, text:state.openText, mode:'test'};
    },
    async saveAs(name, text) {
      state.currentText = text;
      state.writes.push({kind:'saveAs',name,text,handle});
      return {handle,name,mode:'test'};
    },
    async save(target, name, text) {
      assert.strictEqual(target, handle, 'Save must reuse chosen file handle');
      state.currentText = text;
      state.writes.push({kind:'save',name,text,handle:target});
      return {handle:target,name,mode:'test'};
    }
  };
}

function managerFor(workspace, profileRef, transport) {
  return ProjectFiles.createManager({
    Blockly,
    profiles:Profiles,
    activitiesDocument:Activities.DOCUMENT,
    blockCatalog:Activities.BLOCK_CATALOG,
    semanticAst:SemanticAst,
    activityContract:ActivityContract,
    workspace,
    getProfile:() => profileRef.value,
    setProfile:profile => { profileRef.value = profile; },
    transport
  });
}

async function expectRejectedWithoutMutation(manager, transport, text, workspace, profileRef, label) {
  const beforeAst = ast(workspace, profileRef.value);
  const beforeState = Blockly.serialization.workspaces.save(workspace);
  transport.state.openText = text;
  let rejected = false;
  try { await manager.open(); } catch (error) { rejected = true; }
  assert(rejected, label + ' must reject');
  assert.deepStrictEqual(ast(workspace, profileRef.value), beforeAst, label + ' changed AST');
  assert.deepStrictEqual(Blockly.serialization.workspaces.save(workspace), beforeState, label + ' changed workspace');
}

function validatePickerOptions(options) {
  assert(options && Array.isArray(options.types) && options.types.length > 0, 'picker types missing');
  for (const type of options.types) {
    for (const [mime, extensions] of Object.entries(type.accept || {})) {
      assert(/^[^/]+\/[^/]+$/.test(mime), 'invalid picker MIME type');
      for (const extension of extensions) {
        // Chrome rejects overlong native suffixes before any WebeeBlocks
        // interpretation. Keep this check first so the historical
        // `.webeeblocks.json` regression is causally represented, then still
        // validate the syntax of all suffixes that fit the native limit.
        assert(Array.from(extension).length <= 16, 'picker extension exceeds native limit');
        assert(/^\.[A-Za-z0-9]+$/.test(extension), 'invalid picker extension ' + extension);
      }
    }
  }
}

function fakeNativeBrowser() {
  const state = {options:[], writes:0, bytes:'', nextOpenName:'eleve.wbb'};
  const handle = {
    name:'eleve.wbb',
    async createWritable() {
      return {
        async write(text) { state.bytes = String(text); state.writes += 1; },
        async close() {}
      };
    },
    async getFile() { return {name:state.nextOpenName, text:async () => state.bytes}; }
  };
  const browserWindow = {
    async showSaveFilePicker(options) {
      validatePickerOptions(options);
      state.options.push({kind:'save', options});
      return handle;
    },
    async showOpenFilePicker(options) {
      validatePickerOptions(options);
      state.options.push({kind:'open', options});
      return [handle];
    }
  };
  return {state, handle, browserWindow};
}

async function exerciseBrowserBoundary() {
  assert.throws(() => validatePickerOptions({
    types:[{accept:{'application/json':['.webeeblocks.json']}}]
  }), /native limit/, 'historical compound suffix must be rejected');

  const fake = fakeNativeBrowser();
  const transport = ProjectFiles.createBrowserTransport(fake.browserWindow, {});
  assert.strictEqual(transport.nativeFileSystemAccess, true);
  const saved = await transport.saveAs('eleve.webeeblocks.json', '{"ok":1}');
  assert.strictEqual(saved.name, 'eleve.wbb');
  assert.strictEqual(fake.state.writes, 1);
  const saveOptions = fake.state.options[0].options;
  assert.strictEqual(saveOptions.suggestedName, 'eleve.wbb');
  assert.deepStrictEqual(saveOptions.types[0].accept, {'application/json':['.wbb']});

  for (const name of ['projet.wbb','ancien.webeeblocks.json','legacy.json']) {
    fake.state.nextOpenName = name;
    const opened = await transport.open();
    assert.strictEqual(opened.name, name, 'opened OS filename must be preserved exactly');
  }
  const openOptions = fake.state.options.find(entry => entry.kind === 'open').options;
  assert.deepStrictEqual(openOptions.types[0].accept, {'application/json':['.wbb','.json']});
  await transport.save(fake.handle, 'eleve.wbb', '{"ok":2}');
  assert.strictEqual(fake.state.writes, 2, 'Save must write the selected handle');

  const unavailable = ProjectFiles.createBrowserTransport({}, {});
  assert.strictEqual(unavailable.nativeFileSystemAccess, false);
  await assert.rejects(unavailable.open(), /use Google Chrome/);
  await assert.rejects(unavailable.saveAs('x', '{}'), /use Google Chrome/);
  assert(!ProjectFiles.createBrowserTransport.toString().includes('Blob'), 'Blob fallback must not exist');
  assert(!ProjectFiles.createBrowserTransport.toString().includes("createElement('input')"), 'input upload fallback must not exist');
}

(async function() {
  await exerciseBrowserBoundary();
  assert.strictEqual(ProjectFiles.EXTENSION, '.wbb');
  assert.strictEqual(ProjectFiles.normalizeName('eleve'), 'eleve.wbb');
  assert.strictEqual(ProjectFiles.normalizeName('eleve.webeeblocks.json'), 'eleve.wbb');
  assert.strictEqual(ProjectFiles.normalizeName('eleve.json'), 'eleve.wbb');

  const profileRef = {value:Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG)};
  const liveWorkspace = buildWorkspace(0.3);
  const transport = memoryTransport();
  const manager = managerFor(liveWorkspace, profileRef, transport);

  const initialAst = ast(liveWorkspace, profileRef.value);
  assert.strictEqual(manager.hasCurrentTarget(), false);
  await assert.rejects(manager.save(), /no current file/);
  assert.strictEqual(transport.state.writes.length, 0, 'Save without target reached transport');
  const saved = await manager.saveAs('eleve');
  assert.strictEqual(manager.hasCurrentTarget(), true);
  assert.strictEqual(saved.name, 'eleve.wbb');
  assert.strictEqual(transport.state.writes.length, 1);
  const project = JSON.parse(transport.state.currentText);
  assert.deepStrictEqual(Object.keys(project).sort(), ['activity','format','version','workspace']);
  assert.deepStrictEqual(Object.keys(project.activity).sort(), ['id','semantics']);
  assert.strictEqual(project.format, 'webeeblocks-project');
  assert.strictEqual(project.version, 1);
  assert.strictEqual(project.activity.id, 'reactive-obstacle-v2');
  assert.strictEqual(project.activity.semantics, 'webeeblocks-ast-v1');
  ['identity','attempt','result','score','debug','progress','history'].forEach(word => {
    assert(!transport.state.currentText.toLowerCase().includes('"' + word), 'forbidden project data: ' + word);
  });

  // Editing/compiling is deliberately persistence-inert.
  liveWorkspace.getBlocksByType('webeeblocks_v2_move', false)[0].setFieldValue('0.8','DISTANCE');
  ast(liveWorkspace, profileRef.value);
  assert.strictEqual(transport.state.writes.length, 1, 'workspace edit caused implicit persistence write');

  // Re-open the explicit Save As bytes and recover the exact full AST.
  transport.state.openText = transport.state.currentText;
  await manager.open();
  assert.deepStrictEqual(ast(liveWorkspace, profileRef.value), initialAst, 'round-trip AST differs');

  // Explicit Save updates the same chosen target; no hidden version/history file exists.
  liveWorkspace.getBlocksByType('webeeblocks_v2_move', false)[0].setFieldValue('0.7','DISTANCE');
  const editedAst = ast(liveWorkspace, profileRef.value);
  const writesBeforeSave = transport.state.writes.length;
  await manager.save();
  assert.strictEqual(transport.state.writes.length, writesBeforeSave + 1, 'explicit Save did not write once');
  assert.strictEqual(transport.state.writes.at(-1).kind, 'save');
  transport.state.openText = transport.state.currentText;
  liveWorkspace.getBlocksByType('webeeblocks_v2_move', false)[0].setFieldValue('0.4','DISTANCE');
  await manager.open();
  assert.deepStrictEqual(ast(liveWorkspace, profileRef.value), editedAst, 'Save bytes did not restore edited AST');

  const validText = manager.encodeCurrent();
  await expectRejectedWithoutMutation(manager, transport, '{bad json', liveWorkspace, profileRef, 'malformed JSON');
  const unknownVersion = JSON.parse(validText); unknownVersion.version = 999;
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(unknownVersion), liveWorkspace, profileRef, 'unknown version');
  const unknownActivity = JSON.parse(validText); unknownActivity.activity.id = 'unknown-profile';
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(unknownActivity), liveWorkspace, profileRef, 'unknown activity');
  const extraHistory = JSON.parse(validText); extraHistory.history = [{score:1}];
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(extraHistory), liveWorkspace, profileRef, 'unsupported history field');
  const invalidWorkspace = JSON.parse(validText); invalidWorkspace.workspace = {blocks:{languageVersion:0,blocks:[{type:'does_not_exist'}]}};
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(invalidWorkspace), liveWorkspace, profileRef, 'invalid workspace');
  const injectedProfile = Profiles.resolveById(Activities.DOCUMENT, 'progression-sequence-v1', Activities.BLOCK_CATALOG);
  const injected = {
    format:'webeeblocks-project',
    version:1,
    activity:{id:injectedProfile.id,semantics:'webeeblocks-ast-v1'},
    workspace:{blocks:{languageVersion:0,blocks:[{type:'webeeblocks_v2_move',fields:{DIRECTION:'right',DISTANCE:0.3}}]}}
  };
  await expectRejectedWithoutMutation(manager, transport, JSON.stringify(injected), liveWorkspace, profileRef, 'hidden dropdown injection');
  assert.strictEqual(transport.state.writes.length, writesBeforeSave + 1, 'failed opens caused persistence writes');

  // A student must be able to save unfinished work. It is a valid project even
  // though it is not yet a valid executable flight AST.
  const incompleteProfile = {value:Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG)};
  const incomplete = new Blockly.Workspace();
  const takeoffOnly = incomplete.newBlock('webeeblocks_v2_takeoff');
  takeoffOnly.setFieldValue('0.8', 'HEIGHT');
  const incompleteTransport = memoryTransport();
  const incompleteManager = managerFor(incomplete, incompleteProfile, incompleteTransport);
  await incompleteManager.saveAs('en-cours');
  assert.strictEqual(incompleteTransport.state.writes.length, 1, 'incomplete project was not explicitly saved');
  const incompleteBytes = incompleteTransport.state.currentText;
  incomplete.clear();
  incompleteTransport.state.openText = incompleteBytes;
  const reopenedIncomplete = await incompleteManager.open();
  assert.strictEqual(reopenedIncomplete.ast, null, 'incomplete project unexpectedly compiled as executable AST');
  assert.strictEqual(incomplete.getBlocksByType('webeeblocks_v2_takeoff', false).length, 1, 'incomplete workspace was not restored');
  assert.strictEqual(incompleteTransport.state.writes.length, 1, 'opening incomplete project caused a write');

  const fs = require('fs');
  const uiSource = fs.readFileSync(path.join(ROOT, 'plugins/robot_windows/blockly_v2/project_ui.js'), 'utf8');
  assert(uiSource.includes("error.name === 'AbortError'"), 'UI must treat native cancellation neutrally');
  assert(uiSource.includes('!manager.hasCurrentTarget()'), 'UI must disable Save without a current handle');
  assert(uiSource.includes('utilisez Google Chrome'), 'unsupported-browser message must be explicit');
  assert(!uiSource.includes('Nouvelle copie'), 'UI must not advertise download copies');
  console.log('PASS project-files: Chrome .wbb/options/same-handle/state/fail-closed/profile-field-injection/no-fallback/no-autosave');
})().catch(error => { console.error(error); process.exit(1); });
