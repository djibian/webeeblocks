'use strict';

(function() {
  const PROFILE_ID = 'reactive-obstacle-v2';
  let sequence = 0;
  let reportChain = Promise.resolve();

  function canonical(value) {
    if (Array.isArray(value))
      return value.map(canonical);
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
    return {
      kind: 'flyoutToolbox',
      contents: profile.toolbox.map(type => ({kind: 'block', type}))
    };
  }

  async function main() {
    document.getElementById('status').textContent = 'PAGE_LOADED';
    await report('PAGE_LOADED', {
      href: location.href,
      origin: location.origin,
      readyState: document.readyState
    });

    if (!window.Blockly)
      throw new Error('Blockly global missing');
    if (Blockly.VERSION !== '13.2.1')
      throw new Error(`unexpected Blockly version: ${Blockly.VERSION}`);
    if (!window.WebeeBlocksActivityProfiles || !window.WebeeBlocksActivities ||
        !window.WebeeBlocksSemanticAst || !window.WebeeBlocksActivityContract)
      throw new Error('Runtime v2 product modules missing');
    if (!window.WebeeBlocksModernBlocklyFixture ||
        typeof window.WebeeBlocksModernBlocklyFixture.xml !== 'string' ||
        !window.WebeeBlocksModernBlocklyFixture.expectedAst)
      throw new Error('embedded modern Blockly fixture missing');

    document.getElementById('status').textContent = 'BLOCKLY_INITIALIZED';
    await report('BLOCKLY_INITIALIZED', {version: Blockly.VERSION});

    const profile = WebeeBlocksActivityProfiles.resolveById(
      WebeeBlocksActivities.DOCUMENT,
      PROFILE_ID,
      WebeeBlocksActivities.BLOCK_CATALOG
    );
    for (const type of profile.toolbox) {
      if (!Blockly.Blocks[type])
        throw new Error(`profile block unavailable in modern Blockly: ${type}`);
    }

    const workspace = Blockly.inject('blocklyDiv', {
      toolbox: toolboxFromProfile(profile),
      scrollbars: true,
      sounds: false,
      media: 'vendor/media/'
    });
    window.modernBlocklyExperimentWorkspace = workspace;
    WebeeBlocksActivityContract.applyFieldBounds(profile, workspace);

    const takeoff = workspace.newBlock('webeeblocks_v2_takeoff');
    const height = takeoff.getField('HEIGHT');
    height.setValue(99);
    if (Number(height.getValue()) !== 1.5)
      throw new Error('profile upper bound not applied by modern Robot Window');
    height.setValue(-99);
    if (Number(height.getValue()) !== 0.2)
      throw new Error('profile lower bound not applied by modern Robot Window');
    workspace.clear();

    document.getElementById('status').textContent = 'PROFILE_APPLIED';
    await report('PROFILE_APPLIED', {
      profile: profile.id,
      toolbox: profile.toolbox.slice(),
      takeoffBounds: profile.parameterBounds.webeeblocks_v2_takeoff.HEIGHT
    });

    const fixture = window.WebeeBlocksModernBlocklyFixture;
    const xml = Blockly.utils.xml.textToDom(fixture.xml);
    Blockly.Xml.domToWorkspace(xml, workspace);
    WebeeBlocksActivityContract.preflightWorkspace(profile, workspace);
    WebeeBlocksActivityContract.applyFieldBounds(profile, workspace);
    const ast = WebeeBlocksSemanticAst.compileWorkspace(workspace);
    WebeeBlocksActivityContract.preflightAst(profile, ast);

    if (!sameJson(ast, fixture.expectedAst))
      throw new Error(`AST mismatch: actual=${JSON.stringify(ast)} expected=${JSON.stringify(fixture.expectedAst)}`);

    const resources = performance.getEntriesByType('resource').map(entry => entry.name);
    document.getElementById('status').textContent = 'AST_EQUIVALENT';
    await report('AST_EQUIVALENT', {ast, resources});
    await reportChain;
    console.log('WEBEEBLOCKS_MODERN_BLOCKLY_ROBOT_WINDOW_PASS');
  }

  window.addEventListener('error', event => {
    report('ERROR', {message: event.message, filename: event.filename, line: event.lineno});
  });
  window.addEventListener('unhandledrejection', event => {
    report('ERROR', {message: String(event.reason)});
  });

  window.addEventListener('load', () => {
    main().catch(async error => {
      document.getElementById('status').textContent = 'ERROR';
      await report('ERROR', {message: error && error.stack ? error.stack : String(error)});
      await reportChain;
      console.error(error);
    });
  });
})();
