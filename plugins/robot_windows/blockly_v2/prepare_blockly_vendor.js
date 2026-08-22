'use strict';

const fs = require('node:fs');
const path = require('node:path');

const pluginDir = __dirname;
const blocklyRoot = path.join(pluginDir, 'node_modules', 'blockly');
const vendorDir = path.join(pluginDir, 'vendor');

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
copyFile(path.join('msg', 'en.js'));
fs.cpSync(requirePath(path.join(blocklyRoot, 'media')), path.join(vendorDir, 'media'), {recursive: true});

// Webots R2025a's Robot Window server does not serve SVG assets. Blockly 13.2.1
// uses sprites.svg for the trashcan/zoom sprite but ships the raster-equivalent
// sprites.png in the same media directory. Apply one explicit build-time
// compatibility rewrite and fail closed if the upstream bundle shape changes.
requirePath(path.join(vendorDir, 'media', 'sprites.png'));
const blocklyBundlePath = path.join(vendorDir, 'blockly_compressed.js');
let blocklyBundle = fs.readFileSync(blocklyBundlePath, 'utf8');
const spriteSvgMatches = blocklyBundle.match(/sprites\.svg/g) || [];
if (spriteSvgMatches.length !== 1)
  throw new Error(`expected exactly one Blockly sprites.svg reference, found ${spriteSvgMatches.length}`);
blocklyBundle = blocklyBundle.replace('sprites.svg', 'sprites.png');
fs.writeFileSync(blocklyBundlePath, blocklyBundle, 'utf8');

const pkg = JSON.parse(fs.readFileSync(path.join(blocklyRoot, 'package.json'), 'utf8'));
if (pkg.version !== '13.2.1')
  throw new Error(`unexpected Blockly version: ${pkg.version}`);
fs.writeFileSync(path.join(vendorDir, 'VERSION'), `${pkg.version}\n`, 'utf8');
console.log(`WEBEEBLOCKS_BLOCKLY_VENDOR_VERSION=${pkg.version}`);
console.log('WEBEEBLOCKS_BLOCKLY_SPRITE=sprites.png');
