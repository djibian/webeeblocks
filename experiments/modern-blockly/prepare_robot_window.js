'use strict';

const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const blocklyRoot = path.join(__dirname, 'node_modules', 'blockly');
const pluginName = 'modern_blockly_v2_experiment';
const pluginDir = path.join(root, 'plugins', 'robot_windows', pluginName);
const vendorDir = path.join(pluginDir, 'vendor');
const worldSource = path.join(root, 'worlds', 'crazyflie_runtime_v2.wbt');
const worldTarget = path.join(root, 'worlds', 'modern_blockly_v2_experiment.wbt');
const projectTarget = path.join(root, 'worlds', '.modern_blockly_v2_experiment.wbproj');

function requireFile(file) {
  if (!fs.existsSync(file))
    throw new Error(`required file missing: ${file}`);
  return file;
}

function copyFile(source, target) {
  requireFile(source);
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.copyFileSync(source, target);
}

function copyTree(source, target) {
  requireFile(source);
  fs.cpSync(source, target, {recursive: true});
}

fs.rmSync(pluginDir, {recursive: true, force: true});
fs.mkdirSync(vendorDir, {recursive: true});

copyFile(path.join(blocklyRoot, 'blockly_compressed.js'), path.join(vendorDir, 'blockly_compressed.js'));
copyFile(path.join(blocklyRoot, 'blocks_compressed.js'), path.join(vendorDir, 'blocks_compressed.js'));
copyFile(path.join(blocklyRoot, 'msg', 'en.js'), path.join(vendorDir, 'msg', 'en.js'));
copyTree(path.join(blocklyRoot, 'media'), path.join(vendorDir, 'media'));

copyFile(path.join(__dirname, 'robot_window.html'), path.join(pluginDir, `${pluginName}.html`));
copyFile(path.join(__dirname, 'robot_window.js'), path.join(pluginDir, 'main.js'));

const fixtureXml = fs.readFileSync(
  requireFile(path.join(root, 'controllers', 'Blockly_Programs', 'CrazyflieReactiveV2.xml')),
  'utf8'
);
const expectedAst = JSON.parse(fs.readFileSync(requireFile(path.join(__dirname, 'expected_ast.json')), 'utf8'));
fs.writeFileSync(
  path.join(pluginDir, 'fixture_data.js'),
  `'use strict';\nwindow.WebeeBlocksModernBlocklyFixture = ${JSON.stringify({xml: fixtureXml, expectedAst})};\n`,
  'utf8'
);

const world = fs.readFileSync(requireFile(worldSource), 'utf8');
if (!world.includes('window "blockly_v2"'))
  throw new Error('Runtime v2 world no longer contains window "blockly_v2"');
fs.writeFileSync(worldTarget, world.replace('window "blockly_v2"', `window "${pluginName}"`), 'utf8');
fs.writeFileSync(projectTarget, 'Webots Project File version R2025a\nrobotWindow: Crazyflie Runtime v2\n', 'utf8');

// Scan executable HTML/JS references only. fixture_data.js deliberately contains the
// historical XML namespace URL as inert data; runtime network behavior is asserted
// independently from Chrome NetLog in CI.
const forbidden = /https?:\/\/(?!127\.0\.0\.1(?::\d+)?\/event)/g;
for (const file of [
  path.join(pluginDir, `${pluginName}.html`),
  path.join(pluginDir, 'main.js')
]) {
  const text = fs.readFileSync(file, 'utf8');
  const match = text.match(forbidden);
  if (match)
    throw new Error(`runtime external URL forbidden in ${file}: ${match.join(', ')}`);
}

console.log(`MODERN_BLOCKLY_PLUGIN=${pluginDir}`);
console.log(`MODERN_BLOCKLY_WORLD=${worldTarget}`);
console.log('OFFLINE_BUNDLE_PREPARED=PASS');
