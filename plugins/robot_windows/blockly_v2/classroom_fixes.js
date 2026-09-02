(function() {
  'use strict';

  // Pedagogical wording validated on the target classroom PC.
  if (window.Blockly && Blockly.Msg) {
    Blockly.Msg.CONTROLS_IF_MSG_THEN = 'alors';
    Blockly.Msg.CONTROLS_REPEAT_INPUT_DO = '';
  }

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
