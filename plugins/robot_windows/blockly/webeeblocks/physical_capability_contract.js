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

  function normalizeDescriptor(value) {
    if (!isObject(value))
      fail('descriptor must be an object');
    if (value.transport !== 'crazyradio')
      fail('unsupported transport: ' + String(value.transport));
    if (value.connected !== true)
      fail('Crazyflie connection is not established');

    requireString(value.device, 'device');
    if (value.device !== 'crazyflie-2.1')
      fail('unsupported device: ' + value.device);

    var hardware = normalizeStringArray(value.hardware, 'hardware');
    if (hardware.indexOf('crazyflie-2.1') < 0)
      fail('hardware must include crazyflie-2.1');

    if (!isObject(value.capabilities))
      fail('capabilities must be an object');

    var descriptor = {
      transport: 'crazyradio',
      connected: true,
      device: 'crazyflie-2.1',
      hardware: hardware,
      capabilities: {
        actions: normalizeStringArray(value.capabilities.actions, 'capabilities.actions'),
        rangeDirections: normalizeStringArray(value.capabilities.rangeDirections, 'capabilities.rangeDirections'),
        moveDirections: normalizeStringArray(value.capabilities.moveDirections, 'capabilities.moveDirections'),
        verticalDirections: normalizeStringArray(value.capabilities.verticalDirections, 'capabilities.verticalDirections')
      }
    };

    return descriptor;
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

  function preflight(profile, facts, descriptorValue) {
    if (!profile || !Array.isArray(profile.hardware))
      fail('profile hardware requirements unavailable');
    if (!facts || !facts.statements || !facts.ranges ||
        !facts.moveDirections || !facts.verticalDirections)
      fail('AST capability facts unavailable');

    var descriptor = normalizeDescriptor(descriptorValue);
    requireSubset(profile.hardware, descriptor.hardware, 'required hardware unavailable: ');

    var actions = descriptor.capabilities.actions;
    facts.statements.forEach(function(kind) {
      if (['takeoff', 'move', 'vertical', 'turn', 'wait', 'set_speed', 'set_light', 'land'].indexOf(kind) >= 0 &&
          actions.indexOf(kind) < 0)
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
