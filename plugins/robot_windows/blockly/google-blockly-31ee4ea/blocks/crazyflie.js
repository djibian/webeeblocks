// Minimal Crazyflie student blocks for the first WebeeBlocks semantic mission gate.
// Blockly remains a block-only UI; this file does not generate or expose Python.

Blockly.Blocks['webeeblocks_takeoff'] = {
  init: function() {
    this.appendDummyInput().appendField('décoller');
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(20);
    this.setTooltip('Décoller à l’altitude du parcours.');
  }
};

Blockly.Blocks['webeeblocks_forward'] = {
  init: function() {
    this.appendDummyInput()
        .appendField('avancer de')
        .appendField(new Blockly.FieldNumber(1.0, 0.1, 2.0, 0.1), 'DISTANCE')
        .appendField('m');
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(20);
    this.setTooltip('Avancer de la distance demandée.');
  }
};

Blockly.Blocks['webeeblocks_turn'] = {
  init: function() {
    this.appendDummyInput()
        .appendField('tourner de')
        .appendField(new Blockly.FieldNumber(90, -179, 179, 1), 'ANGLE')
        .appendField('°');
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(20);
    this.setTooltip('Angle positif : tourner à gauche. Angle négatif : tourner à droite.');
  }
};

Blockly.Blocks['webeeblocks_land'] = {
  init: function() {
    this.appendDummyInput().appendField('atterrir');
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(20);
    this.setTooltip('Atterrir.');
  }
};

// Stable semantic bridge used by CI and later by the runtime transport.
// The values are exactly those consumed by webeeblocks_executor.h:
// distances in metres, turns in radians, fixed takeoff delta = 1 m for v0.
(function(global) {
  const COMMAND = {
    webeeblocks_takeoff: 'TAKEOFF',
    webeeblocks_forward: 'FORWARD',
    webeeblocks_turn: 'TURN',
    webeeblocks_land: 'LAND'
  };

  function finiteNumber(block, field) {
    const value = Number(block.getFieldValue(field));
    if (!Number.isFinite(value))
      throw new Error('invalid numeric parameter ' + field + ' on ' + block.type);
    return value;
  }

  function commandFromBlock(block) {
    if (!Object.prototype.hasOwnProperty.call(COMMAND, block.type))
      throw new Error('unsupported block in Crazyflie mission: ' + block.type);

    if (block.type === 'webeeblocks_takeoff')
      return {type: 'TAKEOFF', value: 1.0};
    if (block.type === 'webeeblocks_land')
      return {type: 'LAND', value: 0.0};
    if (block.type === 'webeeblocks_forward') {
      const distance = finiteNumber(block, 'DISTANCE');
      if (!(distance >= 0.1 && distance <= 2.0))
        throw new Error('forward distance out of v0 range: ' + distance);
      return {type: 'FORWARD', value: distance};
    }

    const angleDeg = finiteNumber(block, 'ANGLE');
    if (angleDeg === 0 || Math.abs(angleDeg) >= 180)
      throw new Error('turn angle must satisfy 0 < |angle| < 180 degrees');
    return {type: 'TURN', value: angleDeg * Math.PI / 180.0};
  }

  function workspaceToMission(workspace) {
    const topBlocks = workspace.getTopBlocks(true);
    if (topBlocks.length !== 1)
      throw new Error('Crazyflie mission must contain exactly one top-level sequence');

    const mission = [];
    let block = topBlocks[0];
    while (block) {
      mission.push(commandFromBlock(block));
      block = block.getNextBlock();
    }

    if (mission.length < 2 || mission[0].type !== 'TAKEOFF' || mission[mission.length - 1].type !== 'LAND')
      throw new Error('Crazyflie mission must start with TAKEOFF and end with LAND');
    return mission;
  }

  global.WebeeBlocksCrazyflie = {
    workspaceToMission: workspaceToMission,
    commandFromBlock: commandFromBlock
  };
})(typeof window !== 'undefined' ? window : this);
