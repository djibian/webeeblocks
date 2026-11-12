(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksExecutionObserver = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function fail(message) { throw new Error('execution observer: ' + message); }
  function key(path) { return (path || []).map(String).join('/'); }

  function rejectCancelledExecution() {
    var error = new Error('Step debugger cancelled by STOP');
    error.code = 'USER_STOPPED';
    throw error;
  }

  function buildSourceMap(workspace) {
    if (!workspace || typeof workspace.getTopBlocks !== 'function')
      fail('invalid Blockly workspace');
    var definitions = new Map();
    var tops = workspace.getTopBlocks(true).filter(function(block) {
      if (block.type !== 'procedures_defnoreturn') return true;
      var name = String(block.getProcedureDef()[0]).trim().toLowerCase();
      if (definitions.has(name)) fail('duplicate procedure');
      definitions.set(name, block);
      return false;
    });
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
      if (block.type === 'logic_compare' || block.type === 'logic_operation' || block.type === 'math_arithmetic') {
        expression(block.getInputTargetBlock('A'), path.concat('left'));
        expression(block.getInputTargetBlock('B'), path.concat('right'));
      }
    }

    var expanded = 0;
    function sequence(first, prefix, calls) {
      var block = first;
      var index = 0;
      var guard = 0;
      while (block) {
        guard += 1;
        if (guard > 200) fail('program too large');
        if (++expanded > 2000 || prefix.length > 60) fail('procedure source map too large');
        var path = prefix.concat(index);
        remember(block, path);
        if (block.type === 'procedures_callnoreturn') {
          var name = String(block.getProcedureCall()).trim().toLowerCase();
          if (!definitions.has(name) || calls.indexOf(name) >= 0) fail('invalid procedure call');
          sequence(definitions.get(name).getInputTargetBlock('STACK'), path.concat('body'), calls.concat(name));
        } else if (block.type === 'controls_whileUntil' || block.type === 'webeeblocks_v2_until') {
          expression(block.getInputTargetBlock('BOOL'), path.concat('condition'));
          sequence(block.getInputTargetBlock('DO'), path.concat('body'), calls);
        } else if (block.type === 'controls_repeat_ext') {
          sequence(block.getInputTargetBlock('DO'), path.concat('body'), calls);
        } else if (block.type === 'controls_if') {
          var armPath = path;
          for (var arm = 0; arm <= (block.elseifCount_ || 0); arm++) {
            // AST v1 lowers IF1/DO1 to if inside else[0], same visible Blockly ID.
            if (arm) {
              armPath = armPath.concat('else', 0);
              remember(block, armPath);
            }
            expression(block.getInputTargetBlock('IF' + arm), armPath.concat('condition'));
            sequence(block.getInputTargetBlock('DO' + arm), armPath.concat('then'), calls);
          }
          if (block.getInputTargetBlock('ELSE'))
            sequence(block.getInputTargetBlock('ELSE'), armPath.concat('else'), calls);
        } else if (block.type === 'webeeblocks_v2_takeoff') {
          expression(block.getInputTargetBlock('HEIGHT'),path.concat('height_m'));
        } else if (block.type === 'webeeblocks_v2_move'||block.type === 'webeeblocks_v2_vertical') {
          expression(block.getInputTargetBlock('DISTANCE'),path.concat('distance_m'));
        } else if (block.type === 'variables_set') {
          expression(block.getInputTargetBlock('VALUE'), path.concat('value'));
        } else if (block.type === 'math_change') {
          remember(block, path.concat('value'));
          remember(block, path.concat('value', 'left'));
          expression(block.getInputTargetBlock('DELTA'), path.concat('value', 'right'));
        }
        block = typeof block.getNextBlock === 'function' ? block.getNextBlock() : null;
        index += 1;
      }
    }

    sequence(tops[0], ['program'], []);
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
    // UI-only state: block IDs are never stored in the AST or a .wbb.
    this.breakpoints = new Set();
    this.skipBeforeStep = Object.create(null);
    this.cancelled = false;
    this.sensorValues = Object.create(null);
    this.lightColor = 'off';
    var self = this;
    this.hooks = {
      onNode: function(context) { return self._onNode(context); },
      beforeStep: function(context) { return self._beforeStep(context); },
      onSensor: function(context) { return self._onSensor(context); },
      onLight: function(context) { return self._onLight(context); },
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

  Controller.prototype._markBreakpoint = function(id, marked) {
    var block = this.workspace && this.workspace.getBlockById && this.workspace.getBlockById(id);
    var svg = block && typeof block.getSvgRoot === 'function' && block.getSvgRoot();
    if (svg && svg.classList) svg.classList.toggle('webeeblocks-breakpoint', marked);
  };

  Controller.prototype.hasBreakpoint = function(id) {
    return this.breakpoints.has(String(id));
  };

  Controller.prototype.toggleBreakpoint = function(id) {
    id = String(id);
    var block = this.workspace && this.workspace.getBlockById && this.workspace.getBlockById(id);
    if (!block || block.type === 'procedures_defnoreturn' || block.workspace !== this.workspace)
      return false;
    if (this.breakpoints.has(id)) this.breakpoints.delete(id);
    else this.breakpoints.add(id);
    this._markBreakpoint(id, this.breakpoints.has(id));
    return true;
  };

  Controller.prototype.clearBreakpoints = function() {
    var self = this;
    this.breakpoints.forEach(function(id) { self._markBreakpoint(id, false); });
    this.breakpoints.clear();
  };

  Controller.prototype.pruneBreakpoints = function() {
    var self = this;
    this.breakpoints.forEach(function(id) {
      if (!self.workspace || !self.workspace.getBlockById(id)) self.breakpoints.delete(id);
    });
  };

  // An else-if arm lowered by AST v1 is a new AST "if" but the SAME Blockly block.
  // Do not stop twice inside a single visible conditional on Continue.
  Controller.prototype._syntheticElseIf = function(context) {
    var path = context && context.path;
    return !!(context && context.node && context.node.kind === 'if' &&
      Array.isArray(path) && path.length >= 2 &&
      path[path.length - 2] === 'else' && path[path.length - 1] === 0 &&
      this._blockId(path) === this._blockId(path.slice(0, -2)));
  };

  Controller.prototype._pause = async function(detail, reason) {
    var self = this, waiter;
    var pending = new Promise(function(resolve, reject) {
      waiter = {resolve: resolve, reject: reject, context: detail};
    });
    this.waiter = waiter;
    try {
      if (typeof this.callbacks.onPause === 'function')
        this.callbacks.onPause(Object.assign({}, detail, {reason: reason}));
      await pending;
      if (this.cancelled) {
        var error = new Error('Step debugger cancelled by STOP');
        error.code = 'USER_STOPPED';
        throw error;
      }
      if (typeof this.callbacks.onResume === 'function')
        this.callbacks.onResume(detail);
    } finally {
      if (this.waiter === waiter) this.waiter = null;
    }
  };

  Controller.prototype.begin = function(enabled) {
    this.finish();
    this.sourceMap = Object.create(null);
    this.sourceMapReady = false;
    this.enabled = enabled === true;
    this.continuous = !this.enabled;
    this.credit = 0;
    this.skipBeforeStep = Object.create(null);
    this.cancelled = false;
    this.pruneBreakpoints();
    this.sensorValues = Object.create(null);
    this.lightColor = 'off';
    if (typeof this.callbacks.onBegin === 'function')
      this.callbacks.onBegin({enabled: this.enabled});
    return this.hooks;
  };

  Controller.prototype._onNode = async function(context) {
    // Check before enabled: a late interpreter hook must fail closed after STOP.
    if (this.cancelled) rejectCancelledExecution();
    if (!this.enabled) return;
    // Re-entering this AST site after a loop/call invalidates any prior
    // unconsumed beforeStep credit (e.g. a loop with no body iteration).
    delete this.skipBeforeStep[key(context.path)];
    if (!this.sourceMapReady) {
      this.sourceMap = buildSourceMap(this.workspace);
      this.sourceMapReady = true;
    }
    var detail = this._detail(context);
    if (typeof this.callbacks.onActive === 'function')
      this.callbacks.onActive(detail);
    if (this.continuous && detail.blockId && this.breakpoints.has(detail.blockId) &&
        !this._syntheticElseIf(context)) {
      this.continuous = false;
      await this._pause(detail, 'breakpoint');
      // The block may later also fire beforeStep (after evaluating operands).
      // Consume precisely that one hook, not the next loop iteration/call.
      this.skipBeforeStep[key(context.path)] = true;
    }
  };

  Controller.prototype._beforeStep = async function(context) {
    if (this.cancelled) rejectCancelledExecution();
    if (!this.enabled) return;
    var path = key(context.path);
    if (this.skipBeforeStep[path]) {
      delete this.skipBeforeStep[path];
      return;
    }
    var detail = this._detail(context);
    if (this.continuous &&
        (!detail.blockId || !this.breakpoints.has(detail.blockId) ||
         this._syntheticElseIf(context))) return;
    if (this.continuous) this.continuous = false;
    if (typeof this.callbacks.onActive === 'function')
      this.callbacks.onActive(detail);
    if (this.credit > 0) {
      this.credit -= 1;
      if (typeof this.callbacks.onResume === 'function')
        this.callbacks.onResume(detail);
      return;
    }
    await this._pause(detail, this.breakpoints.has(detail.blockId) ? 'breakpoint' : 'step');
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

  Controller.prototype._onLight = async function(context) {
    if (!this.enabled || !context || typeof context.color !== 'string') return;
    this.lightColor = String(context.color);
    var detail = Object.assign({}, context, {
      blockId: this._blockId(context.path),
      color: this.lightColor
    });
    if (typeof this.callbacks.onLight === 'function')
      this.callbacks.onLight(detail);
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

  Controller.prototype.cancel = function() {
    if (!this.enabled) return false;
    this.cancelled = true;
    this.continuous = true;
    this.credit = 0;
    if (this.waiter) {
      var error = new Error('Step debugger interrupted by STOP');
      error.code = 'USER_STOPPED';
      this.waiter.reject(error);
    }
    return true;
  };

  Controller.prototype.finish = function() {
    if (this.waiter) this.waiter.resolve();
    this.waiter = null;
    this.credit = 0;
    this.skipBeforeStep = Object.create(null);
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
