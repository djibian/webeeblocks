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
    '{"protocol":1,"provider":"ci-injected-dialog","providerInjectable":true,"operationsReady":false,"canonicalExtension":".wbb"}'
  ), true);
  const capabilities = await pending;
  assert.strictEqual(capabilities.provider, 'ci-injected-dialog');
  assert.strictEqual(capabilities.operationsReady, false);
  console.log('PASS: browser native file broker handshake parser');
})().catch(error => { console.error(error); process.exit(1); });
