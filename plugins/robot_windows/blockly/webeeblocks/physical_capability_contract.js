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
  var EXACT_AIRFRAME = 'crazyflie-2.1';

  function fail(message) {
    throw new Error('physical capability contract: ' + message);
  }

  function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
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

  function requireSubset(requiredValues, availableValues, messagePrefix) {
    var available = new Set(availableValues || []);
    (requiredValues || []).forEach(function(value) {
      if (!available.has(value))
        fail(messagePrefix + value);
    });
  }

  function requireHardware(profile, descriptor) {
    profile.hardware.forEach(function(requirement) {
      if (requirement === EXACT_AIRFRAME) {
        if (descriptor.identity.modelEvidence !== 'verified' ||
            descriptor.identity.model !== EXACT_AIRFRAME)
          fail('exact physical model evidence unavailable: ' + EXACT_AIRFRAME);
        return;
      }
      if (descriptor.hardware.indexOf(requirement) < 0)
        fail('required hardware unavailable: ' + requirement);
    });
  }

  function preflight(profile, facts, descriptorValue) {
    if (!profile || !Array.isArray(profile.hardware))
      fail('profile hardware requirements unavailable');
    if (!facts || !facts.statements || !facts.ranges ||
        !facts.moveDirections || !facts.verticalDirections)
      fail('AST capability facts unavailable');

    var descriptor = normalizeDescriptor(descriptorValue);
    requireHardware(profile, descriptor);

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

  return {
    normalizeDescriptor: normalizeDescriptor,
    inspect: inspect,
    preflight: preflight,
    FORBIDDEN_AUTHORITY_METHODS: FORBIDDEN_AUTHORITY_METHODS.slice()
  };
});
