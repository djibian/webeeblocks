'use strict';
const assert = require('assert');
const NativeFileBroker = require('../../plugins/robot_windows/blockly/webeeblocks/native_file_broker.js');

(async function() {
  const sent = [];
  const broker = new NativeFileBroker({send: message => sent.push(message)}, {timeoutMs: 1000});
  const pending = broker.requestCapabilities();
  assert.deepStrictEqual(sent, ['WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 1 CAPABILITIES']);
  assert.strictEqual(broker.handleMessage('WEBEEBLOCKS_RUNTIME_V2 READY'), false);
  assert.strictEqual(broker.handleMessage(
    'WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 1 CAPABILITIES ' +
    '{"protocol":1,"provider":"qt6-qfiledialog-constructed","providerInjectable":true,"operationsReady":false,"canonicalExtension":".wbb"}'
  ), true);
  assert.strictEqual((await pending).operationsReady, false);
  console.log('PASS: browser capability-only broker handshake parser');
})().catch(error => { console.error(error); process.exit(1); });
