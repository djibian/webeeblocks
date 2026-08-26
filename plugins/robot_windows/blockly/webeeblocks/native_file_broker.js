(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksNativeFileBroker = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  var PREFIX = 'WEBEEBLOCKS_FILE_BROKER_V1';

  function NativeFileBroker(robotWindow, options) {
    if (!robotWindow || typeof robotWindow.send !== 'function') throw new Error('native file broker requires RobotWindow');
    this.robotWindow = robotWindow;
    this.timeoutMs = options && options.timeoutMs || 5000;
    this.nextId = 1;
    this.pending = new Map();
  }
  NativeFileBroker.prototype.handleMessage = function(message) {
    if (typeof message !== 'string' || message.indexOf(PREFIX + ' RESPONSE ') !== 0) return false;
    var match = message.match(/^WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE ([1-9][0-9]*) CAPABILITIES (\{.*\})$/);
    if (!match) return true;
    var pending = this.pending.get(Number(match[1]));
    if (!pending) return true;
    this.pending.delete(Number(match[1]));
    clearTimeout(pending.timer);
    try {
      var capabilities = JSON.parse(match[2]);
      if (capabilities.protocol !== 1 || capabilities.provider !== 'qt6-qfiledialog-constructed' ||
          capabilities.providerInjectable !== true || capabilities.operationsReady !== false ||
          capabilities.canonicalExtension !== '.wbb')
        throw new Error('native file broker capability contract mismatch');
      pending.resolve(capabilities);
    } catch (error) { pending.reject(error); }
    return true;
  };
  NativeFileBroker.prototype.requestCapabilities = function() {
    var self = this;
    var id = this.nextId++;
    return new Promise(function(resolve, reject) {
      var timer = setTimeout(function() {
        self.pending.delete(id);
        reject(new Error('native file broker capability timeout'));
      }, self.timeoutMs);
      self.pending.set(id, {resolve: resolve, reject: reject, timer: timer});
      self.robotWindow.send(PREFIX + ' REQUEST ' + id + ' CAPABILITIES');
    });
  };
  NativeFileBroker.PREFIX = PREFIX;
  return NativeFileBroker;
});
