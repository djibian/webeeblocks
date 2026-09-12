(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksProjectFileWwiTransport = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var PREFIX = 'WEBEEBLOCKS_FILE_BROKER_V1';
  var TOKEN = /^[A-Za-z0-9_-]{1,128}$/;

  function BrokerError(code) {
    this.name = 'ProjectFileBrokerError';
    this.code = String(code || 'IO_ERROR');
    this.message = 'Project file broker error: ' + this.code;
    if (Error.captureStackTrace) Error.captureStackTrace(this, BrokerError);
  }
  BrokerError.prototype = Object.create(Error.prototype);
  BrokerError.prototype.constructor = BrokerError;

  function cancellation() {
    var error = new Error('Project file dialog cancelled');
    error.name = 'AbortError';
    error.code = 20;
    return error;
  }

  function bytesToBase64(bytes) {
    if (typeof btoa === 'function') {
      var binary = '';
      for (var offset = 0; offset < bytes.length; offset += 0x8000) {
        var chunk = bytes.subarray(offset, Math.min(offset + 0x8000, bytes.length));
        binary += String.fromCharCode.apply(null, chunk);
      }
      return btoa(binary);
    }
    if (typeof Buffer !== 'undefined') return Buffer.from(bytes).toString('base64');
    throw new Error('Base64 encoder unavailable');
  }

  function base64ToBytes(value) {
    if (typeof atob === 'function') {
      var binary = atob(value);
      var bytes = new Uint8Array(binary.length);
      for (var i = 0; i < binary.length; ++i) bytes[i] = binary.charCodeAt(i);
      return bytes;
    }
    if (typeof Buffer !== 'undefined') return new Uint8Array(Buffer.from(value, 'base64'));
    throw new Error('Base64 decoder unavailable');
  }

  function encodeText(value) {
    if (typeof TextEncoder !== 'function') throw new Error('UTF-8 encoder unavailable');
    return bytesToBase64(new TextEncoder().encode(String(value)));
  }

  function decodeText(value) {
    if (typeof TextDecoder !== 'function') throw new Error('UTF-8 decoder unavailable');
    return new TextDecoder('utf-8', {fatal: true}).decode(base64ToBytes(value));
  }

  function WwiProjectFileTransport(robotWindow, options) {
    if (!robotWindow || typeof robotWindow.send !== 'function')
      throw new Error('Project file WWI transport unavailable');
    this.robotWindow = robotWindow;
    this.timeoutMs = options && Number.isFinite(options.timeoutMs) ? options.timeoutMs : 5000;
    this.nextId = 1;
    this.pending = Object.create(null);
    this.readyPromise = null;
    this.capabilities = null;
    // Compatibility with the existing project manager/UI contract: both the
    // Chromium picker and the local WWI broker provide direct same-file access.
    this.nativeFileSystemAccess = true;
    this.mode = 'wwi-native';
  }

  WwiProjectFileTransport.prototype._request = function(operation, args) {
    var self = this;
    var id = this.nextId++;
    var suffix = args && args.length ? ' ' + args.join(' ') : '';
    return new Promise(function(resolve, reject) {
      // Bound only the non-side-effecting readiness handshake. Open and Save As
      // are user-paced, while Save may legitimately block on slow local/network
      // storage. The protocol has no cancellation acknowledgement: timing out a
      // file operation could detach the browser from an operation that later
      // commits, leaving the manager's target state inconsistent with disk.
      var bounded = operation === 'CAPABILITIES';
      var timer = bounded ? setTimeout(function() {
        if (!self.pending[id]) return;
        delete self.pending[id];
        reject(new BrokerError('TIMEOUT'));
      }, self.timeoutMs) : null;
      self.pending[id] = {operation: operation, resolve: resolve, reject: reject, timer: timer};
      try {
        self.robotWindow.send(PREFIX + ' REQUEST ' + id + ' ' + operation + suffix);
      } catch (error) {
        clearTimeout(timer);
        delete self.pending[id];
        reject(error);
      }
    });
  };

  WwiProjectFileTransport.prototype.waitUntilReady = function() {
    if (this.readyPromise) return this.readyPromise;
    var self = this;
    this.readyPromise = this._request('CAPABILITIES', []).then(function(capabilities) {
      if (!capabilities || capabilities.protocol !== 1 || capabilities.operationsReady !== true ||
          capabilities.sameFileSave !== true || capabilities.canonicalExtension !== '.wbb')
        throw new BrokerError('CAPABILITY_UNAVAILABLE');
      self.capabilities = Object.freeze(capabilities);
      return self.capabilities;
    });
    return this.readyPromise;
  };

  WwiProjectFileTransport.prototype.handleMessage = function(message) {
    if (typeof message !== 'string' || message.indexOf(PREFIX + ' RESPONSE ') !== 0)
      return false;
    var match = message.match(/^WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE (\d+) (.+)$/);
    if (!match) return true;
    var id = Number(match[1]);
    var pending = this.pending[id];
    if (!pending) return true;
    clearTimeout(pending.timer);
    delete this.pending[id];
    var payload = match[2];
    var error = payload.match(/^ERR ([A-Z][A-Z0-9_]{0,63})$/);
    if (error) {
      pending.reject(new BrokerError(error[1]));
      return true;
    }
    if (payload === pending.operation + ' CANCELLED') {
      pending.reject(cancellation());
      return true;
    }
    try {
      if (pending.operation === 'CAPABILITIES') {
        var capabilities = payload.match(/^CAPABILITIES (\{.*\})$/);
        if (!capabilities) throw new BrokerError('INVALID_RESPONSE');
        pending.resolve(JSON.parse(capabilities[1]));
        return true;
      }
      if (pending.operation === 'OPEN') {
        var opened = payload.match(/^OPEN OK ([A-Za-z0-9_-]{1,128}) ([A-Za-z0-9+/=]+) ([A-Za-z0-9+/=]+)$/);
        if (!opened) throw new BrokerError('INVALID_RESPONSE');
        pending.resolve({handle:{kind:'wwi',reference:opened[1]}, name:decodeText(opened[2]), text:decodeText(opened[3]), mode:this.mode});
        return true;
      }
      var saved = payload.match(new RegExp('^' + pending.operation + ' OK ([A-Za-z0-9_-]{1,128}) ([A-Za-z0-9+/=]+)$'));
      if (!saved) throw new BrokerError('INVALID_RESPONSE');
      pending.resolve({handle:{kind:'wwi',reference:saved[1]}, name:decodeText(saved[2]), mode:this.mode});
    } catch (responseError) {
      pending.reject(responseError instanceof BrokerError ? responseError : new BrokerError('INVALID_RESPONSE'));
    }
    return true;
  };

  WwiProjectFileTransport.prototype.open = function() {
    var self = this;
    return this.waitUntilReady().then(function() { return self._request('OPEN', []); });
  };

  WwiProjectFileTransport.prototype.saveAs = function(name, text) {
    var self = this;
    return this.waitUntilReady().then(function() {
      return self._request('SAVE_AS', [encodeText(name), encodeText(text)]);
    });
  };

  WwiProjectFileTransport.prototype.save = function(target, name, text) {
    var self = this;
    if (!target || target.kind !== 'wwi' || !TOKEN.test(target.reference || ''))
      return Promise.reject(new BrokerError('TARGET_UNAVAILABLE'));
    return this.waitUntilReady().then(function() {
      return self._request('SAVE', [target.reference, encodeText(text)]);
    });
  };

  WwiProjectFileTransport.BrokerError = BrokerError;
  WwiProjectFileTransport.encodeText = encodeText;
  WwiProjectFileTransport.decodeText = decodeText;
  return WwiProjectFileTransport;
});
