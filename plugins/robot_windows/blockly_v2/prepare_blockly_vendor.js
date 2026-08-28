'use strict';

const fs = require('node:fs');
const path = require('node:path');

const pluginDir = __dirname;
const blocklyRoot = path.join(pluginDir, 'node_modules', 'blockly');
const vendorDir = path.join(pluginDir, 'vendor');
const historicalMediaDir = path.join(
  pluginDir,
  '..',
  'blockly',
  'google-blockly-31ee4ea',
  'media'
);

function requirePath(target) {
  if (!fs.existsSync(target))
    throw new Error(`required Blockly asset missing: ${target}`);
  return target;
}

function copyFile(relativeSource, relativeTarget = relativeSource) {
  const source = requirePath(path.join(blocklyRoot, relativeSource));
  const target = path.join(vendorDir, relativeTarget);
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.copyFileSync(source, target);
}

fs.rmSync(vendorDir, {recursive: true, force: true});
fs.mkdirSync(vendorDir, {recursive: true});
copyFile('blockly_compressed.js');
copyFile('blocks_compressed.js');
copyFile(path.join('msg', 'fr.js'));
fs.cpSync(requirePath(path.join(blocklyRoot, 'media')), path.join(vendorDir, 'media'), {recursive: true});

// Webots R2025a's Robot Window server does not serve SVG assets. Blockly 13.2.1
// uses sprites.svg for the trashcan/zoom sprite, while the preserved Blockly
// runtime already contains the rasterized sprites.png generated from the same
// SVG. Reuse that PNG only if both SVG sources are byte-for-byte identical;
// otherwise fail closed instead of silently substituting a mismatched UI asset.
const modernSpriteSvg = requirePath(path.join(blocklyRoot, 'media', 'sprites.svg'));
const historicalSpriteSvg = requirePath(path.join(historicalMediaDir, 'sprites.svg'));
const historicalSpritePng = requirePath(path.join(historicalMediaDir, 'sprites.png'));
const modernSvgBytes = fs.readFileSync(modernSpriteSvg);
const historicalSvgBytes = fs.readFileSync(historicalSpriteSvg);
if (!modernSvgBytes.equals(historicalSvgBytes))
  throw new Error('Blockly 13.2.1 sprites.svg differs from the preserved raster source');
fs.copyFileSync(historicalSpritePng, path.join(vendorDir, 'media', 'sprites.png'));

const blocklyBundlePath = path.join(vendorDir, 'blockly_compressed.js');
let blocklyBundle = fs.readFileSync(blocklyBundlePath, 'utf8');
const spriteSvgMatches = blocklyBundle.match(/sprites\.svg/g) || [];
if (spriteSvgMatches.length !== 3)
  throw new Error(`expected exactly three Blockly sprites.svg references, found ${spriteSvgMatches.length}`);
blocklyBundle = blocklyBundle.replaceAll('sprites.svg', 'sprites.png');
if (blocklyBundle.includes('sprites.svg'))
  throw new Error('Blockly sprites.svg reference remained after compatibility rewrite');
fs.writeFileSync(blocklyBundlePath, blocklyBundle, 'utf8');

const pkg = JSON.parse(fs.readFileSync(path.join(blocklyRoot, 'package.json'), 'utf8'));
if (pkg.version !== '13.2.1')
  throw new Error(`unexpected Blockly version: ${pkg.version}`);
fs.writeFileSync(path.join(vendorDir, 'VERSION'), `${pkg.version}\n`, 'utf8');
console.log(`WEBEEBLOCKS_BLOCKLY_VENDOR_VERSION=${pkg.version}`);
console.log('WEBEEBLOCKS_BLOCKLY_SPRITE=sprites.png');
