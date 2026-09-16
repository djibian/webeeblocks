'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SOURCE = path.join(ROOT, 'activities', 'progression');
const BLOCKLY = path.join(ROOT, 'plugins', 'robot_windows', 'blockly_v2');
const TARGET = path.join(BLOCKLY, 'vendor', 'classroom-activities', 'progression');
const Activities = require(path.join(
  ROOT,
  'plugins',
  'robot_windows',
  'blockly',
  'webeeblocks',
  'activities.js'
));

function fail(message) {
  throw new Error('classroom progression preparation: ' + message);
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    fail('invalid JSON in ' + path.relative(ROOT, file) + ': ' + error.message);
  }
}

function same(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

const manifestPath = path.join(SOURCE, 'index.json');
if (!fs.existsSync(manifestPath)) fail('starter manifest is missing');

const manifest = readJson(manifestPath);
if (!manifest || manifest.version !== 1 || !Array.isArray(manifest.starters) || !manifest.starters.length)
  fail('starter manifest must contain a non-empty version 1 starters array');

const progressionProfiles = Activities.DOCUMENT.activities
  .filter(activity => activity.id.startsWith('progression-'));
const profileIds = progressionProfiles.map(activity => activity.id);
const profileById = new Map(progressionProfiles.map(activity => [activity.id, activity]));
const declaredFiles = [];
const declaredIds = [];
const seenFiles = new Set();
const seenIds = new Set();

for (const entry of manifest.starters) {
  if (!entry || typeof entry.file !== 'string' || typeof entry.activityId !== 'string')
    fail('each starter entry must contain file and activityId strings');
  if (!/^\d{2}-[a-z0-9-]+\.wbb$/.test(entry.file) || path.basename(entry.file) !== entry.file)
    fail('invalid starter filename: ' + entry.file);
  if (!/^progression-[a-z0-9-]+-v1$/.test(entry.activityId))
    fail('invalid progression activity id: ' + entry.activityId);
  if (seenFiles.has(entry.file) || seenIds.has(entry.activityId))
    fail('duplicate starter declaration: ' + entry.file + ' / ' + entry.activityId);
  seenFiles.add(entry.file);
  seenIds.add(entry.activityId);
  declaredFiles.push(entry.file);
  declaredIds.push(entry.activityId);

  const profile = profileById.get(entry.activityId);
  if (!profile || !profile.brief || profile.brief.visible !== true)
    fail('starter does not map to one visible progression profile: ' + entry.activityId);

  const starterPath = path.join(SOURCE, entry.file);
  if (!fs.existsSync(starterPath)) fail('declared starter is missing: ' + entry.file);
  const project = readJson(starterPath);
  if (project.format !== 'webeeblocks-project' || project.version !== 1)
    fail('invalid project format in ' + entry.file);
  if (!project.activity || project.activity.id !== entry.activityId || project.activity.semantics !== 'webeeblocks-ast-v1')
    fail('starter project does not match manifest activity: ' + entry.file);
}

if (!same(declaredIds, profileIds))
  fail('manifest order must map one-to-one to every declared progression profile');

const sourceFiles = fs.readdirSync(SOURCE)
  .filter(name => name.endsWith('.wbb'))
  .sort();
const sortedDeclaredFiles = declaredFiles.slice().sort();
if (!same(sourceFiles, sortedDeclaredFiles))
  fail('manifest must declare every progression starter exactly once');

fs.rmSync(TARGET, {recursive: true, force: true});
fs.mkdirSync(TARGET, {recursive: true});
fs.copyFileSync(manifestPath, path.join(TARGET, 'index.json'));
for (const file of declaredFiles)
  fs.copyFileSync(path.join(SOURCE, file), path.join(TARGET, file));

const preparedFiles = fs.readdirSync(TARGET).sort();
const expectedPreparedFiles = ['index.json', ...sortedDeclaredFiles].sort();
if (!same(preparedFiles, expectedPreparedFiles))
  fail('prepared starter bundle is incomplete');

console.log('Classroom progression ready: ' + declaredFiles.length + ' starters');
