(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksPhysicalCapabilityContract = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var FORBIDDEN_AUTHORITY_METHODS = [
    'takeoff', 'land', 'move', 'vertical', 'turn', 'wait', 'setSpeed',
    'setLight', 'arm', 'disarm', 'startMotors', 'stopMotors', 'setpoint',
    'sendSetpoint', 'thrust'
  ];
  var ACTION_KINDS = ['takeoff', 'move', 'vertical', 'turn', 'wait', 'set_speed', 'set_light', 'land'];
  var CAPABILITY_DEPENDENT_HARDWARE = ['flow-deck-v2', 'multi-ranger-deck', 'color-led-deck'];
  var EXACT_AIRFRAME = 'crazyflie-2.1';

  function fail(message) {
    throw new Error('physical capability contract: ' + message);
  }

  function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function canonicalJson(value, path, depth) {
    path = path || 'value';
    depth = depth || 0;
    if (depth > 100)
      fail(path + ' nesting is too deep');
    if (value === null || typeof value === 'string' || typeof value === 'boolean')
      return JSON.stringify(value);
    if (typeof value === 'number') {
      if (!Number.isFinite(value))
        fail(path + ' contains a non-finite number');
      return JSON.stringify(value);
    }
    if (Array.isArray(value))
      return '[' + value.map(function(item, index) {
        return canonicalJson(item, path + '[' + index + ']', depth + 1);
      }).join(',') + ']';
    if (isObject(value)) {
      return '{' + Object.keys(value).sort().map(function(key) {
        return JSON.stringify(key) + ':' + canonicalJson(value[key], path + '.' + key, depth + 1);
      }).join(',') + '}';
    }
    fail(path + ' contains a non-JSON value');
  }

  function bindAst(ast) {
    if (!isObject(ast) || ast.version !== 1 || ast.semantics !== 'webeeblocks-ast-v1')
      fail('unsupported or malformed backend-neutral AST');
    return canonicalJson(ast, 'AST', 0);
  }

  function requireString(value, path) {
    if (typeof value !== 'string' || value.trim() === '')
      fail(path + ' must be a non-empty string');
  }

  function normalizeStringArray(value, path) {
    if (!Array.isArray(value))
      fail(path + ' must be an array');
    var seen = Object.create(null);
    return value.map(function(item, index) {
      requireString(item, path + '[' + index + ']');
      if (seen[item])
        fail(path + ' contains duplicate value: ' + item);
      seen[item] = true;
      return item;
    });
  }

  function normalizeIdentity(value) {
    if (!isObject(value))
      fail('identity must be an object');
    if (value.family !== 'crazyflie')
      fail('unsupported device family: ' + String(value.family));
    if (value.modelEvidence !== 'unproven' && value.modelEvidence !== 'verified')
      fail('identity.modelEvidence must be unproven or verified');

    if (value.modelEvidence === 'unproven') {
      if (value.model !== null)
        fail('unproven exact model must be null');
      return {family: 'crazyflie', model: null, modelEvidence: 'unproven'};
    }

    requireString(value.model, 'identity.model');
    return {family: 'crazyflie', model: value.model, modelEvidence: 'verified'};
  }

  function normalizeDescriptor(value) {
    if (!isObject(value))
      fail('descriptor must be an object');
    if (value.transport !== 'crazyradio')
      fail('unsupported transport: ' + String(value.transport));
    if (value.connected !== true)
      fail('Crazyflie connection is not established');
    if (value.executionAuthority !== false)
      fail('read-only descriptor must declare executionAuthority=false');

    var identity = normalizeIdentity(value.identity);
    var hardware = normalizeStringArray(value.hardware, 'hardware');
    if (hardware.indexOf(EXACT_AIRFRAME) >= 0)
      fail('exact airframe identity must not be encoded as generic hardware evidence');

    if (!isObject(value.capabilities))
      fail('capabilities must be an object');

    return {
      transport: 'crazyradio',
      connected: true,
      executionAuthority: false,
      identity: identity,
      hardware: hardware,
      capabilities: {
        actions: normalizeStringArray(value.capabilities.actions, 'capabilities.actions'),
        rangeDirections: normalizeStringArray(value.capabilities.rangeDirections, 'capabilities.rangeDirections'),
        moveDirections: normalizeStringArray(value.capabilities.moveDirections, 'capabilities.moveDirections'),
        verticalDirections: normalizeStringArray(value.capabilities.verticalDirections, 'capabilities.verticalDirections')
      }
    };
  }

  function assertReadOnlyAdapter(adapter) {
    if (!adapter || typeof adapter.readCapabilities !== 'function')
      fail('adapter.readCapabilities is required');

    FORBIDDEN_AUTHORITY_METHODS.forEach(function(name) {
      if (typeof adapter[name] === 'function')
        fail('read-only adapter exposes forbidden authority method: ' + name);
    });
  }

  async function inspect(adapter) {
    assertReadOnlyAdapter(adapter);
    return normalizeDescriptor(await adapter.readCapabilities());
  }

  async function preflightConnected(profile, ast, adapter) {
    var descriptor = await inspect(adapter);
    return preflightAst(profile, ast, descriptor);
  }

  function requireSubset(requiredValues, availableValues, messagePrefix) {
    var available = new Set(availableValues || []);
    (requiredValues || []).forEach(function(value) {
      if (!available.has(value))
        fail(messagePrefix + value);
    });
  }

  function requireExactAirframe(profile, descriptor) {
    if (profile.hardware.indexOf(EXACT_AIRFRAME) < 0)
      fail('profile exact physical model requirement unavailable: ' + EXACT_AIRFRAME);
    if (descriptor.identity.modelEvidence !== 'verified' ||
        descriptor.identity.model !== EXACT_AIRFRAME)
      fail('exact physical model evidence unavailable: ' + EXACT_AIRFRAME);
  }

  function preflight(profile, facts, descriptorValue) {
    if (!profile || !Array.isArray(profile.hardware))
      fail('profile hardware requirements unavailable');
    if (!facts || !facts.statements || !facts.ranges ||
        !facts.moveDirections || !facts.verticalDirections)
      fail('AST capability facts unavailable');

    var descriptor = normalizeDescriptor(descriptorValue);
    requireExactAirframe(profile, descriptor);

    var actions = descriptor.capabilities.actions;
    facts.statements.forEach(function(kind) {
      if (ACTION_KINDS.indexOf(kind) >= 0 && actions.indexOf(kind) < 0)
        fail('physical action capability unavailable: ' + kind);
    });
    requireSubset(Array.from(facts.ranges), descriptor.capabilities.rangeDirections,
      'physical range capability unavailable: ');
    requireSubset(Array.from(facts.moveDirections), descriptor.capabilities.moveDirections,
      'physical move direction unavailable: ');
    requireSubset(Array.from(facts.verticalDirections), descriptor.capabilities.verticalDirections,
      'physical vertical direction unavailable: ');

    return true;
  }

  function newFacts() {
    return {
      statements: new Set(),
      ranges: new Set(),
      moveDirections: new Set(),
      verticalDirections: new Set()
    };
  }

  function visitExpression(expression, facts) {
    if (!isObject(expression) || typeof expression.kind !== 'string')
      fail('malformed AST expression');
    if (expression.kind === 'number' || expression.kind === 'variable_get')
      return;
    if (expression.kind === 'range') {
      requireString(expression.direction, 'AST range direction');
      facts.ranges.add(expression.direction);
      return;
    }
    if (expression.kind === 'arithmetic' || expression.kind === 'compare' || expression.kind === 'logic') {
      visitExpression(expression.left, facts);
      visitExpression(expression.right, facts);
      return;
    }
    fail('unsupported AST expression kind: ' + expression.kind);
  }

  function visitSequence(sequence, facts) {
    if (!Array.isArray(sequence))
      fail('AST statement sequence must be an array');
    sequence.forEach(function(statement) {
      if (!isObject(statement) || typeof statement.kind !== 'string')
        fail('malformed AST statement');
      var kind = statement.kind;
      facts.statements.add(kind);
      if (ACTION_KINDS.indexOf(kind) >= 0) {
        if (kind === 'move') {
          requireString(statement.direction, 'AST move direction');
          facts.moveDirections.add(statement.direction);
        } else if (kind === 'vertical') {
          requireString(statement.direction, 'AST vertical direction');
          facts.verticalDirections.add(statement.direction);
        }
        return;
      }
      if (kind === 'set_variable') {
        visitExpression(statement.value, facts);
        return;
      }
      if (kind === 'repeat') {
        visitSequence(statement.body, facts);
        return;
      }
      if (kind === 'if') {
        visitExpression(statement.condition, facts);
        visitSequence(statement.then, facts);
        if (statement.else !== undefined)
          visitSequence(statement.else, facts);
        return;
      }
      fail('unsupported AST statement kind: ' + kind);
    });
  }

  function deriveFacts(ast) {
    if (!isObject(ast) || ast.version !== 1 || ast.semantics !== 'webeeblocks-ast-v1')
      fail('unsupported or malformed backend-neutral AST');
    var facts = newFacts();
    visitSequence(ast.program, facts);
    return facts;
  }

  function requireUnconditionalHardware(profile, descriptor) {
    var explicit = profile.physicalHardwareRequired;
    if (explicit !== undefined)
      explicit = normalizeStringArray(explicit, 'physicalHardwareRequired');
    else
      explicit = profile.hardware.filter(function(requirement) {
        return requirement !== EXACT_AIRFRAME && CAPABILITY_DEPENDENT_HARDWARE.indexOf(requirement) < 0;
      });
    explicit.forEach(function(requirement) {
      if (requirement === EXACT_AIRFRAME) {
        requireExactAirframe(profile, descriptor);
      } else if (descriptor.hardware.indexOf(requirement) < 0) {
        fail('required hardware unavailable: ' + requirement);
      }
    });
  }

  function detectedSummary(descriptor) {
    return 'matériel détecté: ' + (descriptor.hardware.length ? descriptor.hardware.join(', ') : 'aucun deck compatible') +
      '; actions: ' + (descriptor.capabilities.actions.length ? descriptor.capabilities.actions.join(', ') : 'aucune') +
      '; distances: ' + (descriptor.capabilities.rangeDirections.length ? descriptor.capabilities.rangeDirections.join(', ') : 'aucune');
  }

  function compatibilityError(error, descriptor) {
    var wrapped = new Error('physical capability preflight: ' + error.message);
    wrapped.code = 'PHYSICAL_CAPABILITY_MISMATCH';
    wrapped.studentDetail = 'Le programme n’a pas été envoyé au Crazyflie : ' +
      error.message.replace(/^physical capability contract: /, '') + '. ' + detectedSummary(descriptor) + '.';
    return wrapped;
  }

  function preflightAst(profile, ast, descriptorValue) {
    if (!profile || !Array.isArray(profile.hardware))
      fail('profile hardware requirements unavailable');
    var descriptor = normalizeDescriptor(descriptorValue);
    var facts = deriveFacts(ast);
    var astBinding = bindAst(ast);
    try {
      requireExactAirframe(profile, descriptor);
      requireUnconditionalHardware(profile, descriptor);
      var actions = descriptor.capabilities.actions;
      facts.statements.forEach(function(kind) {
        if (ACTION_KINDS.indexOf(kind) >= 0 && actions.indexOf(kind) < 0)
          fail('physical action capability unavailable: ' + kind);
      });
      requireSubset(Array.from(facts.ranges), descriptor.capabilities.rangeDirections,
        'physical range capability unavailable: ');
      requireSubset(Array.from(facts.moveDirections), descriptor.capabilities.moveDirections,
        'physical move direction unavailable: ');
      requireSubset(Array.from(facts.verticalDirections), descriptor.capabilities.verticalDirections,
        'physical vertical direction unavailable: ');
    } catch (error) {
      throw compatibilityError(error, descriptor);
    }
    return {
      compatible: true,
      executionAuthority: false,
      astBinding: astBinding,
      facts: facts,
      descriptor: descriptor
    };
  }

  function assertPreflightAst(preflightResult, ast) {
    if (!isObject(preflightResult) || preflightResult.compatible !== true ||
        preflightResult.executionAuthority !== false || typeof preflightResult.astBinding !== 'string')
      fail('valid non-authority physical preflight result required');
    if (bindAst(ast) !== preflightResult.astBinding)
      fail('submitted AST differs from preflighted AST');
    return true;
  }

  return {
    normalizeDescriptor: normalizeDescriptor,
    inspect: inspect,
    preflight: preflight,
    deriveFacts: deriveFacts,
    bindAst: bindAst,
    preflightAst: preflightAst,
    preflightConnected: preflightConnected,
    assertPreflightAst: assertPreflightAst,
    FORBIDDEN_AUTHORITY_METHODS: FORBIDDEN_AUTHORITY_METHODS.slice()
  };
});
