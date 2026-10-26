'use strict';
// Experiment intervention: delay ONLY the seventh ordinary RESET until a passive
// native sample sees the failed vehicle on the floor. Never alter physics/ACKs.
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const Backend = require(path.join(root, 'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'));
const original = Backend.prototype.resetSimulation;
let resets = 0;
Backend.prototype.resetSimulation = async function() {
  if (++resets === 7) {
    const directory = process.env.WEBEEBLOCKS_CI_ARTIFACT_DIR;
    const filename = path.join(directory, 'native-reset-state.jsonl');
    const until = Date.now() + 10000;
    let target = null;
    while (Date.now() < until) {
      // Ignore an incomplete trailing line while the passive observer writes.
      const lines = fs.readFileSync(filename, 'utf8').split('\n');
      if (lines[lines.length-1] !== '') lines.pop();
      for (const line of lines.slice(-5).reverse()) {
        if (!line) continue;
        const sample = JSON.parse(line);
        if (sample.type === 'sample' && sample.custom_data.startsWith('WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=7 ')
            && sample.position[2] < .05 && sample.contacts.length > 0) {
          target = sample; break;
        }
      }
      if (target) break;
      await new Promise(resolve => setTimeout(resolve, 2));
    }
    if (!target) throw new Error('no post-failure floor contact observed; refuse experiment');
    fs.writeFileSync(path.join(directory,'impact-trigger.json'),JSON.stringify({
      scope:'host timing intervention, not Runtime receipt timestamp',sample:target,wall_ms:Date.now()
    },null,2)+'\n');
  }
  return original.call(this);
};
