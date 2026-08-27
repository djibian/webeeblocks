(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksExecutionObserver = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function fail(message) { throw new Error('execution observer: ' + message); }
  function key(path) { return (path || []).map(String).join('/'); }

  function buildSourceMap(workspace) {
    if (!workspace || typeof workspace.getTopBlocks !== 'function')
      fail('invalid Blockly workspace');
    var tops = workspace.getTopBlocks(true);
    if (tops.length !== 1)
      fail('Crazyflie program must have exactly one top-level sequence');
    var map = Object.create(null);

    function remember(block, path) {
      if (!block || !block.id) fail('Blockly block without id');
      map[key(path)] = String(block.id);
    }

    function expression(block, path) {
      if (!block) return;
      remember(block, path);
      if (block.type === 'logic_compare' || block.type === 'logic_operation') {
        expression(block.getInputTargetBlock('A'), path.concat('left'));
        expression(block.getInputTargetBlock('B'), path.concat('right'));
      }
    }

    function sequence(first, prefix) {
      var block = first;
      var index = 0;
      var guard = 0;
      while (block) {
        guard += 1;
        if (guard > 200) fail('program too large');
        var path = prefix.concat(index);
        remember(block, path);
        if (block.type === 'controls_repeat_ext') {
          sequence(block.getInputTargetBlock('DO'), path.concat('body'));
        } else if (block.type === 'controls_if') {
          expression(block.getInputTargetBlock('IF0'), path.concat('condition'));
          sequence(block.getInputTargetBlock('DO0'), path.concat('then'));
          if (block.getInputTargetBlock('ELSE'))
            sequence(block.getInputTargetBlock('ELSE'), path.concat('else'));
        }
        block = typeof block.getNextBlock === 'function' ? block.getNextBlock() : null;
        index += 1;
      }
    }

    sequence(tops[0], ['program']);
    return map;
  }

  function Controller(workspace, callbacks) {
    this.workspace = workspace;
    this.callbacks = callbacks || {};
    this.sourceMap = Object.create(null);
    this.sourceMapReady = false;
    this.enabled = false;
    this.continuous = true;
    this.waiter = null;
    this.credit = 0;
    this.sensorValues = Object.create(null);
    var self = this;
    this.hooks = {
      onNode: function(context) { return self._onNode(context); },
      beforeStep: function(context) { return self._beforeStep(context); },
      onSensor: function(context) { return self._onSensor(context); },
      onVariables: function(context) { return self._onVariables(context); }
    };
  }

  Controller.prototype._blockId = function(path) {
    return this.sourceMap[key(path)] || null;
  };

  Controller.prototype._detail = function(context) {
    var detail = Object.assign({}, context, {blockId: this._blockId(context.path)});
    if (detail.blockId && this.workspace && typeof this.workspace.highlightBlock === 'function')
      this.workspace.highlightBlock(detail.blockId);
    return detail;
  };

  Controller.prototype.begin = function(enabled) {
    this.finish();
    this.sourceMap = Object.create(null);
    this.sourceMapReady = false;
    this.enabled = enabled === true;
    this.continuous = !this.enabled;
    this.credit = 0;
    this.sensorValues = Object.create(null);
    if (typeof this.callbacks.onBegin === 'function')
      this.callbacks.onBegin({enabled: this.enabled});
    return this.hooks;
  };

  Controller.prototype._onNode = async function(context) {
    if (!this.enabled) return;
    if (!this.sourceMapReady) {
      this.sourceMap = buildSourceMap(this.workspace);
      this.sourceMapReady = true;
    }
    var detail = this._detail(context);
    if (typeof this.callbacks.onActive === 'function')
      this.callbacks.onActive(detail);
  };

  Controller.prototype._beforeStep = async function(context) {
    if (!this.enabled || this.continuous) return;
    var detail = this._detail(context);
    if (typeof this.callbacks.onActive === 'function')
      this.callbacks.onActive(detail);
    if (this.credit > 0) {
      this.credit -= 1;
      if (typeof this.callbacks.onResume === 'function')
        this.callbacks.onResume(detail);
      return;
    }
    var self = this;
    if (typeof this.callbacks.onPause === 'function')
      this.callbacks.onPause(detail);
    await new Promise(function(resolve) {
      self.waiter = {resolve: resolve, context: detail};
    });
    self.waiter = null;
    if (typeof this.callbacks.onResume === 'function')
      this.callbacks.onResume(detail);
  };

  Controller.prototype._onSensor = async function(context) {
    if (!this.enabled) return;
    this.sensorValues[String(context.direction)] = context.value;
    var detail = Object.assign({}, context, {
      blockId: this._blockId(context.path),
      values: Object.assign({}, this.sensorValues)
    });
    if (typeof this.callbacks.onSensor === 'function')
      this.callbacks.onSensor(detail);
  };

  Controller.prototype._onVariables = async function(context) {
    if (!this.enabled || !context || !context.values) return;
    if (typeof this.callbacks.onVariables === 'function')
      this.callbacks.onVariables(context);
  };

  Controller.prototype.next = function() {
    if (!this.enabled || this.continuous) return false;
    if (this.waiter) {
      this.waiter.resolve();
      return true;
    }
    this.credit = 1;
    return true;
  };

  Controller.prototype.continueRun = function() {
    if (!this.enabled) return false;
    this.continuous = true;
    this.credit = 0;
    if (this.waiter) this.waiter.resolve();
    return true;
  };

  Controller.prototype.finish = function() {
    if (this.waiter) this.waiter.resolve();
    this.waiter = null;
    this.credit = 0;
    this.continuous = true;
    if (this.enabled && this.workspace && typeof this.workspace.highlightBlock === 'function')
      this.workspace.highlightBlock(null);
    if (this.enabled && typeof this.callbacks.onFinish === 'function')
      this.callbacks.onFinish();
    this.enabled = false;
  };

  return {
    buildSourceMap: buildSourceMap,
    create: function(workspace, callbacks) { return new Controller(workspace, callbacks); }
  };
});
