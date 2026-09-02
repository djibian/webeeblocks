(function() {
  'use strict';

  function localizeBlockInit(type, messages) {
    if (!window.Blockly || !Blockly.Blocks || !Blockly.Msg || !Blockly.Blocks[type] || typeof Blockly.Blocks[type].init !== 'function') return;
    var definition = Blockly.Blocks[type];
    var originalInit = definition.init;
    definition.init = function() {
      var previous = {};
      Object.keys(messages).forEach(function(key) {
        previous[key] = Blockly.Msg[key];
        Blockly.Msg[key] = messages[key];
      });
      try {
        return originalInit.call(this);
      } finally {
        Object.keys(messages).forEach(function(key) {
          Blockly.Msg[key] = previous[key];
        });
      }
    };
  }

  // Keep Blockly's upstream French message registry intact while adapting the
  // two rendered classroom blocks to the wording observed as clearer by pupils.
  localizeBlockInit('controls_if', {CONTROLS_IF_MSG_THEN: 'alors'});
  localizeBlockInit('controls_repeat_ext', {CONTROLS_REPEAT_INPUT_DO: ''});

  window.addEventListener('load', function() {
    var submit = document.getElementById('submit');
    if (!submit || typeof window.runProgram !== 'function') return;

    submit.onclick = function() {
      if (window.workspace && typeof workspace.getTopBlocks === 'function' && workspace.getTopBlocks(false).length === 0) {
        setRuntimeStatus('À COMPLÉTER', 'Ajoutez au moins une instruction avant de lancer le vol');
        return;
      }
      return runProgram();
    };
  });
})();
