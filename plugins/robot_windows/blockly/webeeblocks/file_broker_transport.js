(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksFileBrokerTransport = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var PREFIX = 'WEBEEBLOCKS_FILE_BROKER_V1';
  var TOKEN_RE = /^[A-Za-z0-9_-]{1,128}$/;
  var PAYLOAD_RE = /^[A-Za-z0-9_-]*$/;

  function fail(message) { throw new Error('file broker transport: ' + message); }

  function cancellation() {
    var error = new Error('File operation cancelled');
    error.name = 'AbortError';
    error.code = 20;
    return error;
  }

  function encodeUtf8(value) {
    var bytes = new TextEncoder().encode(String(value));
    var binary = '';
    for (var offset = 0; offset < bytes.length; offset += 0x8000) {
      var chunk = bytes.subarray(offset, Math.min(bytes.length, offset + 0x8000));
      binary += String.fromCharCode.apply(null, chunk);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  }

  function decodeUtf8(value) {
    if (!PAYLOAD_RE.test(value)) fail('invalid encoded payload');
    var base64 = value.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) base64 += '=';
    var binary;
    try { binary = atob(base64); }
    catch (error) { fail('invalid encoded payload'); }
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; ++i) bytes[i] = binary.charCodeAt(i);
    try { return new TextDecoder('utf-8', {fatal: true}).decode(bytes); }
    catch (error) { fail('invalid UTF-8 payload'); }
  }

  function create(robotWindow, options) {
    if (!robotWindow || typeof robotWindow.send !== 'function') fail('Robot Window transport unavailable');
    var nextId = 1;
    var pending = Object.create(null);
    var operationTimeoutMs = options && Number.isFinite(options.operationTimeoutMs) ? options.operationTimeoutMs : 600000;
    var probeTimeoutMs = options && Number.isFinite(options.probeTimeoutMs) ? options.probeTimeoutMs : 2000;
    var previousReceive = typeof robotWindow.receive === 'function' ? robotWindow.receive : null;

    function request(parts, timeoutMs) {
      var id = nextId++;
      return new Promise(function(resolve, reject) {
        var timer = setTimeout(function() {
          if (!pending[id]) return;
          delete pending[id];
          reject(new Error('file broker request timeout id=' + id));
        }, timeoutMs);
        pending[id] = {resolve: resolve, reject: reject, timer: timer};
        try { robotWindow.send(PREFIX + ' REQUEST ' + id + ' ' + parts.join(' ')); }
        catch (error) {
          clearTimeout(timer);
          delete pending[id];
          reject(error);
        }
      });
    }

    function receive(value) {
      var text = String(value);
      var match = text.match(/^WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE (\d+) (.+)$/);
      if (!match) return false;
      var id = Number(match[1]);
      var waiter = pending[id];
      if (!waiter) return true;
      clearTimeout(waiter.timer);
      delete pending[id];
      waiter.resolve(match[2]);
      return true;
    }

    robotWindow.receive = function(value) {
      if (receive(value)) return;
      if (previousReceive) return previousReceive.call(robotWindow, value);
    };

    function parseErrorOrCancel(payload) {
      if (payload === 'CANCEL') throw cancellation();
      var error = payload.match(/^ERR ([A-Z0-9_]+)$/);
      if (error) fail('broker error ' + error[1]);
    }

    function requireToken(value) {
      if (!TOKEN_RE.test(value)) fail('invalid opaque target reference');
      return value;
    }

    return {
      mode: 'wwi-native-broker',
      nativeFileSystemAccess: false,
      async probe() {
        var payload = await request(['CAPABILITIES'], probeTimeoutMs);
        var match = payload.match(/^CAPABILITIES (\{.*\})$/);
        if (!match) fail('invalid capabilities response');
        var capabilities;
        try { capabilities = JSON.parse(match[1]); }
        catch (error) { fail('invalid capabilities JSON'); }
        if (!capabilities || capabilities.protocol !== 1 || capabilities.operationsReady !== true || capabilities.canonicalExtension !== '.wbb')
          fail('native broker operations unavailable');
        return capabilities;
      },
      async open() {
        var payload = await request(['OPEN'], operationTimeoutMs);
        parseErrorOrCancel(payload);
        var match = payload.match(/^OPEN OK ([A-Za-z0-9_-]{1,128}) ([A-Za-z0-9_-]*) ([A-Za-z0-9_-]*)$/);
        if (!match) fail('invalid OPEN response');
        var token = requireToken(match[1]);
        var name = decodeUtf8(match[2]);
        var text = decodeUtf8(match[3]);
        return {handle: Object.freeze({brokerRef: token, name: name}), name: name, text: text, mode: 'wwi-native-broker'};
      },
      async saveAs(name, text) {
        var payload = await request(['SAVE_AS', encodeUtf8(name), encodeUtf8(text)], operationTimeoutMs);
        parseErrorOrCancel(payload);
        var match = payload.match(/^SAVE_AS OK ([A-Za-z0-9_-]{1,128}) ([A-Za-z0-9_-]*)$/);
        if (!match) fail('invalid SAVE_AS response');
        var token = requireToken(match[1]);
        var selectedName = decodeUtf8(match[2]);
        return {handle: Object.freeze({brokerRef: token, name: selectedName}), name: selectedName, mode: 'wwi-native-broker'};
      },
      async save(target, name, text) {
        if (!target || typeof target.brokerRef !== 'string') fail('current opaque target unavailable');
        var token = requireToken(target.brokerRef);
        var payload = await request(['SAVE', token, encodeUtf8(text)], operationTimeoutMs);
        parseErrorOrCancel(payload);
        var match = payload.match(/^SAVE OK ([A-Za-z0-9_-]{1,128}) ([A-Za-z0-9_-]*)$/);
        if (!match) fail('invalid SAVE response');
        if (requireToken(match[1]) !== token) fail('broker changed current target');
        var selectedName = decodeUtf8(match[2]);
        return {handle: target, name: selectedName || name, mode: 'wwi-native-broker'};
      }
    };
  }

  return {PREFIX: PREFIX, create: create, encodeUtf8: encodeUtf8, decodeUtf8: decodeUtf8};
});
