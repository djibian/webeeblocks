(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksWwiBackend = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var PREFIX = 'WEBEEBLOCKS_RUNTIME_V2';
  var MISSION_EVALUATION_TYPE = 'mission-state-v1';
  var OUTCOME_STATES = Object.freeze({achieved:true, 'not-achieved':true, interrupted:true});
  var ORACLE_TOKEN = /^[A-Za-z0-9_.-]{1,63}$/;

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
    // World evaluators settle in simulation time. A separate 2 s wall budget
    // incorrectly rejected valid negative results on a slower classroom PC.
    // Keep the same bounded observation budget as other backend operations;
    // only a real exact-attempt/oracle terminal response can supply the result.
    this.outcomeSettleMs = options && Number.isFinite(options.outcomeSettleMs) ? options.outcomeSettleMs : this.timeoutMs;
    this.outcomePollMs = options && Number.isFinite(options.outcomePollMs) ? options.outcomePollMs : 50;
    this.nextId = 1;
    this.timeObservationEpoch = 0;
    this.pending = Object.create(null);
    this.ready = false;
    this.readyWaiters = [];
    this.simulationStopped = false;
    this.completedMissionOracle = null;
    this.failureProbeMissionOracle = null;
    // READY proves liveness, not which scene the surviving controller selected.
    this.sceneIdentity = null;
    this.scenePreparationPending = false;
    var capabilities = {
      conditionalLoops: true,
      procedures: true,
      elapsedSimulationTime: true,
      actions: ['takeoff', 'move', 'vertical', 'turn', 'wait', 'set_speed', 'set_light', 'land'],
      rangeDirections: ['front', 'back', 'left', 'right', 'up'],
      moveDirections: ['forward', 'back', 'left', 'right'],
      verticalDirections: ['up', 'down']
    };
    if (options && options.simulationDebug === true)
      capabilities.simulationDebug = true;
    if (options && options.simulationReset === true)
      capabilities.simulationReset = true;
    if (options && options.simulationStop === true)
      capabilities.simulationStop = true;
    if (options && options.simulationScenes === true)
      capabilities.simulationScenes = true;
    if (options && options.simulationWorldReload === true)
      capabilities.simulationWorldReload = true;
    this.capabilities = Object.freeze(capabilities);
  }

  RuntimeV2WwiBackend.prototype.waitUntilReady = function() {
    if (this.ready)
      return Promise.resolve();
    var self = this;
    return new Promise(function(resolve, reject) {
      var firstWaiter = self.readyWaiters.length === 0;
      var waiter = {resolve: resolve, reject: reject, timer: null};
      waiter.timer = setTimeout(function() {
        var index = self.readyWaiters.indexOf(waiter);
        if (index !== -1)
          self.readyWaiters.splice(index, 1);
        reject(new Error('Runtime v2 READY timeout'));
      }, self.timeoutMs);
      self.readyWaiters.push(waiter);
      if (!firstWaiter)
        return;
      try {
        // READY is normally emitted spontaneously by the controller. The explicit
        // HELLO makes late/early Robot Window attachment deterministic without
        // changing any student-visible action or replaying a program.
        self.robotWindow.send(PREFIX + ' HELLO');
      } catch (error) {
        clearTimeout(waiter.timer);
        var index = self.readyWaiters.indexOf(waiter);
        if (index !== -1)
          self.readyWaiters.splice(index, 1);
        reject(error);
      }
    });
  };

  RuntimeV2WwiBackend.prototype._request = function(parts) {
    var self = this;
    var sceneNonce = null;
    if (parts[0] === 'SCENE' || (parts[0] === 'RESET' && parts.length === 2 && parts[1] === 'CORRELATED')) {
      // Numeric request IDs restart at each Robot Window. A fresh correlation
      // token must survive routing an old connection's ACK to this receiver.
      var bytes = new Uint8Array(32);
      if (!globalThis.crypto || typeof globalThis.crypto.getRandomValues !== 'function')
        return Promise.reject(new Error('Runtime v2 scene correlation unavailable'));
      globalThis.crypto.getRandomValues(bytes);
      sceneNonce = Array.from(bytes, function(b) { return b.toString(16).padStart(2, '0'); }).join('');
      parts = parts[0] === 'RESET' ? ['RESET', sceneNonce] : parts.concat([sceneNonce]);
    }
    if (!Number.isSafeInteger(this.nextId) || this.nextId < 1 || this.nextId > 2147483647)
      return Promise.reject(new RuntimeV2BackendError('REQUEST_ID_EXHAUSTED'));
    var id = this.nextId++;
    return new Promise(function(resolve, reject) {
      var timer = setTimeout(function() {
        if (!self.pending[id]) return;
        delete self.pending[id];
        reject(new Error('Runtime v2 request timeout id=' + id));
      }, self.timeoutMs);
      self.pending[id] = {resolve: resolve, reject: reject, timer: timer, sceneNonce: sceneNonce};
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
    var startupReady = message === PREFIX + ' READY';
    var helloReady = message === PREFIX + ' READY HELLO';
    if (startupReady || helloReady) {
      // A delayed HELLO reply may follow startup READY and even a scene ACK.
      // It only releases an outstanding liveness wait; it cannot revoke or
      // recreate evidence on an already-ready backend or after a cancelled wait.
      if (helloReady && (this.ready || this.readyWaiters.length === 0))
        return true;
      // The native process may have restarted without reloading its world.
      // No scene identity survives that liveness message as positive evidence.
      if (startupReady) {
        this.timeObservationEpoch += 1;
        if (this.ready) this._cancelPendingForReset();
        this.sceneIdentity = null;
      }
      this.ready = true;
      var waiters = this.readyWaiters.splice(0);
      waiters.forEach(function(waiter) {
        clearTimeout(waiter.timer);
        waiter.resolve();
      });
      return true;
    }
    var sceneAck = message.match(/^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) SCENE_OK ([0-9a-f]{64})$/);
    if (sceneAck) {
      var scenePending = this.pending[Number(sceneAck[1])];
      if (scenePending && scenePending.sceneNonce === sceneAck[2]) {
        clearTimeout(scenePending.timer);
        delete this.pending[Number(sceneAck[1])];
        scenePending.resolve(null);
      }
      return true;
    }
    var resetAck = message.match(/^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) RESET_OK ([0-9a-f]{64})$/);
    if (resetAck) {
      var resetPending = this.pending[Number(resetAck[1])];
      if (resetPending && resetPending.sceneNonce === resetAck[2]) {
        clearTimeout(resetPending.timer);
        delete this.pending[Number(resetAck[1])];
        resetPending.resolve(null);
      }
      return true;
    }
    var match = message.match(/^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (OK|VALUE ([^\s]+)|STATE ([A-Za-z-]+)|ERR ([A-Z0-9_]+))$/);
    if (!match)
      return true;
    var id = Number(match[1]);
    var pending = this.pending[id];
    if (!pending)
      return true;
    if (pending.sceneNonce && match[2] === 'OK')
      return true; // A legacy/other connection's ACK cannot confirm a scene or recovery RESET.
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
    } else if (match[4] !== undefined) {
      if (!Object.prototype.hasOwnProperty.call(OUTCOME_STATES, match[4]))
        pending.reject(new Error('Runtime v2 invalid activity outcome state id=' + id));
      else
        pending.resolve(match[4]);
    } else {
      pending.reject(new RuntimeV2BackendError(match[5]));
    }
    return true;
  };

  RuntimeV2WwiBackend.prototype._guardSimulationStopped = function() {
    return this.simulationStopped ? Promise.reject(new RuntimeV2BackendError('USER_STOPPED')) : null;
  };

  RuntimeV2WwiBackend.prototype._missionOracle = function(evaluation) {
    if (!evaluation || evaluation.type !== MISSION_EVALUATION_TYPE)
      throw new Error('Runtime v2 unsupported activity outcome evaluation');
    var oracle = evaluation.oracle;
    if (typeof oracle !== 'string' || !ORACLE_TOKEN.test(oracle))
      throw new Error('Runtime v2 invalid activity outcome oracle');
    return oracle;
  };

  RuntimeV2WwiBackend.prototype.takeoff = function(heightM) { this.timeObservationEpoch += 1; return this._guardSimulationStopped() || this._request(['TAKEOFF', Number(heightM).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.prepareActivity = function(profile) {
    if (!this.capabilities.simulationScenes)
      return Promise.reject(new Error('Runtime v2 simulation scenes unavailable'));
    var stopped = this._guardSimulationStopped();
    if (stopped) return stopped;
    if (this.scenePreparationPending)
      return Promise.reject(new RuntimeV2BackendError('SCENE_BUSY'));
    // A profile declares its scene; an unknown activity must never silently
    // fall back to the obstacle-filled legacy scene.
    var scene = profile && profile.runtime && profile.runtime.scene;
    if (scene !== 'sequence-v1' && scene !== 'legacy-v1')
      return Promise.reject(new RuntimeV2BackendError('SCENE_UNAVAILABLE'));
    if (this.sceneIdentity === scene) return Promise.resolve();
    this.sceneIdentity = null; // An unknown import outcome must be reconstructed.
    this.scenePreparationPending = true;
    var self = this, epoch = this.timeObservationEpoch;
    return this._request(['SCENE', scene]).then(function(value) {
      if (epoch !== self.timeObservationEpoch)
        throw new RuntimeV2BackendError('RESET_CANCELLED');
      if (value !== null) throw new Error('Runtime v2 invalid scene acknowledgement');
      self.sceneIdentity = scene;
      return value;
    }).finally(function() { self.scenePreparationPending = false; });
  };
  RuntimeV2WwiBackend.prototype.move = function(direction, distanceM) { return this._guardSimulationStopped() || this._request(['MOVE', String(direction), Number(distanceM).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.vertical = function(direction, distanceM) { return this._guardSimulationStopped() || this._request(['VERTICAL', String(direction), Number(distanceM).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.turn = function(angleDeg) { return this._guardSimulationStopped() || this._request(['TURN', Number(angleDeg).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.wait = function(seconds) { return this._guardSimulationStopped() || this._request(['WAIT', Number(seconds).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.setSpeed = function(speedMps) { return this._guardSimulationStopped() || this._request(['SPEED', Number(speedMps).toPrecision(17)]); };
  RuntimeV2WwiBackend.prototype.setLight = function(color) { return this._guardSimulationStopped() || this._request(['LIGHT', String(color)]); };
  RuntimeV2WwiBackend.prototype.land = function() { this.timeObservationEpoch += 1; return this._guardSimulationStopped() || this._request(['LAND']); };
  RuntimeV2WwiBackend.prototype.readElapsedTime = function() {
    var stopped = this._guardSimulationStopped();
    if (stopped) return stopped;
    var self = this, epoch = this.timeObservationEpoch;
    return this._request(['ELAPSED']).then(function(value) {
      if (epoch !== self.timeObservationEpoch) throw new RuntimeV2BackendError('TIME_UNAVAILABLE');
      if (typeof value !== 'number' || !Number.isFinite(value) || value < 0)
        throw new Error('Runtime v2 invalid elapsed time response');
      return value;
    });
  };
  RuntimeV2WwiBackend.prototype.readRange = function(direction) { return this._guardSimulationStopped() || this._request(['RANGE', String(direction)]); };
  RuntimeV2WwiBackend.prototype.completeActivityMission = function(evaluation) {
    var oracle;
    try { oracle = this._missionOracle(evaluation); }
    catch (error) { return Promise.reject(error); }
    var stopped = this._guardSimulationStopped();
    if (stopped) return stopped;
    var self = this;
    return this._request(['COMPLETE', oracle]).then(function(value) {
      self.completedMissionOracle = oracle;
      self.failureProbeMissionOracle = null;
      return value;
    });
  };
  RuntimeV2WwiBackend.prototype.probeActivityMissionFailure = function(evaluation) {
    var oracle;
    try { oracle = this._missionOracle(evaluation); }
    catch (error) { return Promise.reject(error); }
    var stopped = this._guardSimulationStopped();
    if (stopped) return stopped;
    var self = this;
    return this._request(['FAILURE', oracle]).then(function(value) {
      self.failureProbeMissionOracle = oracle;
      return value;
    });
  };
  RuntimeV2WwiBackend.prototype.readActivityOutcome = function(evaluation) {
    var oracle;
    try { oracle = this._missionOracle(evaluation); }
    catch (error) { return Promise.reject(error); }
    var stopped = this._guardSimulationStopped();
    if (stopped) return stopped;
    var self = this;
    function requestOnce() {
      return self._request(['OUTCOME', oracle]).then(function(status) {
        if (!Object.prototype.hasOwnProperty.call(OUTCOME_STATES, status))
          throw new Error('Runtime v2 invalid activity outcome state');
        return {status: status};
      });
    }
    if (this.completedMissionOracle !== oracle && this.failureProbeMissionOracle !== oracle)
      return requestOnce();
    var deadline = Date.now() + Math.max(0, this.outcomeSettleMs);
    function poll() {
      return requestOnce().catch(function(error) {
        if (!(error && error.code === 'OUTCOME_UNAVAILABLE') || Date.now() >= deadline)
          throw error;
        return new Promise(function(resolve) {
          setTimeout(resolve, Math.max(0, self.outcomePollMs));
        }).then(poll);
      });
    }
    return poll();
  };
  RuntimeV2WwiBackend.prototype.stopSimulation = function() {
    if (!this.capabilities || this.capabilities.simulationStop !== true)
      return Promise.reject(new Error('Runtime v2 simulation stop unavailable'));
    this.timeObservationEpoch += 1;
    this.simulationStopped = true;
    this.sceneIdentity = null;
    return this._request(['STOP']);
  };
  RuntimeV2WwiBackend.prototype.resetSimulation = function(correlated) {
    if (!this.capabilities || this.capabilities.simulationReset !== true)
      return Promise.reject(new Error('Runtime v2 simulation reset unavailable'));
    this.timeObservationEpoch += 1;
    this.sceneIdentity = null;
    this._cancelPendingForReset();
    this.completedMissionOracle = null;
    this.failureProbeMissionOracle = null;
    this.ready = false;
    var self = this;
    return this._request(correlated === true ? ['RESET', 'CORRELATED'] : ['RESET']).then(function(value) {
      self.ready = true;
      self.simulationStopped = false;
      return value;
    }, function(error) {
      self.ready = true;
      throw error;
    });
  };

  // Irreversible one-way request: never acknowledge recovery on the OLD world.
  // The new Robot Window must independently validate strict RESET and scene.
  RuntimeV2WwiBackend.prototype.requestWorldReload = function() {
    if (!this.capabilities || this.capabilities.simulationWorldReload !== true)
      throw new Error('Runtime v2 world reload unavailable');
    this.timeObservationEpoch += 1;
    this.sceneIdentity = null;
    this._cancelPendingForReset();
    this.ready = false;
    this.simulationStopped = true;
    this.robotWindow.send(PREFIX + ' RELOAD_WORLD');
  };

  RuntimeV2WwiBackend.BackendError = RuntimeV2BackendError;
  return RuntimeV2WwiBackend;
});
