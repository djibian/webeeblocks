(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksWwiBackend = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var PREFIX = 'WEBEEBLOCKS_RUNTIME_V2';

  function RuntimeV2BackendError(code) {
    this.name = 'RuntimeV2BackendError';
    this.code = String(code);
    this.message = 'Runtime v2 backend error: ' + this.code;
    if (Error.captureStackTrace)
      Error.captureStackTrace(this, RuntimeV2BackendError);
  }
  RuntimeV2BackendError.prototype = Object.create(Error.prototype);
  RuntimeV2BackendError.prototype.constructor = RuntimeV2BackendError;

  function RuntimeV2WwiBackend(robotWindow, options) {
    if (!robotWindow || typeof robotWindow.send !== 'function')
      throw new Error('Runtime v2 RobotWindow transport unavailable');
    this.robotWindow = robotWindow;
    this.timeoutMs = options && Number.isFinite(options.timeoutMs) ? options.timeoutMs : 35000;
    this.nextId = 1;
    this.pending = Object.create(null);
    this.ready = false;
    this.readyWaiters = [];
    this.simulationStopped = false;
    var capabilities = {
      actions: ['takeoff', 'move', 'land'],
      rangeDirections: ['front', 'left', 'right'],
      moveDirections: ['forward', 'left'],
      verticalDirections: []
    };
    if (options && options.simulationDebug === true)
      capabilities.simulationDebug = true;
    if (options && options.simulationReset === true)
      capabilities.simulationReset = true;
    if (options && options.simulationStop === true)
      capabilities.simulationStop = true;
    this.capabilities = Object.freeze(capabilities);
  }

  RuntimeV2WwiBackend.prototype.waitUntilReady = function() {
    if (this.ready)
      return Promise.resolve();
    var self = this;
    return new Promise(function(resolve, reject) {
      var waiter = {resolve: resolve, reject: reject, timer: null};
      waiter.timer = setTimeout(function() {
        var index = self.readyWaiters.indexOf(waiter);
        if (index !== -1)
          self.readyWaiters.splice(index, 1);
        reject(new Error('Runtime v2 READY timeout'));
      }, self.timeoutMs);
      self.readyWaiters.push(waiter);
    });
  };

  RuntimeV2WwiBackend.prototype._request = function(parts) {
    var self = this;
    var id = this.nextId++;
    return new Promise(function(resolve, reject) {
      var timer = setTimeout(function() {
        if (!self.pending[id]) return;
        delete self.pending[id];
        reject(new Error('Runtime v2 request timeout id=' + id));
      }, self.timeoutMs);
      self.pending[id] = {resolve: resolve, reject: reject, timer: timer};
      try {
        self.robotWindow.send(PREFIX + ' REQUEST ' + id + ' ' + parts.join(' '));
      } catch (error) {
        clearTimeout(timer);
        delete self.pending[id];
        reject(error);
      }
    });
  };

  RuntimeV2WwiBackend.prototype._cancelPendingForReset = function() {
    var pending = this.pending;
    this.pending = Object.create(null);
    Object.keys(pending).forEach(function(id) {
      clearTimeout(pending[id].timer);
      pending[id].reject(new RuntimeV2BackendError('RESET_CANCELLED'));
    });
  };

  RuntimeV2WwiBackend.prototype.handleMessage = function(message) {
    if (typeof message !== 'string' || message.indexOf(PREFIX + ' ') !== 0)
      return false;
    if (message === PREFIX + ' READY') {
      this.ready = true;
      var waiters = this.readyWaiters.splice(0);
      waiters.forEach(function(waiter) {
        clearTimeout(waiter.timer);
        waiter.resolve();
      });
      return true;
    }
    var match = message.match(/^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (OK|VALUE ([^\s]+)|ERR ([A-Z0-9_]+))$/);
    if (!match)
      return true;
    var id = Number(match[1]);
    var pending = this.pending[id];
    if (!pending)
      return true;
    clearTimeout(pending.timer);
    delete this.pending[id];
    if (match[2] === 'OK') {
      pending.resolve(null);
    } else if (match[3] !== undefined) {
      var value = Number(match[3]);
      if (!Number.isFinite(value))
        pending.reject(new Error('Runtime v2 invalid numeric response id=' + id));
      else
        pending.resolve(value);
    } else {
      pending.reject(new RuntimeV2BackendError(match[4]));
    }
    return true;
  };

  RuntimeV2WwiBackend.prototype._guardSimulationStopped = function() {
    return this.simulationStopped ? Promise.reject(new RuntimeV2BackendError('USER_STOPPED')) : null;
  };

  RuntimeV2WwiBackend.prototype.takeoff = function(heightM) { return this._guardSimulationStopped() || this._request(['TAKEOFF', Number(heightM).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.move = function(direction, distanceM) { return this._guardSimulationStopped() || this._request(['MOVE', String(direction), Number(distanceM).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.land = function() { return this._guardSimulationStopped() || this._request(['LAND']); };
  RuntimeV2WwiBackend.prototype.readRange = function(direction) { return this._guardSimulationStopped() || this._request(['RANGE', String(direction)]); };
  RuntimeV2WwiBackend.prototype.stopSimulation = function() {
    if (!this.capabilities || this.capabilities.simulationStop !== true)
      return Promise.reject(new Error('Runtime v2 simulation stop unavailable'));
    this.simulationStopped = true;
    return this._request(['STOP']);
  };
  RuntimeV2WwiBackend.prototype.resetSimulation = function() {
    if (!this.capabilities || this.capabilities.simulationReset !== true)
      return Promise.reject(new Error('Runtime v2 simulation reset unavailable'));
    this._cancelPendingForReset();
    this.ready = false;
    var self = this;
    return this._request(['RESET']).then(function(value) {
      self.ready = true;
      self.simulationStopped = false;
      return value;
    }, function(error) {
      self.ready = true;
      throw error;
    });
  };
  RuntimeV2WwiBackend.prototype.vertical = function() { return Promise.reject(new Error('Runtime v2 Webots backend vertical capability unavailable')); };
  RuntimeV2WwiBackend.prototype.turn = function() { return Promise.reject(new Error('Runtime v2 Webots backend turn capability unavailable')); };
  RuntimeV2WwiBackend.prototype.wait = function() { return Promise.reject(new Error('Runtime v2 Webots backend wait capability unavailable')); };
  RuntimeV2WwiBackend.prototype.setSpeed = function() { return Promise.reject(new Error('Runtime v2 Webots backend speed capability unavailable')); };

  RuntimeV2WwiBackend.BackendError = RuntimeV2BackendError;
  return RuntimeV2WwiBackend;
});
