'use strict';

(function() {
  const PROFILE_ID = 'reactive-obstacle-v2';
  let sequence = 0;
  let reportChain = Promise.resolve();

  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === 'object') {
      const result = {};
      Object.keys(value).sort().forEach(key => { result[key] = canonical(value[key]); });
      return result;
    }
    return value;
  }

  function sameJson(left, right) {
    return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
  }

  function report(event, detail) {
    const payload = {seq: sequence++, event, detail: detail === undefined ? null : detail, wall_ms: Date.now()};
    reportChain = reportChain.then(() => fetch('http://127.0.0.1:8765/event', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    }));
    return reportChain;
  }

  function toolboxFromProfile(profile) {
    return {kind: 'flyoutToolbox', contents: profile.toolbox.map(type => ({kind: 'block', type}))};
  }

  async function main() {
    document.getElementById('status').textContent = 'PAGE_LOADED';
    await report('PAGE_LOADED', {href: location.href, origin: location.origin});

    if (!window.Blockly || Blockly.VERSION !== '13.2.1')
      throw new Error(`unexpected Blockly version: ${window.Blockly && Blockly.VERSION}`);
    if (!window.WebeeBlocksInterpreter || !window.WebeeBlocksWwiBackend)
      throw new Error('Runtime v2 interpreter/WWI backend missing');

    await report('BLOCKLY_INITIALIZED', {version: Blockly.VERSION});
    const profile = WebeeBlocksActivityProfiles.resolveById(
      WebeeBlocksActivities.DOCUMENT,
      PROFILE_ID,
      WebeeBlocksActivities.BLOCK_CATALOG
    );
    const workspace = Blockly.inject('blocklyDiv', {
      toolbox: toolboxFromProfile(profile),
      scrollbars: true,
      sounds: false,
      media: 'vendor/media/'
    });
    WebeeBlocksActivityContract.applyFieldBounds(profile, workspace);
    await report('PROFILE_APPLIED', {profile: profile.id});

    const fixture = window.WebeeBlocksModernBlocklyFixture;
    Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(fixture.xml), workspace);
    WebeeBlocksActivityContract.preflightWorkspace(profile, workspace);
    WebeeBlocksActivityContract.applyFieldBounds(profile, workspace);
    const ast = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    const facts = WebeeBlocksActivityContract.preflightAst(profile, ast);
    if (!sameJson(ast, fixture.expectedAst))
      throw new Error(`AST mismatch: actual=${JSON.stringify(ast)} expected=${JSON.stringify(fixture.expectedAst)}`);
    await report('AST_EQUIVALENT', {ast});

    const module = await import('./RobotWindow.js');
    const robotWindow = new module.default();
    const backend = new WebeeBlocksWwiBackend(robotWindow, {timeoutMs: 35000});
    const originalSend = robotWindow.send.bind(robotWindow);
    robotWindow.send = function(message) {
      report('WWI_TX', {message});
      return originalSend(message);
    };
    robotWindow.receive = function(message) {
      report('WWI_RX', {message});
      backend.handleMessage(message);
    };
    WebeeBlocksActivityContract.preflightBackend(profile, facts, backend);
    await report('WWI_BOUND', {capabilities: backend.capabilities});

    document.getElementById('status').textContent = 'RUNNING';
    await report('RUN_STARTED', null);
    await WebeeBlocksInterpreter.run(ast, backend, {maxSteps: 1000});
    document.getElementById('status').textContent = 'DONE';
    await report('RUN_DONE', null);
    await reportChain;
    console.log('WEBEEBLOCKS_MODERN_BLOCKLY_WWI_PASS');
  }

  window.addEventListener('error', event => {
    report('ERROR', {message: event.message, filename: event.filename, line: event.lineno});
  });
  window.addEventListener('unhandledrejection', event => report('ERROR', {message: String(event.reason)}));
  window.addEventListener('load', () => {
    main().catch(async error => {
      document.getElementById('status').textContent = 'ERROR';
      await report('ERROR', {message: error && error.stack ? error.stack : String(error)});
      await reportChain;
      console.error(error);
    });
  });
})();
