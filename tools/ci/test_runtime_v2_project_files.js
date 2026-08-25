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
  const handle = {name:'eleve.webeeblocks.json', token:'same-target'};
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
  options.types.forEach(type => {
    Object.entries(type.accept || {}).forEach(([mime, extensions]) => {
      assert(/^[^/]+\/[^/]+$/.test(mime), 'invalid picker MIME type');
      extensions.forEach(extension => {
        assert(extension.startsWith('.') && extension.length > 1, 'picker extension must start with a dot');
        assert(Array.from(extension).length <= 16, 'picker extension exceeds the native 16-code-point limit');
        assert(!/[\\/:*?"<>|]/.test(extension.slice(1)), 'picker extension contains invalid suffix characters');
      });
    });
  });
}

function fakeBrowser(options = {}) {
  const state = {downloads:[], revoked:[], revokeDelays:[], removed:0, nativeOptions:[], writes:0};
  const handle = {
    name:'eleve.webeeblocks.json',
    async createWritable() {
      return {
        async write(text) { state.writes += 1; state.nativeBytes = String(text); },
        async close() {}
      };
    },
    async getFile() {
      return {name:this.name, text:async () => state.nativeBytes || '{"native":true}'};
    }
  };
  const browserWindow = {
    Blob: class {
      constructor(parts, blobOptions) { this.parts = parts; this.type = blobOptions && blobOptions.type; }
    },
    URL: {
      createObjectURL(blob) { state.blob = blob; return 'blob:webeeblocks-test'; },
      revokeObjectURL(url) { state.revoked.push(url); }
    },
    setTimeout(callback, delay) {
      state.revokeDelays.push(delay);
      callback();
    }
  };
  if (options.native) {
    browserWindow.showSaveFilePicker = async picker => {
      state.nativeOptions.push({kind:'save', picker});
      validatePickerOptions(picker);
      return handle;
    };
    browserWindow.showOpenFilePicker = async picker => {
      state.nativeOptions.push({kind:'open', picker});
      validatePickerOptions(picker);
      return [handle];
    };
  }
  const documentObject = {
    body:{appendChild() {}},
    createElement(tag) {
      const listeners = {};
      const element = {
        tagName:tag.toUpperCase(),
        style:{},
        files:null,
        addEventListener(name, callback) { listeners[name] = callback; },
        remove() { state.removed += 1; },
        click() {
          if (tag === 'a') {
            state.downloads.push({name:this.download, href:this.href});
            return;
          }
          if (options.cancelUpload) {
            listeners.cancel();
            return;
          }
          this.files = [{
            name:'ouvert.webeeblocks.json',
            text:async () => options.openText || '{"fallback":true}'
          }];
          listeners.change();
        }
      };
      return element;
    }
  };
  return {state, handle, browserWindow, documentObject};
}

async function exerciseBrowserTransports() {
  assert.throws(() => validatePickerOptions({
    types:[{accept:{'application/json':['.webeeblocks.json']}}]
  }), /16-code-point/, 'old compound suffix must reproduce the native browser rejection');

  const native = fakeBrowser({native:true});
  const nativeTransport = ProjectFiles.createBrowserTransport(native.browserWindow, native.documentObject);
  assert.strictEqual(nativeTransport.nativeFileSystemAccess, true);
  const nativeSave = await nativeTransport.saveAs('eleve', '{"native":1}');
  assert.strictEqual(nativeSave.mode, 'native');
  const saveOptions = native.state.nativeOptions.find(entry => entry.kind === 'save').picker;
  assert.strictEqual(saveOptions.suggestedName, 'eleve.webeeblocks.json');
  assert.deepStrictEqual(saveOptions.types[0].accept, {'application/json':['.json']});
  await nativeTransport.open();
  assert.strictEqual(native.state.nativeOptions.length, 2, 'both native pickers must inspect the real options');
  await nativeTransport.save(native.handle, 'eleve.webeeblocks.json', '{"native":2}');
  assert.strictEqual(native.state.writes, 2, 'native Save must reuse and write the selected handle');

  const fallback = fakeBrowser({openText:'{"fallback":1}'});
  const fallbackTransport = ProjectFiles.createBrowserTransport(fallback.browserWindow, fallback.documentObject);
  assert.strictEqual(fallbackTransport.nativeFileSystemAccess, false);
  const opened = await fallbackTransport.open();
  assert.strictEqual(opened.mode, 'upload');
  assert.strictEqual(opened.name, 'ouvert.webeeblocks.json');
  assert.strictEqual(opened.text, '{"fallback":1}');
  const fallbackSaveAs = await fallbackTransport.saveAs('eleve', '{"fallback":2}');
  const fallbackSave = await fallbackTransport.save(null, fallbackSaveAs.name, '{"fallback":3}');
  assert.strictEqual(fallbackSaveAs.mode, 'download-copy');
  assert.strictEqual(fallbackSave.mode, 'download-copy');
  assert.deepStrictEqual(fallback.state.downloads.map(item => item.name),
    ['eleve.webeeblocks.json','eleve.webeeblocks.json']);
  assert.strictEqual(fallback.state.blob.type, 'application/json');
  assert(fallback.state.revokeDelays.every(delay => delay >= 1000),
    'fallback blob URL must not be revoked on the next tick');

  const cancelled = fakeBrowser({cancelUpload:true});
  const cancelledTransport = ProjectFiles.createBrowserTransport(cancelled.browserWindow, cancelled.documentObject);
  await assert.rejects(cancelledTransport.open(), /open cancelled/);
  assert.strictEqual(cancelled.state.removed, 1, 'cancelled input must be cleaned up');
}

(async function() {
  await exerciseBrowserTransports();

  const profileRef = {value:Profiles.resolveById(Activities.DOCUMENT, 'reactive-obstacle-v2', Activities.BLOCK_CATALOG)};
  const liveWorkspace = buildWorkspace(0.3);
  const transport = memoryTransport();
  const manager = managerFor(liveWorkspace, profileRef, transport);

  const initialAst = ast(liveWorkspace, profileRef.value);
  const saved = await manager.saveAs('eleve');
  assert.strictEqual(saved.name, 'eleve.webeeblocks.json');
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

  console.log('PASS project-files: explicit round-trip/save/fail-closed/no-autosave/incomplete-work');
})().catch(error => { console.error(error); process.exit(1); });
