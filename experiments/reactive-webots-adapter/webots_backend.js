(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksWebotsBackend = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function fail(message) {
    throw new Error('webots adapter: ' + message);
  }

  function finite(value, name) {
    var n = Number(value);
    if (!Number.isFinite(n))
      fail(name + ' must be finite');
    return n;
  }

  function WebotsBackend(endpoint) {
    this.endpoint = endpoint || 'http://127.0.0.1:8765';
    this.trace = [];
  }

  WebotsBackend.prototype.rpc = function(payload) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', this.endpoint + '/rpc', false);
    xhr.setRequestHeader('Content-Type', 'text/plain;charset=UTF-8');
    xhr.send(JSON.stringify(payload));
    if (xhr.status !== 200)
      fail('RPC HTTP ' + xhr.status + ': ' + xhr.responseText);
    var response;
    try {
      response = JSON.parse(xhr.responseText);
    } catch (error) {
      fail('invalid RPC JSON');
    }
    if (!response || response.ok !== true)
      fail(response && response.error ? response.error : 'RPC failed');
    return response;
  };

  WebotsBackend.prototype.readRange = function(direction) {
    if (direction !== 'front')
      fail('capability unavailable: range(' + direction + ')');
    var response = this.rpc({op: 'range', direction: direction});
    var value = finite(response.value_m, 'range(front)');
    if (value < 0 || value > 2.001)
      fail('range(front) outside Webots sensor domain: ' + value);
    this.trace.push({op: 'range', direction: 'front', value_m: value, source: response.source});
    return value;
  };

  WebotsBackend.prototype.takeoff = function(height_m) {
    var height = finite(height_m, 'height_m');
    var response = this.rpc({op: 'takeoff', height_m: height});
    this.trace.push({op: 'takeoff', height_m: height, before: response.before, after: response.after});
  };

  WebotsBackend.prototype.land = function() {
    var response = this.rpc({op: 'land'});
    this.trace.push({op: 'land', before: response.before, after: response.after});
  };

  WebotsBackend.prototype.move = function(direction, distance_m) {
    if (direction !== 'forward' && direction !== 'left')
      fail('capability unavailable: move(' + direction + ')');
    var distance = finite(distance_m, 'distance_m');
    var response = this.rpc({op: 'move', direction: direction, distance_m: distance});
    this.trace.push({op: 'move', direction: direction, distance_m: distance, before: response.before, after: response.after});
  };

  WebotsBackend.prototype.vertical = function(direction) { fail('capability unavailable: vertical(' + direction + ')'); };
  WebotsBackend.prototype.turn = function() { fail('capability unavailable: turn'); };
  WebotsBackend.prototype.wait = function() { fail('capability unavailable: wait'); };
  WebotsBackend.prototype.setSpeed = function() { fail('capability unavailable: setSpeed'); };

  WebotsBackend.prototype.getControllerTrace = function() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', this.endpoint + '/trace', false);
    xhr.send(null);
    if (xhr.status !== 200)
      fail('trace HTTP ' + xhr.status);
    return JSON.parse(xhr.responseText);
  };

  return {WebotsBackend: WebotsBackend};
});
